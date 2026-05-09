# FlowDesk — Backend API Map

> **Purpose**: A complete reference of every API route in the FlowDesk FastAPI backend — what it does, what auth it requires, what files handle its logic, and any non-obvious behaviour.

---

## 1. Entry Point & Middleware (`main.py`)

The app starts in `backend/main.py`. Key things that happen before any route runs:

```
Request arrives
    → HTTP logging middleware (logs method, path, status, ms — skips /health)
    → CORS middleware (allows localhost:3000 + all *.vercel.app origins)
    → Route matched → handler runs
    → Global exception handler catches unhandled errors → 500 JSON
```

**Registered routers** (in order):
| Router | Prefix | File |
|---|---|---|
| `auth` | `/auth` | `routers/auth.py` |
| `tasks` | `/tasks` | `routers/tasks.py` |
| `notifications` | `/notifications` | `routers/notifications.py` |
| `knowledge` | `/knowledge` | `routers/knowledge.py` |
| `collections` | `/collections` | `routers/collections.py` |
| `search` | `/search` | `routers/search.py` |
| health check | `/health` | inline in `main.py` |

---

## 2. Authentication Model (`core/clerk_auth.py`)

Every protected route uses `Depends(get_current_user)` which lives in `core/clerk_auth.py`. Here is the exact flow on every authenticated request:

```
Authorization: Bearer <clerk_jwt>
    1. Extract token from header (HTTPBearer scheme)
    2. Verify JWT signature using Clerk's RSA public key (RS256)
       → ExpiredSignatureError → 401 "Token has expired"
       → JWTError → 401 "Invalid or expired token"
    3. Extract claims: clerk_user_id ("user_id"), email
    4. DB lookup by clerk_user_id → if found → return User
    5. DB lookup by email (migration fallback) → if found → backfill clerk_user_id → return User
    6. Neither found → auto-provision new User row with blank hashed_password → return User
```

> **Key insight**: The backend auto-creates a `User` row on the first authenticated request from a new Clerk user. You never need to call `/auth/register` for Clerk users.

---

## 3. Route Reference

### 🔧 System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET/HEAD` | `/health` | ❌ None | Returns `{"status": "ok"}`. Used by UptimeRobot for uptime monitoring. **Does not touch the DB** (by design — avoids waking NeonDB). |

---

### 👤 Auth (`/auth`) — `routers/auth.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | ❌ None | ~~**DEPRECATED**~~ — Password-based registration. Clerk handles this now. Kept for backwards compatibility only. |
| `POST` | `/auth/login` | ❌ None | ~~**DEPRECATED**~~ — Password-based login returning a JWT. Clerk handles this now. |
| `GET` | `/auth/me` | ✅ Clerk JWT | Returns the current user's profile (`UserOut` schema). The Clerk dependency auto-creates the user on first call. |

> ⚠️ `/auth/register` and `/auth/login` are marked `deprecated=True` in FastAPI, which adds a strikethrough in `/docs`. Do not use these for new code.

---

### ✅ Tasks (`/tasks`) — `routers/tasks.py`

All routes require Clerk JWT auth. Ownership is enforced by `get_task_or_fail()` helper — returns `404` if not found, `403` if not owned.

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/tasks` | ✅ | List all tasks. On every call, **recurring tasks are spawned** if `last_spawned_at != today`. Query params: `scope` (`DAILY`/`WEEKLY`/`MONTHLY`), `is_done` (bool), `is_history` (bool). |
| `POST` | `/tasks` | ✅ | Create a new task. **Case-insensitive duplicate check** on title — rejects if a task with the same title already exists for this user. |
| `PATCH` | `/tasks/{task_id}` | ✅ | Partial update of `title`, `notes`, `priority`, `due_date`. Uses `exclude_unset=True` so only sent fields are updated. |
| `PATCH` | `/tasks/{task_id}/toggle` | ✅ | Explicitly set `is_done`. When set to `True`, also sets `last_completed_at = today`. |
| `DELETE` | `/tasks/{task_id}` | ✅ | Hard delete. Returns `204 No Content`. |

**Recurring task spawning logic** (runs inside `GET /tasks`):
```
1. Load all master tasks where is_recurring=True for this user
2. For each master:
   - Skip if last_spawned_at == today
   - Check if a child already exists for today (safety net)
   - If not: create a new Task instance (is_recurring=False, parent_id=master.id, due_date=today)
   - Set master.last_spawned_at = today
