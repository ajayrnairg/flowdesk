# FlowDesk — Knowledge Base: Full Request Lifecycle

> **Purpose**: A deep-dive trace of every file involved in the Knowledge Base module — from the moment the user clicks "Save URL" in the browser, all the way through ingestion, AI processing, vector indexing, and eventually retrieval via semantic search.

---

## 1. The Two Journeys

The Knowledge module has two distinct user-triggered flows:

```
┌─────────────────────────────────────────────────────────┐
│  JOURNEY 1: SAVE                                        │
│  User saves a URL / PDF / bookmarklet clip              │
│  → Content extracted → AI summarised → Vector indexed  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  JOURNEY 2: SEARCH                                      │
│  User types a query into the Search page                │
│  → Query embedded → ANN vector search → AI synthesised │
└─────────────────────────────────────────────────────────┘
```

Both journeys are documented in full below with the exact file at each step.

---

## 2. Journey 1: Saving a URL

### Step 1 — UI: User Opens "Save URL" Dialog

**File**: `frontend/components/knowledge/AddUrlDialog.tsx`

```
User clicks "Save URL" button
→ <Dialog> opens
→ useEffect fires: getAuthenticatedApi() → GET /collections
    (fetches user's collections to populate the optional dropdown)
→ User pastes URL, optionally selects a collection, checks "Priority"
→ Clicks "Save to Knowledge Base"
```

**What happens in `handleSubmit`**:
```typescript
const api = await getAuthenticatedApi()  // useApi() injects Clerk JWT
api.post("/knowledge", { url, collection_id, is_priority })
// → returns 202 Accepted immediately
// → toast.success("Ingestion started")
// → calls onAdded() → parent page re-fetches knowledge list
```

The frontend receives `202 Accepted` and moves on. The actual processing happens entirely in the background on the server — the user sees the item appear with `status: "pending"` initially.

---

### Step 2 — HTTP: Arrives at FastAPI

**File**: `backend/routers/knowledge.py` → `POST /knowledge`

```python
# 1. Auth: Clerk JWT verified → User row looked up (or auto-created)
current_user: User = Depends(get_current_user)  # core/clerk_auth.py

# 2. Content type detection (synchronous, in-process)
content_type = detect_content_type(payload.url)
# → "youtube" / "github" / "article" / "twitter" / "linkedin"

# 3. Fast-fail for social platforms
if content_type in ["twitter", "linkedin"]:
    return {"status": "use_bookmarklet"}  # 200 not 202

# 4. Create KnowledgeItem row with status="pending"
new_item = KnowledgeItem(
    user_id=current_user.id,
    url=payload.url,
    content_type=content_type,
    status=ItemStatus.PENDING.value,
    is_processed=False
)
db.add(new_item)
await db.commit()

# 5. Register background task
background_tasks.add_task(safe_ingestion_runner, new_item.id)

# 6. Return 202 Accepted immediately — HTTP response sent here
return IngestAccepted(id=new_item.id, status=new_item.status)
```

---

### Step 3 — Content Type Detection

**File**: `backend/services/content_detector.py`

Pure function, no I/O. Uses `urllib.parse` to inspect the URL domain:

| URL Pattern | Detected Type |
|---|---|
| `youtube.com`, `youtu.be` | `youtube` |
| `github.com` | `github` |
| `twitter.com`, `x.com` | `twitter` |
| `linkedin.com` | `linkedin` |
| Anything else | `article` |

Note: `pdf` is never detected here — it's set explicitly by the PDF upload endpoint.

---

### Step 4 — Background Task Starts

**File**: `backend/routers/knowledge.py` → `safe_ingestion_runner`

After the HTTP response is sent, FastAPI runs the background task with a **fresh DB session** (not the request session, which closes after the response):

```python
async def safe_ingestion_runner(item_id: UUID):
    async with AsyncSessionLocal() as bg_db:   # fresh session
        await run_ingestion_pipeline(item_id, bg_db)
```

