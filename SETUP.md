# FlowDesk Setup & Commands

## 🚀 How to Start

### 1. Backend (FastAPI)
```powershell
# Navigate to backend directory
cd backend

# Activate virtual environment
.\venv\Scripts\activate

# Start the dev server with hot reload
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

### 2. Frontend (Next.js 14)
```powershell
# Navigate to frontend directory
cd frontend

# Start the dev server
npm run dev
```

---

## 🗄️ Database Migrations (Alembic)

All alembic commands should be run from the `backend/` directory with the `venv` activated.

```powershell
# 1. Create a new migration automatically (detects model changes)
alembic revision --autogenerate -m "description_of_changes"

# 2. Apply all pending migrations to the database
alembic upgrade head

# 3. Revert the last migration (use with caution)
alembic downgrade -1

# 4. View migration history
alembic history --verbose
```

---

## 🚀 Deployment Optimization

To ensure that backend changes don't trigger frontend builds (and vice versa), configure your deployment platforms as follows:

### 1. Vercel (Frontend)
1. Go to **Settings > Git**.
2. Find the **Ignored Build Step** section.
3. Select **Command** and enter:
   ```bash
   git diff --quiet HEAD^ HEAD -- .
   ```
   *(Note: This assumes your **Root Directory** in Vercel is set to `frontend`. If it is NOT set, use `git diff --quiet HEAD^ HEAD -- frontend` instead.)*
   
   *This tells Vercel: "If there are no changes in this folder since the last commit, skip this build."*

### 2. Render (Backend)
1. Go to your Web Service **Settings**.
2. Scroll to **Build & Deploy**.
3. Find **Build Filter**.
4. Set it to only include the `backend/` directory.
   *This ensures Render only restarts your API when backend code is updated.*

---

## 🔖 Bookmarklet
The latest bookmarklet code is stored in `BOOKMARKLET.js`. 
To use it:
1. Create a new bookmark in your browser.
2. Name it "FlowDesk Save".
3. Paste the minified code from `BOOKMARKLET.js` into the URL field.
