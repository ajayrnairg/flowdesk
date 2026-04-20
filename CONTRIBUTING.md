# FlowDesk Development Workflow

## 1. Feature Branches
Never work directly on `master`. Create a feature branch for all new work:
```bash
git checkout -b feature/your-feature-name
```

## 2. Local Environment
- **Backend**: `localhost:8000` (FastAPI)
- **Frontend**: `localhost:3000` (Next.js)

## 3. Pre-Push Checklist
Verify everything is stable before pushing to GitHub:
- **Backend**: Run tests
  ```bash
  cd backend
  pytest
  ```
- **Frontend**: Run build (catches TypeScript/Linting errors)
  ```bash
  cd frontend
  npm run build
  ```

## 4. Pull Requests
1. Push your branch to GitHub.
2. Open a Pull Request (PR) against `master`.
3. Review and merge.

## 5. Deployment
Merging to `master` triggers automated deployments:
- **Frontend**: Auto-deploys to Vercel.
- **Backend**: Auto-deploys to Render (ensure **Auto-Deploy** is enabled in Render settings).

## 6. Post-Merge Migrations
If the merge includes new database migrations, manually run the production migration command **immediately** to avoid backend crashes:
```powershell
$env:DATABASE_URL="your_prod_url"; .\venv\Scripts\python.exe -m alembic upgrade head
```
