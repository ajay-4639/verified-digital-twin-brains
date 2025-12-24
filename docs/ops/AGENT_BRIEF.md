# Agent Brief: verified-digital-twin-brain

> How an agent must operate in THIS repository.

## Repo Map

```
verified-digital-twin-brain/
├── frontend/                 # Next.js 16, TypeScript, Tailwind
│   ├── app/                  # App Router pages (31+ pages)
│   ├── components/           # React components
│   ├── lib/                  # Context, Supabase, Feature Flags
│   ├── .nvmrc                # Node 20 pinned
│   └── vercel.json           # Vercel config
│
├── backend/                  # FastAPI, Python 3.12, LangGraph
│   ├── routers/              # 14+ API route files
│   ├── modules/              # 50+ business logic files
│   ├── database/             # Supabase integration
│   ├── migrations/           # SQL migrations
│   └── tests/                # Pytest tests
│
├── .github/workflows/        # CI: lint.yml
├── scripts/                  # Preflight scripts
├── docs/                     # Documentation
│   └── ops/                  # Operational docs (this folder)
└── render.yaml               # Render backend config
```

---

## Conventions

### Frontend
- Use App Router pattern (`app/` directory)
- Import paths use `@/` alias (e.g., `@/lib/supabase/client`)
- Components in `components/`, contexts in `lib/context/`
- Auth via Supabase + `getSupabaseClient()`

### Backend
- Routers in `routers/`, business logic in `modules/`
- Auth guard: `from modules.auth_guard import get_current_user, verify_owner`
- Supabase client: `from modules.observability import supabase`
- Migrations: Plain SQL files in `backend/migrations/`

---

## How to Add New Features Safely

### Adding a New Backend Router
1. Create `backend/routers/my_feature.py`
2. Follow pattern from existing routers (auth, chat, etc.)
3. Add to `backend/main.py`: `from routers import my_feature` + `app.include_router(my_feature.router)`
4. Run preflight before push

### Adding a New Frontend Page
1. Create `frontend/app/dashboard/my-feature/page.tsx`
2. Add `'use client';` directive at top
3. Import hooks: `import { useState, useEffect, useCallback } from 'react';`
4. Use existing UI patterns from similar pages
5. Run preflight before push

### Adding a Database Migration
1. Create `backend/migrations/my_migration.sql`
2. Use `CREATE TABLE IF NOT EXISTS` pattern
3. Include RLS policies
4. Apply manually in Supabase SQL Editor
5. Document in RUNBOOKS.md

---

## Preflight Command (ALWAYS run before push)

```powershell
# Windows
./scripts/preflight.ps1

# Linux/Mac
./scripts/preflight.sh
```

This runs:
- Frontend: `npm ci` → `npm run lint` → `npm run build`
- Backend: `pip install` → `flake8` → `pytest`

---

## Common Failure Modes and Fixes

| Error | Root Cause | Fix |
|-------|------------|-----|
| `Module not found: @/lib/...` | `.gitignore` too broad (e.g., `lib/`) | Change to specific path like `backend/lib/` |
| `Cannot find name 'useCallback'` | Missing React import | Add to import: `import { useState, useEffect, useCallback } from 'react';` |
| Files exist locally but not on Vercel | Files not tracked by Git | Run `git ls-files <path>` to verify, then `git add -f <path>` |
| Works locally, fails in CI | Case sensitivity (Windows vs Linux) | Use `git mv` to fix casing: `git mv Folder __tmp__ && git mv __tmp__ folder` |
| `tsconfig.json` parse error | Invalid JSON syntax | Check for unclosed brackets, trailing commas |

---

## Do / Don't List

### DO ✅
- Run `./scripts/preflight.ps1` before EVERY push
- Check `git ls-files` to verify new files are tracked
- Use existing auth patterns (`get_current_user`)
- Follow existing migration patterns (RLS, indexes)
- Add ALL React hooks to import statement upfront
- Fix ALL errors in one commit, not one at a time

### DON'T ❌
- Push without running local build
- Add broad patterns to `.gitignore` (like `lib/`)
- Break existing routers/endpoints
- Leave TODOs that break builds
- Assume Windows casing works on Linux
- Use deprecated packages without migration plan