> **Critical**: This session isolation is why background tasks don't get `DetachedInstanceError`. The request's `get_db()` session closes when the response is sent. Background tasks must open their own session.

---

### Step 5 — Ingestion Orchestrator

**File**: `backend/services/ingestion_orchestrator.py` → `run_ingestion_pipeline()`

This is the core coordinator. It follows a numbered sequence:

```
1. Fetch KnowledgeItem from DB → mark status = "processing" → commit

2. Branch on content_type:
   ├── "youtube"   → fetch_youtube_content(url)           [youtube_extractor.py]
   │                   If IP blocked → fetch_with_jina(url)  [jina_extractor.py fallback]
   ├── "github"    → fetch_github_content(url)            [github_extractor.py]
   │                   If invalid URL → fetch_with_jina(url) [jina_extractor.py fallback]
   ├── "pdf"       → skip (text already extracted at upload time)
   ├── "twitter"   → error if no raw_text (must use bookmarklet)
   │   "linkedin"  /
   └── "article"   → fetch_with_jina(url)                 [jina_extractor.py]

3. If extractor returns {"error": ...}:
   → item.status = "failed"
   → commit → return

4. Apply extracted data to item:
   → item.title = ext_result["title"]   (if not already set)
   → item.raw_text = ext_result["raw_text"]
   → item.estimated_read_minutes = estimate_read_minutes(raw_text)
   → item.cover_image_url = ext_result["cover_image_url"]
   → item.is_processed = True

5. Generate AI summary:
   → generate_summary(title, raw_text, content_type)      [gemini_summariser.py]
   → item.summary = summary

6. Finalize:
   → item.status = "done"
   → commit

7. Auto-collection:
   → auto_add_to_collection(item.id, user_id, content_type, db)  [auto_collection_service.py]

8. RAG indexing:
   → index_knowledge_item(item.id, db)                    [rag_indexer.py]
```

If anything throws at any step, the outer `except` block sets `status = "failed"` and commits — the item never gets stuck in `"processing"`.

---

### Step 6 — Content Extraction (by type)

#### For Articles: `services/jina_extractor.py`

```
GET https://r.jina.ai/{url}
Headers: Accept: application/json, X-Return-Format: markdown

→ Returns JSON: { data: { title, content (markdown), image } }
→ Maps to: { title, raw_text, cover_image_url }
→ Timeout: JINA_TIMEOUT_SECONDS (default: 15s)
```

Jina AI Reader converts any web page into clean Markdown — no need to scrape HTML manually.

#### For YouTube: `services/youtube_extractor.py`

Fetches the video transcript using `youtube-transcript-api`. Falls back to Jina if the server IP is blocked by YouTube (common on cloud hosting like Render).

#### For GitHub: `services/github_extractor.py`

Parses the GitHub URL to extract owner/repo, then hits the GitHub REST API for `README.md` content. Falls back to Jina if the URL is not a valid repo URL.

#### For PDFs: `services/pdf_extractor.py`

Called synchronously during `POST /knowledge/upload-pdf` (not in the background). Uses `pypdf` in a `asyncio.to_thread` wrapper to avoid blocking the event loop.

---

### Step 7 — AI Summary Generation

**File**: `backend/services/gemini_summariser.py`

```python
prompt = f"""
You are summarising a saved {content_type} for a personal knowledge base.
Title: {title}
Content (truncated): {raw_text[:3000]}   ← first 3000 chars only
Write exactly 2 sentences summarising the key idea.
Return only the 2 sentences, no preamble.
"""
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)
```

- Truncates to **3000 chars** to control token cost and latency
- Uses `gemini-2.5-flash` (fast, cheap, good for summarisation)
- Retries up to 5× on `429` rate limit errors (exponential backoff via `tenacity`)
- Silent failure: returns `""` on any exception — ingestion still completes

---

### Step 8 — Auto-Collection

**File**: `backend/services/auto_collection_service.py`

