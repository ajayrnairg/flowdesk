# FlowDesk — Architecture Overview

> **Purpose**: This document is a persistent reference for understanding the high-level structure, tech stack, and layout of the FlowDesk codebase. Refer back to this before diving into any module.

---

## 1. What is FlowDesk?

FlowDesk is a **full-stack productivity PWA (Progressive Web App)** built for personal knowledge management, task planning, and AI-powered content digests. It has:

- A **FastAPI** Python backend deployed on **Render**
- A **Next.js 16** (App Router) frontend deployed on **Vercel**
- A **PostgreSQL** database hosted on **NeonDB** (serverless), with vector search via `pgvector`
- **Clerk** for authentication
- **Google Gemini** for AI features (summarisation, embeddings, RAG)
- **Upstash Redis** for rate limiting / caching
- **Resend** for transactional email (morning digest)
- **Web Push (VAPID)** for PWA push notifications

---

## 2. Repository Structure

```
flowdesk/
├── backend/                  # Python FastAPI backend
├── frontend/                 # Next.js 16 frontend (App Router)
├── scripts/                  # Utility scripts (icon gen, digest testing)
├── docs/                     # 📌 YOU ARE HERE — reference documentation
├── ARCHITECTURE.md           # High-level architecture summary (brief)
├── BOOKMARKLET.js            # Browser bookmarklet for saving web content
├── README.md                 # Public-facing project readme
└── SETUP.md                  # Local development setup guide
```

---

## 3. Backend (`/backend`)

**Runtime**: Python 3.x + FastAPI + Uvicorn
**Deployed on**: Render (Singapore region, free tier)
**Database**: NeonDB (PostgreSQL + pgvector), via asyncpg + SQLAlchemy 2.0

### Directory Breakdown

```
backend/
├── main.py               # 🚀 App entry point — registers all routers, middleware, CORS
├── core/
│   ├── config.py         # Pydantic Settings — loads all env vars from .env
│   ├── database.py       # SQLAlchemy async engine (NullPool for serverless)
│   ├── clerk_auth.py     # Clerk JWT verification (RS256) — auth dependency
│   └── security.py       # Password hashing helpers (bcrypt/passlib)
├── models/               # SQLAlchemy ORM table definitions
│   ├── user.py
│   ├── task.py
│   ├── knowledge.py
│   ├── knowledge_chunk.py
│   └── notification.py
├── schemas/              # Pydantic request/response DTOs (validation layer)
├── routers/              # FastAPI route handlers (HTTP layer)
│   ├── auth.py
│   ├── tasks.py
│   ├── knowledge.py
│   ├── collections.py
│   ├── notifications.py
│   └── search.py
├── services/             # Business logic layer (AI, ingestion, email, push, etc.)
│   ├── ingestion_orchestrator.py   # Orchestrates content ingestion pipeline
│   ├── embedding_service.py        # Gemini embeddings for vector search
│   ├── rag_indexer.py              # RAG indexing (chunk → embed → store)
│   ├── search_service.py           # Semantic search logic
│   ├── chunking_service.py         # Text chunking via LangChain
│   ├── digest_orchestrator.py      # Daily digest orchestration
│   ├── digest_query.py             # Queries knowledge for digest content
│   ├── email_service.py            # Resend email sending
│   ├── push_service.py             # Web Push / VAPID notifications
│   ├── gemini_summariser.py        # Gemini-based summarisation
│   ├── synthesis_service.py        # AI synthesis of knowledge chunks
│   ├── collection_service.py       # Knowledge collection management
│   ├── auto_collection_service.py  # Auto-tagging content into collections
│   ├── cache_service.py            # Upstash Redis caching
│   ├── content_detector.py         # Detects content type (PDF, YouTube, GitHub, URL)
│   ├── jina_extractor.py           # Extracts web content via Jina AI
│   ├── github_extractor.py         # Extracts GitHub repo content
│   ├── youtube_extractor.py        # Extracts YouTube transcripts
│   └── pdf_extractor.py            # Parses uploaded PDFs
├── alembic/              # Database migration scripts
├── tests/                # pytest test suite
├── requirements.txt      # Python dependencies
├── render.yaml           # Render deployment config
└── Procfile              # Process config (for Render)
```

### Key Architectural Patterns

| Pattern | Detail |
|---|---|
| **Database connection** | `NullPool` — no persistent connections; each request opens & closes its own connection. Optimized for NeonDB serverless. |
| **Auth** | Clerk JWT (RS256) verified on every protected route via `clerk_auth.py`. The token comes from the frontend via `Authorization: Bearer` header. |
| **Dependency injection** | FastAPI's `Depends()` used for DB sessions (`get_db`) and auth (`get_current_user`) |
| **Async throughout** | All DB operations use `async with session`, all routes are `async def` |

---

## 4. Frontend (`/frontend`)

**Framework**: Next.js 16 (App Router)
**Language**: TypeScript
**Styling**: Tailwind CSS v4 + shadcn/ui + Radix UI
**Auth**: Clerk (`@clerk/nextjs`)
**Deployed on**: Vercel

### Directory Breakdown