3. Commit all new instances
4. Continue to normal list query
```

**Default sort order** (non-history): Incomplete first → High priority first → Due date soonest first (nulls last).

---

### 🧠 Knowledge (`/knowledge`) — `routers/knowledge.py`

All routes require Clerk JWT. Ownership enforced by `_get_item_or_404()` helper.

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/knowledge` | ✅ | Ingest a URL. Fast-fails for `twitter`/`linkedin` (returns `use_bookmarklet`). Otherwise creates a `KnowledgeItem` (status=`pending`) and fires `run_ingestion_pipeline` as a **background task**. Returns `202 Accepted` immediately. |
| `POST` | `/knowledge/bookmarklet` | ✅ | Ingest pre-selected text from the browser bookmarklet. Text is already extracted, so only `run_summary_only` (Gemini) runs in background. |
| `POST` | `/knowledge/upload-pdf` | ✅ | Upload a PDF file. Synchronously extracts text (fast), then `run_summary_only` runs in background. Rejects files > 10MB or non-PDF MIME types. |
| `POST` | `/knowledge/reprocess` | ✅ | Admin/debug endpoint. Retries all `failed`/`pending`/`processing` items for the current user. |
| `GET` | `/knowledge` | ✅ | List all knowledge items. Query params: `content_type`, `item_status`, `is_priority` (bool), `q` (title search, case-insensitive ilike). Ordered by `created_at DESC`. |
| `GET` | `/knowledge/{item_id}` | ✅ | Get one item. **Side effect**: updates `last_opened_at = now()` on every fetch. |
| `PATCH` | `/knowledge/{item_id}` | ✅ | Update user-editable fields: `title`, `tags`, `read_status`. Auto-sets `read_at = now()` on first transition to `DONE`. |
| `DELETE` | `/knowledge/{item_id}` | ✅ | Hard delete item. `CollectionItem` join rows cascade automatically. |
| `PATCH` | `/knowledge/{item_id}/read-status` | ✅ | Dedicated read-progress endpoint. Sets `read_status` + `last_opened_at`. Sets `read_at` once on first `DONE` transition. |

**Background task session safety**: Background tasks cannot reuse the request's DB session (it closes when the HTTP response is sent). A new `AsyncSessionLocal()` is opened inside the background task:
```python
async def safe_ingestion_runner(item_id):
    async with AsyncSessionLocal() as bg_db:
        await run_ingestion_pipeline(item_id, bg_db)
```

---

### 📚 Collections (`/collections`) — `routers/collections.py`

All routes require Clerk JWT. Ownership enforced by `_get_collection_or_404()` — always returns `404` (not `403`) to avoid leaking other users' collection IDs.

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/collections` | ✅ | List all collections **with item counts and unread counts** (via a SQL subquery + `COALESCE`). Default collections sorted first. |
| `POST` | `/collections` | ✅ | Create a custom collection (name, description, color, emoji). `is_default=False` always. |
| `GET` | `/collections/{collection_id}` | ✅ | Fetch a single collection. Handles the **virtual "Priority List"** (`id=00000000-0000-0000-0000-000000000001`) as a special case — it has no real DB row. |
| `PATCH` | `/collections/{collection_id}` | ✅ | Update name, description, color, emoji. |
| `DELETE` | `/collections/{collection_id}` | ✅ | Delete collection (not its items). **Blocked for `is_default=True` collections.** Returns `403`. |
| `GET` | `/collections/{collection_id}/items` | ✅ | List items in a collection, optionally filtered by `read_status`. UNREAD items sorted first. Handles virtual Priority List. |
| `POST` | `/collections/{collection_id}/items` | ✅ | Link an existing `KnowledgeItem` to a collection. Rejects duplicates (`409`). |
| `DELETE` | `/collections/{collection_id}/items/{item_id}` | ✅ | Unlink item from collection (**item is not deleted**, only the `CollectionItem` join row). |
| `GET` | `/collections/library/overview` | ✅ | **Performance-critical aggregation** for the Library page. Loads everything in **exactly 2 DB queries** (1: collections + counts, 2: all items via IN clause), assembles in Python. Returns top-10 items per collection preview. Injects virtual "Priority List" at position 0 if the user has priority items. |

> ⚠️ **Route ordering gotcha**: `GET /collections/library/overview` must be registered before `GET /collections/{collection_id}`, otherwise FastAPI would match `"library"` as a UUID and return a 422 error. The file-level ordering handles this correctly.

---

### 🔔 Notifications (`/notifications`) — `routers/notifications.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/notifications/send-my-digest` | ✅ Clerk JWT | Triggers an on-demand digest for the current user (for testing / Settings page). |
| `GET/HEAD` | `/notifications/check-and-send` | 🔑 `X-Notification-Token` header | **UptimeRobot webhook**. Time-gated: only fires if `hour == DIGEST_HOUR_UTC` and `minute < DIGEST_WINDOW_MINUTES`. Deduplication: checks `NotificationLog` to skip if already sent today (IST timezone). |
| `POST` | `/notifications/send-digest` | 🔑 `X-Notification-Token` header | **Unconditional digest trigger** for GitHub Actions / manual overrides. No time-gating or dedup. |
| `POST` | `/notifications/subscriptions` | ✅ Clerk JWT | Upsert a browser VAPID push subscription (endpoint, p256dh, auth keys). Handles re-registration gracefully. |
| `DELETE` | `/notifications/subscriptions/{sub_id}` | ✅ Clerk JWT | Remove a push subscription (e.g. user logs out of a device). |

**Digest trigger flow**:
```
UptimeRobot pings GET /notifications/check-and-send every 5 min
    → verify X-Notification-Token header
    → check if now_utc.hour == DIGEST_HOUR_UTC (default: 1 AM UTC = 6:30 AM IST)
    → check if minute < DIGEST_WINDOW_MINUTES (default: 15)
    → check NotificationLog: already sent today (IST bounds)?
    → fire send_morning_digest_to_all_users()
        → for each user: digest_query.py → email_service.py + push_service.py
        → log to NotificationLog
