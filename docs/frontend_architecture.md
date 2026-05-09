# FlowDesk — Frontend Architecture

> **Purpose**: Reference document for the Next.js frontend — routing, layout system, authentication, component structure, API communication pattern, and state management.

---

## 1. Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v4 + shadcn/ui + Radix UI |
| Auth | Clerk (`@clerk/nextjs`) |
| HTTP client | Axios (`lib/api.ts`) |
| Forms | react-hook-form + Zod |
| Notifications (UI) | Sonner (toast library) |
| Icons | Lucide React |
| Date utilities | date-fns, react-day-picker |
| Theming | next-themes |
| Deployment | Vercel |

---

## 2. App Router — Page Hierarchy

The entire app uses the **Next.js App Router** (`app/` directory). There are no Pages Router files.

```
app/
├── layout.tsx                      ← Root layout: ClerkProvider wraps entire app
├── page.tsx                        ← Smart redirect: /planner (authed) or /sign-in
├── globals.css                     ← Global styles, Tailwind base
│
├── sign-in/                        ← Clerk-hosted sign-in UI
├── sign-up/                        ← Clerk-hosted sign-up UI
│
└── (dashboard)/                    ← Route GROUP — no URL segment, just shared layout
    ├── layout.tsx                  ← Dashboard shell: DashboardNav + MobileBottomNav + Toaster + SW registration
    ├── planner/
    │   └── page.tsx                ← Task management (client component, ~15KB)
    ├── knowledge/
    │   ├── page.tsx                ← Thin server shell — renders page.client.tsx
    │   └── page.client.tsx         ← Knowledge base UI (client component, ~11KB)
    ├── library/
    │   ├── page.tsx                ← Collections overview (client component, ~8KB)
    │   └── [collection_id]/        ← Dynamic route: individual collection view
    ├── search/
    │   └── page.tsx                ← Semantic search UI (client component, ~8KB)
    ├── settings/
    │   └── page.tsx                ← User settings: push notification setup (~1KB)
    └── save/
        └── page.tsx                ← Bookmarklet landing page (~6KB)
```

### What the `(dashboard)` Route Group Does

The parentheses make it a **route group** — it doesn't add a URL segment. So `/planner` in the URL actually renders `app/(dashboard)/planner/page.tsx`, wrapped by `app/(dashboard)/layout.tsx`.

This pattern allows the dashboard layout (nav, mobile bar, toaster) to apply to all protected pages **without polluting the URL** with `/dashboard/planner`.

---

## 3. Layout Hierarchy

Every page request passes through two nested layouts:

```
app/layout.tsx (Root)
└── <ClerkProvider>              ← Clerk auth context for entire app
    └── <html>
        └── <body>
            └── app/(dashboard)/layout.tsx (Dashboard Shell)
                ├── <DashboardNav />          ← Sticky top bar (desktop, md+)
                ├── <main>
                │   └── {children}            ← The actual page
                └── <MobileBottomNav />       ← Fixed bottom bar (mobile, hidden md+)
                    <Toaster />               ← Sonner toast notifications
                    [useEffect: registerServiceWorker()]
                    [useEffect: Cmd+K → /search]
```

**Root layout** (`app/layout.tsx`):
- Wraps everything in `<ClerkProvider>` — required for all Clerk hooks to work
- Sets `Inter` font (Google Fonts)
- Sets PWA `manifest.json` reference and theme color
- Minimal — no auth logic here

**Dashboard layout** (`app/(dashboard)/layout.tsx`):
- Handles three cross-cutting concerns:
  1. **Service worker registration** on mount (for PWA push notifications)
  2. **Keyboard shortcut** `Cmd+K` / `Ctrl+K` to navigate to `/search`
  3. **Layout chrome** — `DashboardNav` (top) + `MobileBottomNav` (bottom)
- Auth protection is **not here** — it's in `middleware.ts`

---

## 4. Authentication

### Route Protection — `middleware.ts`

```typescript
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/"])

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect()
  }
})
```

- Runs at **Edge runtime** before any page renders
- Any route not matching `/`, `/sign-in`, or `/sign-up` requires a valid Clerk session
- `auth.protect()` automatically redirects to sign-in if the user is not authenticated
- **No client-side auth guards needed** in layouts or pages

### Root Page Redirect — `app/page.tsx`

```typescript
const { userId } = await auth()
if (userId) redirect("/planner")
else redirect("/sign-in")
```

- Server component — checks auth on the server, redirects immediately
- No flash of content — the redirect happens before HTML is sent

### Token Injection — `hooks/useApi.ts`