Every saved item is automatically filed into a default collection by content type:

| Content Type | Default Collection | Color |
|---|---|---|
| `article` | 📰 Articles | `#3B82F6` (blue) |
| `youtube` | 🎥 Videos | `#EF4444` (red) |
| `github` | 💻 Repos & Docs | `#6B7280` (grey) |
| `twitter` / `linkedin` | 💬 Social Saves | `#8B5CF6` (purple) |
| `pdf` | 📄 PDFs | `#F97316` (orange) |

**Logic**: `get_or_create_default_collection()` checks if the collection already exists (SELECT first) before creating — safe for concurrent calls. `auto_add_to_collection()` wraps everything in `try/except` so a failure here never breaks the ingestion.

---

### Step 9 — RAG Indexing

**File**: `backend/services/rag_indexer.py`

```
a. Fetch KnowledgeItem from DB

b. Guard: item must have raw_text

c. Delete existing chunks for this item
   (DELETE FROM knowledge_chunks WHERE knowledge_item_id = ?)
   → supports re-indexing without duplicates
   → db.flush() ensures deletes apply before inserts

d. Chunk the raw_text → list of strings          [chunking_service.py]

e. Embed the chunks → list of 768-dim vectors    [embedding_service.py]

f. Create KnowledgeChunk rows:
   For each chunk+embedding:
     KnowledgeChunk(
       knowledge_item_id=item.id,
       user_id=item.user_id,    ← denormalised intentionally
       chunk_index=idx,
       chunk_text=chunk,
       embedding=vector
     )

g. db.add_all(chunk_objects) → commit

h. Log: "Indexed N chunks for item X"
```

Errors here are caught and logged — they do **not** fail the overall ingestion. The item stays `status="done"` but won't be searchable until it's reindexed (via `GET /search/reindex/{item_id}`).

---

### Step 9a — Chunking

**File**: `backend/services/chunking_service.py`

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,          # ~200 tokens — safe for 2048 token model limit
    chunk_overlap=150,       # context continuity at chunk boundaries
    separators=["\n\n", "\n", ". ", " ", ""]  # paragraph → sentence → word → char
)
```

- Texts under 800 chars are returned as a single chunk
- Post-processing: strips whitespace, filters chunks < 50 chars (noise)

---

### Step 9b — Embedding

**File**: `backend/services/embedding_service.py`

```python
# For document chunks (during indexing):
embed_content(
    model="models/gemini-embedding-2",   # EMBEDDING_MODEL setting
    contents=batch,                       # list of chunk strings
    config={
        "task_type": "RETRIEVAL_DOCUMENT",  # ← critical: optimises for corpus storage
        "output_dimensionality": 768
    }
)
```

- Batches up to **100 texts per API call** (Gemini's batch limit)
- 500ms sleep between batches for free-tier rate limiting
- Retries on 429 with exponential backoff (tenacity)
- `task_type="RETRIEVAL_DOCUMENT"` vs `"RETRIEVAL_QUERY"` matters — mixing them degrades cosine similarity quality

---

## 3. Ingestion Variants (3 Entry Points)

| Entry Point | Route | Extraction | Background Task |
|---|---|---|---|
| **URL** | `POST /knowledge` | Runs in background | `run_ingestion_pipeline` (full: extract + summarise + index) |
| **Bookmarklet** | `POST /knowledge/bookmarklet` | Text already sent by browser | `run_summary_only` (summarise + index only) |
| **PDF upload** | `POST /knowledge/upload-pdf` | `extract_pdf_text()` — synchronous during request | `run_summary_only` (summarise + index only) |

---

## 4. Journey 2: Searching the Knowledge Base

### Step 1 — UI: User Types a Query

**File**: `frontend/app/(dashboard)/search/page.tsx`

```
User types query → input debounced
User submits form → handleSearch()
    → const api = await getAuthenticatedApi()
    → api.post("/search", { query }, { signal: abortController.signal })
        (AbortSignal cancels in-flight request if user types again)
    → Shows loading state
    → On success: render answer + source cards
    → Shows "cached" badge if response.cached === true
    → Shows "took_ms" latency indicator
