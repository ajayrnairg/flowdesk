"""
services/extraction_task.py — Background extraction pipeline for FlowDesk KB.

─────────────────────────────────────────────────────────────────────────────
BACKGROUND TASK PATTERN DECISION: asyncio.create_task over BackgroundTasks
─────────────────────────────────────────────────────────────────────────────

FastAPI offers two lightweight options. Here's the honest comparison:

FastAPI BackgroundTasks
  • Managed by Starlette's middleware layer.
  • The task is tied to the HTTP response lifecycle: it starts AFTER the
    response is sent, but the worker process (Uvicorn) will wait for it to
    finish before fully clearing the request context.
  • DB sessions passed into a BackgroundTask are usually already closed or
    in a broken state by the time the task runs, because the FastAPI
    dependency (get_db) tears down when the route handler returns.
  • You must create a fresh DB session INSIDE the background task.
  • Safe: BackgroundTasks are awaited during server shutdown (ASGI lifespan),
    so a clean Render restart won't silently drop in-flight tasks.
  • Problem: long-running tasks (30s+ PDF extraction + Gemini summary) block
    the Uvicorn worker from picking up new requests if you run single-worker.

asyncio.create_task
  • Schedules a coroutine on the running event loop immediately.
  • Completely decoupled from the HTTP lifecycle — the request returns 202
    and the task keeps running independently.
  • You must still create a fresh DB session inside the task (same as above).
  • The event loop is shared with Uvicorn's I/O, so CPU-bound work (e.g.
    parsing a large PDF with pdfplumber) should be wrapped in
    asyncio.to_thread() to avoid blocking I/O for other requests.
  • Risk: if the process crashes or Render cold-restarts the container,
    any in-flight asyncio.create_task is lost silently.
    Mitigation: set status="pending" on DB insert BEFORE the task fires.
    On startup, a recovery routine re-queues any items stuck in "pending"
    or "processing" from a previous run.

RECOMMENDATION: asyncio.create_task for this project, because:
  1. The extraction pipeline is genuinely long (fetching URLs, calling
     Gemini). BackgroundTasks block Uvicorn's request handling for that
     duration on a single-worker Render free tier.
  2. asyncio.create_task runs concurrently alongside request handling via
     the event loop — the 202 response is returned in <5ms and extraction
     proceeds independently.
  3. The "lost on crash" risk is fully mitigated by the pending status +
     startup recovery pattern shown in this file.
  4. No extra infrastructure (no Redis, no Celery worker process, no ARQ
     broker) — the 512MB Render constraint is respected.

If you ever need guaranteed-once delivery or retry-with-backoff, the next
upgrade step is ARQ (async Redis Queue), not Celery. ARQ is ~10MB overhead.
─────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models.knowledge import KnowledgeItem, ItemStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The extraction pipeline
# ---------------------------------------------------------------------------

async def run_extraction(
    item_id: UUID,
    session_factory: async_sessionmaker,
) -> None:
    """
    Full extraction pipeline for one KnowledgeItem.

    Called via asyncio.create_task() from the router — never awaited directly.
    Creates its own DB session because the request-scoped session is gone.

    Pipeline steps:
      1. Mark status = "processing"
      2. Fetch/extract content (URL fetch or PDF parse)
      3. Compute read time
      4. Call Gemini for 2-sentence summary
      5. Mark status = "done", is_processed = True
      On any exception: mark status = "failed", log the error
    """
    async with session_factory() as db:
        try:
            # ── Step 1: claim the item ─────────────────────────────────────
            await _set_status(item_id, ItemStatus.PROCESSING, db)

            result = await db.execute(
                select(KnowledgeItem).where(KnowledgeItem.id == item_id)
            )
            item = result.scalar_one_or_none()
            if item is None:
                logger.error("run_extraction: item %s not found", item_id)
                return

            # ── Step 2: extract content ───────────────────────────────────
            if item.content_type == "pdf":
                raw_text, title, cover_image_url = await _extract_pdf(item)
            else:
                raw_text, title, cover_image_url = await _extract_url(item)

            # ── Step 3: read time ─────────────────────────────────────────
            estimated_read_minutes = _estimate_read_minutes(raw_text)

            # ── Step 4: Gemini summary ────────────────────────────────────
            summary = await _call_gemini_summary(raw_text, item.content_type)

            # ── Step 5: write back and mark done ─────────────────────────
            await db.execute(
                update(KnowledgeItem)
                .where(KnowledgeItem.id == item_id)
                .values(
                    raw_text=raw_text,
                    title=title or item.title,  # keep user-supplied title if set
                    cover_image_url=cover_image_url,
                    estimated_read_minutes=estimated_read_minutes,
                    summary=summary,
                    is_processed=True,
                    status=ItemStatus.DONE.value,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.info("run_extraction: item %s done", item_id)

        except Exception as exc:
            await db.rollback()
            logger.exception("run_extraction: item %s failed: %s", item_id, exc)
            try:
                await _set_status(item_id, ItemStatus.FAILED, db)
            except Exception:
                logger.exception("run_extraction: could not write failed status for %s", item_id)


async def _set_status(item_id: UUID, status: ItemStatus, db: AsyncSession) -> None:
    await db.execute(
        update(KnowledgeItem)
        .where(KnowledgeItem.id == item_id)
        .values(status=status.value, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Extraction stubs — replace with real implementations
# ---------------------------------------------------------------------------

async def _extract_url(item: KnowledgeItem) -> tuple[str, str | None, str | None]:
    """
    Fetch the URL and extract raw text, title, and cover image.

    Recommended libraries by content_type:
      article   → httpx + BeautifulSoup4 (parse og:title, og:image, article body)
                  OR newspaper3k (handles most article layouts automatically)
      youtube   → youtube-transcript-api (transcript as raw_text)
                  + pytube or yt-dlp for title/thumbnail
      github    → GitHub REST API (/repos/{owner}/{repo}) for README + metadata
      twitter   → Twitter/X API v2 or nitter scrape
      linkedin  → Direct scrape is blocked; use a dedicated scraping service

    All network I/O must use httpx (async) — never requests (sync blocks loop).
    """
    raise NotImplementedError("Implement _extract_url with httpx + content-type router")


async def _extract_pdf(item: KnowledgeItem) -> tuple[str, str | None, str | None]:
    """
    Extract text from a PDF stored at item.url (your storage path/URL).

    Recommended: pdfplumber (better table handling) or pypdf.
    Both are sync — wrap in asyncio.to_thread to avoid blocking the event loop:

        import asyncio, pdfplumber
        def _sync_extract(path: str) -> str:
            with pdfplumber.open(path) as pdf:
                return "\\n\\n".join(
                    p.extract_text() or "" for p in pdf.pages
                )
        raw_text = await asyncio.to_thread(_sync_extract, local_path)

    For cover_image: extract page 1 as image via pdf2image, upload to your
    storage bucket, return the public URL. This is optional for Stage 4.
    """
    raise NotImplementedError("Implement _extract_pdf with pdfplumber + asyncio.to_thread")


async def _call_gemini_summary(raw_text: str, content_type: str) -> str | None:
    """
    Call Google Gemini to produce a 2-sentence summary.

    pip install google-generativeai

    import asyncio, google.generativeai as genai
    from core.config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")  # free-tier friendly

    prompt = (
        f"Summarize the following {content_type} content in exactly 2 sentences. "
        f"Be direct and informative. Do not start with 'This article...'\\n\\n"
        f"{raw_text[:8000]}"  # cap tokens — 8k chars ≈ 2k tokens
    )

    # Gemini SDK is sync — run in thread
    response = await asyncio.to_thread(model.generate_content, prompt)
    return response.text.strip()
    """
    raise NotImplementedError("Implement _call_gemini_summary with google-generativeai")


def _estimate_read_minutes(raw_text: str | None) -> int | None:
    """Average adult reading speed is ~200 wpm."""
    if not raw_text:
        return None
    word_count = len(raw_text.split())
    return max(1, round(word_count / 200))


# ---------------------------------------------------------------------------
# Startup recovery — re-queue items stuck from a previous crash
# ---------------------------------------------------------------------------

async def recover_stuck_items(session_factory: async_sessionmaker) -> None:
    """
    Call this from main.py's lifespan startup hook.

    Any item in "pending" or "processing" at startup was interrupted by a
    process restart. Re-queue them as asyncio tasks.

    In main.py:
        from contextlib import asynccontextmanager
        from core.database import AsyncSessionLocal
        from services.extraction_task import recover_stuck_items

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            await recover_stuck_items(AsyncSessionLocal)
            yield

        app = FastAPI(lifespan=lifespan)
    """
    async with session_factory() as db:
        result = await db.execute(
            select(KnowledgeItem.id).where(
                KnowledgeItem.status.in_([
                    ItemStatus.PENDING.value,
                    ItemStatus.PROCESSING.value,
                ])
            )
        )
        stuck_ids = result.scalars().all()

    if stuck_ids:
        logger.info(
            "recover_stuck_items: re-queuing %d interrupted items", len(stuck_ids)
        )
        for item_id in stuck_ids:
            # Reset to pending before re-queuing so the task starts cleanly
            async with session_factory() as db:
                await db.execute(
                    update(KnowledgeItem)
                    .where(KnowledgeItem.id == item_id)
                    .values(status=ItemStatus.PENDING.value)
                )
                await db.commit()
            asyncio.create_task(
                run_extraction(item_id, session_factory),
                name=f"recover-{item_id}",
            )