```

---

### 🔍 Search (`/search`) — `routers/search.py`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/search` | ✅ Clerk JWT | Semantic search over user's knowledge base with AI-synthesised answer. Cache-aside via Upstash Redis. |
| `GET` | `/search/reindex/{item_id}` | ✅ Clerk JWT | Force synchronous re-embedding + indexing of one item. Used for items saved before the RAG pipeline was deployed. |

**Search pipeline** (inside `POST /search`):
```
1. Check Upstash Redis cache (key = user_id + query)
   → Cache hit: return immediately with cached=True

2. semantic_search(query, user_id, db)
   → Embed query via Gemini (gemini-embedding-2, 768 dims)
   → ANN search on knowledge_chunks using HNSW cosine distance
   → Filter by user_id (denormalised column, avoids JOIN)
   → Return top-k chunks with metadata

3. synthesise_answer(query, chunks)
   → Gemini generates a natural-language answer from chunk context

4. Build SearchResponse: answer + sources (with similarity scores)

5. Cache result in Redis (fire-and-forget via asyncio.create_task)
   → Excludes cached/took_ms from stored payload to keep them accurate on re-hydration
```

---

## 4. Auth Dependency Decision Tree

When writing a new route, use this to choose the right `Depends`:

```
Is the route protected by user identity?
├── YES → use: Depends(get_current_user) from core/clerk_auth.py
│         (Verifies Clerk JWT + auto-creates User row)
│
├── Is it a server-to-server internal webhook?
│   └── YES → verify X-Notification-Token header manually
│             (see notifications.py verify_token helper)
│
└── NO (public route) → No Depends needed
```

---

## 5. Error Response Convention

| Scenario | HTTP Code |
|---|---|
| Resource not found | `404` |
| User doesn't own resource | `403` (tasks) or `404` (collections — hides existence) |
| Invalid/expired JWT | `401` |
| Duplicate creation | `400` (tasks) or `409` (collections, push subscriptions) |
| Unsupported file type | `415` |
| File too large | `413` |
| AI/DB service failure | `503` |
| Any unhandled exception | `500` (global handler in `main.py`) |

---

## 6. Files Involved per Module

| Module | Router | Services Used | Models Used |
|---|---|---|---|
| Auth | `routers/auth.py` | `core/security.py`, `core/clerk_auth.py` | `User` |
| Tasks | `routers/tasks.py` | — (logic inline) | `Task` |
| Knowledge | `routers/knowledge.py` | `ingestion_orchestrator`, `content_detector`, `pdf_extractor`, `gemini_summariser` | `KnowledgeItem`, `CollectionItem` |
| Collections | `routers/collections.py` | — (logic inline) | `Collection`, `CollectionItem`, `KnowledgeItem` |
| Notifications | `routers/notifications.py` | `digest_orchestrator`, `digest_query`, `email_service`, `push_service` | `NotificationLog`, `PushSubscription` |
| Search | `routers/search.py` | `search_service`, `synthesis_service`, `cache_service`, `rag_indexer`, `embedding_service` | `KnowledgeChunk`, `KnowledgeItem` |

---

## 7. Next Steps for Exploration

1. ✅ `docs/architecture_overview.md` — High-level tech stack & layout
2. ✅ `docs/data_models.md` — Database tables & relationships
3. ✅ `docs/backend_api_map.md` — **You are here**
4. ⬜ `docs/frontend_architecture.md` — Pages, components, and state
5. ⬜ `docs/flow_knowledge_base.md` — Full request lifecycle trace (Knowledge module)