```

---

### Step 2 — HTTP: Arrives at FastAPI

**File**: `backend/routers/search.py` → `POST /search`

```
1. Auth: Clerk JWT → get_current_user

2. Cache check: get_cached_search(user_id, query)   [cache_service.py]
   Cache key: "search:{user_id}:{md5(query.lower().strip())}"
   → Hit: return immediately with cached=True, elapsed_ms

3. semantic_search(query, user_id, db)              [search_service.py]

4. synthesise_answer(query, chunks)                 [synthesis_service.py]

5. Build SearchResponse:
   {
     query, answer,
     sources: [ { knowledge_item_id, title, content_type, url,
                  chunk_excerpt (200 chars), similarity_score } ],
     cached: False, took_ms
   }

6. Fire-and-forget cache write:
   asyncio.create_task(cache_search_result(...))    [cache_service.py]
   (excludes "cached" and "took_ms" from stored payload)

7. Return SearchResponse
```

---

### Step 3 — Semantic Search

**File**: `backend/services/search_service.py`

```
a. Embed the query:
   embed_query(query)                               [embedding_service.py]
   task_type="RETRIEVAL_QUERY"   ← matches against RETRIEVAL_DOCUMENT vectors

b. ANN search with pgvector:
   SELECT knowledge_chunks, cosine_distance(embedding, query_vector) AS distance
   WHERE user_id = ?                               ← pre-filter via B-tree index
   AND embedding IS NOT NULL
   ORDER BY distance ASC                           ← HNSW index kicks in here
   LIMIT 5

c. N+1 prevention: collect unique knowledge_item_ids from results
   → Single IN query to fetch parent KnowledgeItem metadata
   → Build {id: item} map for O(1) lookups

d. Format: return list of dicts with chunk_text, distance, item_title,
   item_url, item_content_type, chunk_excerpt (200 chars)
   similarity_score = round(1.0 - distance, 4)    ← router converts distance→similarity
```

**Why cosine distance works**: Both RETRIEVAL_DOCUMENT and RETRIEVAL_QUERY vectors are unit-normalised by Gemini, so cosine distance and dot product are equivalent. Lower distance = higher similarity.

---

### Step 4 — AI Answer Synthesis

**File**: `backend/services/synthesis_service.py`

```python
# Builds context from top-k chunks:
context = """
[Source 1: Article Title (article)]
chunk_text...

---

[Source 2: YouTube Title (youtube)]
chunk_text...
"""

prompt = f"""
You are a personal knowledge assistant. Answer ONLY using the sources below.
Do not use outside knowledge. List sources used at the end.
Keep answer 3-5 sentences.

USER QUERY: {query}
SOURCES: {context}
ANSWER:
"""

response = gemini-2.5-flash.generate_content(prompt)
```

- If no chunks found: returns a graceful "no relevant information" message
- If Gemini fails: returns "Could not generate an answer. Here are the relevant sources."
- Retries on 429 (tenacity, same as summariser)

---

### Step 5 — Redis Cache

**File**: `backend/services/cache_service.py`

```
Cache key format: "search:{user_id}:{md5(query.lower().strip())}"
TTL: 3600 seconds (1 hour)
Client: Upstash Redis REST (HTTP-based, serverless-friendly — no persistent TCP connections)

Read path: redis.get(key) → json.loads(value) → return dict
Write path: json.dumps(result, default=str) → redis.set(key, value, ex=3600)

Both paths are fully silent on failure (try/except + logger.warning only).
```

---

## 5. Complete End-to-End File Map

### Save Flow

```
frontend/components/knowledge/AddUrlDialog.tsx
    ↓ POST /knowledge
backend/routers/knowledge.py
    ↓ detect_content_type()
backend/services/content_detector.py
    ↓ creates KnowledgeItem row