```typescript
export function useApi() {
  const { getToken } = useAuth()

  const authenticatedApi = async () => {
    const token = await getToken({ template: "flowdesk" })
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`
    }
    return api
  }

  return { api: authenticatedApi }
}
```

- Called inside client components before any API call
- Gets a fresh Clerk JWT (using the `"flowdesk"` JWT template — matches what the backend expects)
- Injects `Authorization: Bearer <token>` into the shared Axios instance
- **Usage pattern** in components:
  ```typescript
  const { api: getApi } = useApi()
  // ...
  const api = await getApi()
  const data = await getTasks(scope)   // lib/tasks.ts uses the same api instance
  ```

### Auth Utility — `lib/auth.ts`

- `getClerkToken()` — server-side helper for getting the JWT in Server Components or Route Handlers
- Client-side: use `useAuth()` from `@clerk/nextjs` directly in components

---

## 5. API Communication Layer

### Architecture

```
Component / Page
    → useApi() hook  →  getToken() from Clerk
                     →  sets api.defaults.headers["Authorization"]
    → lib/*.ts function  →  axios instance (lib/api.ts)
        → baseURL: NEXT_PUBLIC_API_URL (backend Render URL)
        → Backend responds
    ← data returned to component
    ← setState() / re-render
```

### `lib/api.ts` — Axios Instance

- Single shared Axios instance
- `baseURL` from `NEXT_PUBLIC_API_URL` env var
- **Global 401 interceptor**: if a response is `401` and no Clerk user exists, redirects to Clerk sign-in
- No default auth header — it's injected per-request by `useApi()`

### `lib/` — API Function Modules

Each file encapsulates all API calls for one backend module. They use the shared `api` instance directly (the `useApi` hook sets the header on the instance before these are called).

| File | Backend Module | Functions |
|---|---|---|
| `lib/tasks.ts` | `/tasks` | `getTasks`, `createTask`, `updateTask`, `toggleTask`, `deleteTask` |
| `lib/knowledge.ts` | `/knowledge` | `getKnowledgeItems`, `deleteKnowledgeItem`, `reprocessItems` |
| `lib/library.ts` | `/collections` | `getLibrary`, `getCollections`, `getCollection`, `getCollectionItems`, `updateReadStatus`, `createCollection`, `deleteCollection`, `addItemToCollection` |
| `lib/search.ts` | `/search` | `searchKnowledge`, `reindexItem` |
| `lib/push.ts` | `/notifications` | `registerServiceWorker`, `requestPushPermission`, `subscribeToPush`, `savePushSubscription`, `setupPushNotifications` |

---

## 6. Page-by-Page Summary

### `/planner` — Task Management

**File**: `app/(dashboard)/planner/page.tsx` (client component, ~15KB)

- Displays tasks grouped by scope tabs: Daily / Weekly / Monthly
- Manages its own state with `useState` (task list, active scope, loading)
- Calls `getTasks(scope)` on mount and on scope change
- Has a **History tab** that calls `getTasks(scope, undefined, true)`
- Components used: `AddTaskDialog`, `EditTaskDialog`, `TaskCard`
- Recurring task spawning is triggered transparently by `GET /tasks`

---

### `/knowledge` — Knowledge Base

**Files**: `app/(dashboard)/knowledge/page.tsx` (Server shell) → `page.client.tsx` (Client)

- The `page.tsx` is a thin server wrapper that renders `<KnowledgePageClient />`
- **Split pattern**: Server component sets the page title/metadata; Client component has all the interactive logic
- Displays a grid of `KnowledgeItemCard` components
- Supports filtering by `content_type` via tab bar
- Add dialog: `AddUrlDialog` — supports URL input or PDF file upload
- Calls `getKnowledgeItems(filters)` on mount and filter change
- Uses **AbortSignal** on filter changes to cancel in-flight requests

---

### `/library` — Collections Library

**File**: `app/(dashboard)/library/page.tsx` (client component, ~8KB)
**Dynamic route**: `app/(dashboard)/library/[collection_id]/` — individual collection detail

- Loads the full library overview via `getLibrary()` → `GET /collections/library/overview`
- Shows collections as shelves, each with a preview of items (top 10)
- **Virtual "Priority List"** collection (UUID `00000000-0000-0000-0000-000000000001`) rendered first if present
- Components used: `LibraryItemCard`, `CreateCollectionDialog`
- Individual collection page (`[collection_id]`) loads via `getCollectionItems(id)`

---

### `/search` — Semantic Search

**File**: `app/(dashboard)/search/page.tsx` (client component, ~8KB)

- Search box with debounced input
- On submit: calls `searchKnowledge(query)` → `POST /search`
- Displays AI-synthesised answer + source cards
- Shows `cached: true` badge if the result came from Redis cache
- Shows `took_ms` latency indicator
- Components: `SearchInput`, `SourceCard`
- Uses **AbortSignal** to cancel previous in-flight search if user types again

---

### `/settings` — User Settings

**File**: `app/(dashboard)/settings/page.tsx` (~1KB, client component)

- Minimal page — primarily hosts `PushNotificationSetup` component
- Component: `components/notifications/PushNotificationSetup.tsx`
- Walks the user through: permission request → SW registration → VAPID subscribe → `POST /notifications/subscriptions`

---

### `/save` — Bookmarklet Landing

**File**: `app/(dashboard)/save/page.tsx` (~6KB, client component)

- Entry point for the browser bookmarklet (`BOOKMARKLET.js` in repo root)
- Receives URL params: `url`, `selected_text`, `page_title`, `content_type`
- Two modes:
  1. **Selected text present** → `POST /knowledge/bookmarklet`
  2. **No selection** → `POST /knowledge` (full URL ingestion)
- Shows ingestion status feedback to the user

---

## 7. Component Inventory

```
components/
├── DashboardNav.tsx              ← Top nav bar (sticky, desktop md+), Clerk UserButton
│
├── tasks/
│   ├── TaskCard.tsx              ← Individual task row with checkbox, priority badge, edit/delete
│   ├── AddTaskDialog.tsx         ← Dialog to create a new task (react-hook-form + Zod)
│   └── EditTaskDialog.tsx        ← Dialog to edit existing task
│
├── knowledge/
│   ├── KnowledgeItemCard.tsx     ← Knowledge item card (cover image, type badge, status, read progress)
│   └── AddUrlDialog.tsx          ← Dialog for URL input or PDF upload
│
├── library/
│   ├── LibraryItemCard.tsx       ← Item card in collection shelf view (read status, type icon)
│   └── CreateCollectionDialog.tsx ← Dialog to create new collection (name + color picker)
│
├── search/
│   ├── SearchInput.tsx           ← Search text input with Cmd+K hint
│   └── SourceCard.tsx            ← Renders one source result (title, excerpt, similarity score)
│
├── notifications/
│   └── PushNotificationSetup.tsx ← Full push notification enrollment UI
│
└── ui/                           ← shadcn/ui base components (Button, Dialog, Input, Badge, etc.)
```

---

## 8. State Management

FlowDesk uses **no global state manager** (no Redux, Zustand, React Query, or Context). All state is local to each page:

| Pattern | Usage |
|---|---|
| `useState` | All page-level data (task list, knowledge items, search results, loading/error booleans) |
| `useEffect` | Data fetching on mount, filter changes, keyboard shortcuts, service worker registration |
| `useRouter` / `usePathname` | Navigation and active link highlighting |
| `useApi()` hook | Injects Clerk token into Axios before every API call |
| react-hook-form | Form state in dialogs (Add/Edit Task, Add URL) |

**Refresh pattern**: After a mutation (create/update/delete), the page re-fetches the full list from the backend rather than doing optimistic local state updates. Simple, predictable, no cache invalidation complexity.

---

## 9. Mobile Responsiveness

| Feature | Desktop (`md+`) | Mobile |
|---|---|---|
| Navigation | `DashboardNav` — sticky top bar with links | `MobileBottomNav` — fixed bottom bar with icons |
| DashboardNav | Visible | Hidden (`hidden md:flex`) |
| MobileBottomNav | Hidden (`md:hidden`) | Visible, fixed at bottom |
| Main content padding | `pb-0` | `pb-16` (to clear bottom nav) |
| Nav items | Text + icon | Icon + small label |

---

## 10. PWA Features

| Feature | Implementation |
|---|---|
| App manifest | `public/manifest.json` (referenced in root `layout.tsx`) |
| Service worker | `public/sw.js` — registered via `lib/push.ts → registerServiceWorker()` |
| SW registration | Triggered in `(dashboard)/layout.tsx` `useEffect` on every page load |
| Push notifications | VAPID via `lib/push.ts` — full flow: permission → subscribe → save to backend |
| Theme color | `#0f172a` (dark slate, in `viewport` export of root layout) |
| Home screen icon | Multiple sizes in `public/` generated by `scripts/generate_icons.js` |

---

## 11. Environment Variables (Frontend)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL (Render) — used by Axios instance |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | Browser VAPID key for push subscription |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk public key for frontend SDK |
| `CLERK_SECRET_KEY` | Clerk secret key (server-side only — not `NEXT_PUBLIC_`) |

---

## 12. Next Steps for Exploration

1. ✅ `docs/architecture_overview.md` — High-level tech stack & layout
2. ✅ `docs/data_models.md` — Database tables & relationships
3. ✅ `docs/backend_api_map.md` — All API routes and what they do
4. ✅ `docs/frontend_architecture.md` — **You are here**
5. ⬜ `docs/flow_knowledge_base.md` — Full request lifecycle trace (Knowledge module)