```
frontend/
├── app/                      # Next.js App Router pages
│   ├── layout.tsx            # Root layout (minimal shell, no auth)
│   ├── page.tsx              # Landing / redirect to /planner
│   ├── sign-in/              # Clerk-powered sign-in page
│   ├── sign-up/              # Clerk-powered sign-up page
│   └── (dashboard)/          # Route group — all protected pages share DashboardLayout
│       ├── layout.tsx        # 🔑 Dashboard shell: nav, mobile bottom bar, toaster, service worker
│       ├── planner/          # Task planning page
│       ├── knowledge/        # Knowledge base page (add/view knowledge items)
│       ├── library/          # Collections / saved content library
│       ├── search/           # Semantic search page
│       ├── save/             # Bookmarklet save landing page
│       └── settings/         # User settings (push notifications, preferences)
├── components/
│   ├── DashboardNav.tsx      # Top navigation bar (desktop)
│   ├── tasks/                # Task-related UI components
│   ├── knowledge/            # Knowledge-related UI components
│   ├── library/              # Library/collections UI components
│   ├── notifications/        # Notification UI components
│   ├── search/               # Search UI components
│   └── ui/                   # shadcn/ui base components (Button, Dialog, etc.)
├── lib/
│   ├── api.ts                # Axios instance — base URL + Clerk token injection
│   ├── auth.ts               # Clerk auth helpers
│   ├── tasks.ts              # Task API call functions
│   ├── knowledge.ts          # Knowledge API call functions
│   ├── library.ts            # Library/collections API call functions
│   ├── search.ts             # Search API call functions
│   ├── push.ts               # PWA push notification registration logic
│   └── utils.ts              # cn() utility (clsx + tailwind-merge)
├── hooks/
│   └── useApi.ts             # Generic API hook wrapper
├── types/                    # TypeScript type definitions
├── public/                   # Static assets, PWA icons, service worker
├── middleware.ts             # 🔐 Route protection via Clerk middleware
└── next.config.ts            # Next.js configuration
```

### Key Architectural Patterns

| Pattern | Detail |
|---|---|
| **App Router** | All pages live in `app/`. The `(dashboard)` group applies a shared layout to all protected pages without affecting the URL. |
| **Route protection** | `middleware.ts` uses `clerkMiddleware` — any non-public route triggers `auth.protect()`. Public routes: `/`, `/sign-in`, `/sign-up`. |
| **API communication** | All backend calls go through `lib/api.ts` which is an Axios instance pre-configured with the backend base URL and a Clerk JWT token injected into every request header. |
| **State management** | Minimal — no Redux/Zustand. Local `useState`/`useEffect` per page. API calls are made in components using functions from `lib/`. |
| **PWA** | Service worker registered in `DashboardLayout`. Push notification subscription managed in `lib/push.ts`. |
| **Mobile layout** | Desktop uses `DashboardNav` (top bar). Mobile uses `MobileBottomNav` (fixed bottom bar, hidden on `md` and above). |

---

## 5. Infrastructure & External Services

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (Browser / PWA)                      │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS
                         ▼
              ┌──────────────────────┐
              │  Vercel (Frontend)   │  Next.js 16 App
              │  flowdesk.vercel.app │
              └──────────┬───────────┘
                         │ REST API calls (Axios + Clerk JWT)
                         ▼
              ┌──────────────────────┐
              │  Render (Backend)    │  FastAPI + Uvicorn
              │  Singapore Region    │
              └──────────┬───────────┘
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
  ┌──────────────┐ ┌──────────┐ ┌──────────────┐
  │  NeonDB      │ │ Upstash  │ │  Clerk Auth  │
  │  PostgreSQL  │ │  Redis   │ │  (JWT/OAuth) │
  │  + pgvector  │ │  Cache   │ │              │
  └──────────────┘ └──────────┘ └──────────────┘
          │
  ┌───────┴────────┐
  │  Google Gemini │  Embeddings + Summarisation + RAG
  └────────────────┘
          │
  ┌───────┴────────┐
  │  Resend Email  │  Morning digest delivery
  └────────────────┘
```

### Environment Variables (Backend)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | NeonDB PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (legacy, now Clerk handles auth) |
| `CLERK_JWT_SIGNING_KEY` | Clerk RS256 public key for JWT verification |
| `NOTIFICATION_SECRET` | Shared secret for triggering digest from cron |
| `RESEND_API_KEY` | Transactional email via Resend |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Web push notification keys |
| `VAPID_CLAIM_EMAIL` | VAPID contact email |
| `GEMINI_API_KEY` | Google Gemini (embeddings + summarisation) |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` | Redis cache/rate limiting |
| `GITHUB_TOKEN` | Optional: GitHub API for repo extraction |
| `DIGEST_HOUR_UTC` | Hour to send morning digest (default: 1 = 6:30 AM IST) |
| `EMBEDDING_MODEL` | Gemini embedding model name |

---

## 6. Data Flow Summary

```
User Action → Next.js Page/Component
    → lib/*.ts API function
        → Axios (lib/api.ts) with Clerk JWT header
            → FastAPI Router (routers/*.py)
                → Auth check via clerk_auth.py
                    → Service layer (services/*.py)
                        → SQLAlchemy model query (models/*.py)
                            → NeonDB (PostgreSQL)
                        ← Result returned
                    ← Pydantic schema (schemas/*.py) serialises response
                ← JSON response
            ← Axios response
        ← Component state update
    ← UI re-renders
```

---

## 7. Next Steps for Exploration

Use these documents in sequence:

1. ✅ `docs/architecture_overview.md` — **You are here**
2. ⬜ `docs/data_models.md` — Database tables & relationships
3. ⬜ `docs/backend_api_map.md` — All API routes and what they do
4. ⬜ `docs/frontend_architecture.md` — Pages, components, and state
5. ⬜ `docs/flow_knowledge_base.md` — Full request lifecycle trace (Knowledge module)