backend/models/knowledge.py
    ↓ background task
backend/services/ingestion_orchestrator.py
    ├── fetch_with_jina()          → backend/services/jina_extractor.py
    ├── fetch_youtube_content()    → backend/services/youtube_extractor.py
    ├── fetch_github_content()     → backend/services/github_extractor.py
    ├── extract_pdf_text()         → backend/services/pdf_extractor.py
    ↓ generate_summary()
backend/services/gemini_summariser.py
    ↓ auto_add_to_collection()
backend/services/auto_collection_service.py
    → backend/models/knowledge.py [Collection, CollectionItem]
    ↓ index_knowledge_item()
backend/services/rag_indexer.py
    ├── chunk_text()               → backend/services/chunking_service.py
    └── embed_texts()              → backend/services/embedding_service.py
        → backend/models/knowledge_chunk.py [KnowledgeChunk rows written to DB]
```

### Search Flow

```
frontend/app/(dashboard)/search/page.tsx
    ↓ POST /search
backend/routers/search.py
    ├── get_cached_search()        → backend/services/cache_service.py → Upstash Redis
    ↓ semantic_search()
backend/services/search_service.py
    └── embed_query()              → backend/services/embedding_service.py → Gemini API
        → pgvector ANN query on knowledge_chunks (HNSW index)
        → IN query on knowledge_items for metadata
    ↓ synthesise_answer()
backend/services/synthesis_service.py → Gemini API
    ↓ cache_search_result()        → backend/services/cache_service.py → Upstash Redis
    ↓ SearchResponse → frontend
```

---

## 6. Status Lifecycle of a KnowledgeItem

```
User submits URL
    → status: "pending"      (created in router, before background task starts)
    → status: "processing"   (set at start of run_ingestion_pipeline)
    → status: "done"         (set after successful extraction + summary)
    → status: "failed"       (set if any step errors — including extractor errors)

Stuck items can be retried via:
    POST /knowledge/reprocess    ← retries all failed/pending/processing items
    GET /search/reindex/{id}     ← force re-embed and re-index one specific item
```

---

## 7. Important Gotchas

| Gotcha | Detail |
|---|---|
| **Background task session** | Never pass the request `db` into a background task — it closes with the HTTP response. Always open a new `AsyncSessionLocal()`. |
| **Twitter/LinkedIn fast-fail** | These are detected synchronously and the route returns early with `use_bookmarklet` before creating any DB row. |
| **YouTube IP blocking** | Render's IPs are often blocked by YouTube. The orchestrator has a Jina fallback for this. |
| **RAG indexing failure is silent** | If `index_knowledge_item` fails, the item stays `status="done"` but isn't searchable. Use `GET /search/reindex/{id}` to fix. |
| **Chunk deletion on re-index** | `rag_indexer.py` deletes all existing chunks before creating new ones — safe for re-ingestion, but means there's a brief window with no chunks. |
| **Embedding task_type mismatch** | Documents use `RETRIEVAL_DOCUMENT`; queries use `RETRIEVAL_QUERY`. Mixing these silently degrades search quality. |
| **Cache excludes took_ms/cached** | These metadata fields are excluded from the Redis payload so they remain accurate when re-hydrated from cache. |
| **Auto-collection is non-blocking** | Wrapped in `try/except` — a failure here never aborts ingestion. |

---

## 8. Next Steps for Exploration

1. ✅ `docs/architecture_overview.md` — High-level tech stack & layout
2. ✅ `docs/data_models.md` — Database tables & relationships
3. ✅ `docs/backend_api_map.md` — All API routes and what they do
4. ✅ `docs/frontend_architecture.md` — Pages, components, and state
5. ✅ `docs/flow_knowledge_base.md` — **You are here** — Complete lifecycle trace

---

> **All 5 documents complete.** You now have a full reference for the FlowDesk codebase.
> Recommended reading order when returning after a break: `architecture_overview` → `data_models` → `backend_api_map` → this file.
