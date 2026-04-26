# FlowDesk Architecture

This document details the system design and technology choices for FlowDesk.

## 🏗 System Overview

```mermaid
graph TD
    %% Subgraphs / Groupings
    subgraph Client
        Browser["User Browser (Next.js 14 / Vercel)"]
    end

    subgraph AuthLayer [Auth Layer]
        Clerk["Clerk Auth"]
    end

    subgraph AppLayer [Application Layer]
        FastAPI["FastAPI Backend (Render)"]
    end

    subgraph DataLayer [Data Layer]
        Neon["NeonDB (Postgres + pgvector)"]
        Redis["Upstash Redis (Cache)"]
    end

    subgraph ExtServices [External Services]
        Extractors["Content Extractors<br/>(Jina, YouTube, GitHub, pdfplumber)"]
        Gemini["Google Gemini API<br/>(text-embedding-004 & gemini-1.5-flash)"]
        Notifiers["Notification Services<br/>(Resend & Web Push VAPID)"]
    end

    subgraph Scheduling
        Cron["UptimeRobot / GitHub Actions"]
    end

    %% 1. Auth Flow
    Browser -- "1. Login / Authenticate" --> Clerk
    Clerk -- "1. Validate Token / Identity" --> FastAPI

    %% 2. Ingestion Flow (Save URL)
    Browser -- "2. Save URL" --> FastAPI
    FastAPI -- "2. Request Page Content" --> Extractors
    Extractors -- "2. Raw Text / Metadata" --> FastAPI
    FastAPI -- "2. Request Summary" --> Gemini
    Gemini -- "2. 2-Sentence Summary" --> FastAPI
    FastAPI -- "2. Store Item & Summary" --> Neon

    %% 3. Semantic Search Flow
    Browser -- "3. Search Query" --> FastAPI
    FastAPI -- "3. Embed Query" --> Gemini
    Gemini -- "3. Query Vector (list[float])" --> FastAPI
    FastAPI -- "3. Cosine Similarity Search" --> Neon
    Neon -- "3. Relevant Chunks" --> FastAPI
    FastAPI -- "3. Synthesise Answer" --> Gemini
    Gemini -- "3. Final Answer String" --> FastAPI
    FastAPI -- "3. Return Search Results" --> Browser

    %% 4. Digest Flow
    Cron -- "4. Trigger Morning Digest" --> FastAPI
    FastAPI -- "4. Fetch Tasks & Unread Items" --> Neon
    Neon -- "4. Query Results" --> FastAPI
    FastAPI -- "4. Dispatch Email & Push" --> Notifiers
    Notifiers -- "4. Deliver Notification" --> Browser

    %% 5. Caching Flow
    FastAPI <--> |"5. Check/Set Search Cache"| Redis

    %% Styling 
    classDef primary fill:#f8fafc,stroke:#94a3b8,stroke-width:2px,color:#0f172a;
    classDef highlight fill:#e2e8f0,stroke:#64748b,stroke-width:2px,color:#0f172a;
    class Browser,Clerk,FastAPI,Neon,Redis,Extractors,Gemini,Notifiers,Cron primary;
    class AppLayer highlight;
```

## 🛠 Design Rationale

| Component | Choice | Why? |
| :--- | :--- | :--- |
| **Database** | **NeonDB + pgvector** | avoids separate vector DB, joins between relational and vector data are trivial SQL, free tier includes pgvector |
| **API Framework** | **FastAPI over Spring Boot** | native Python AI ecosystem integration, async-first, 10x less boilerplate for this type of API |
| **Web Ingestion** | **Jina AI Reader over Playwright** | zero memory overhead on Render's 512MB dyno, handles JS rendering server-side, no maintenance |
| **Job Scheduling** | **UptimeRobot over APScheduler** | decoupled from Render's sleep cycle, stateless backend (important for free tier reliability) |
| **Email Service** | **Resend over SendGrid** | 100 emails/day free with a modern API, better developer experience |
| **Cache Store** | **Upstash Redis over Redis Cloud** | serverless REST API fits perfectly in Render's stateless dyno model |
