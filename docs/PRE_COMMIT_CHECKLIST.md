# Pre-Commit Verification Checklist

**🚨 MUST RUN BEFORE EVERY PUSH TO MAIN**

## Quick Start

```bash
# Run all checks at once
./scripts/validate_before_commit.sh

# Or run individually:
cd backend && python -m flake8 . --count --select=E9,F63,F7,F82 --statistics
cd backend && python -m pytest -v --tb=short -m "not network"
cd frontend && npm run lint
```

---

## Pre-Commit Verification Checklist

### Backend Checks ✅

- [ ] **Syntax Errors** (CRITICAL)
  ```bash
  cd backend
  python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
  # Must return: 0
  ```

- [ ] **Lint Warnings** (CODE QUALITY)
  ```bash
  cd backend
  python -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
  # Review output for warnings
  ```

- [ ] **Tests Pass** (FUNCTIONALITY)
  ```bash
  cd backend
  python -m pytest -v --tb=short -m "not network"
  # Must show: passed
  ```

### Frontend Checks ✅

- [ ] **Lint Pass** (CRITICAL)
  ```bash
  cd frontend
  npm run lint
  # Must pass without errors
  ```

- [ ] **Build Succeeds** (CRITICAL)
  ```bash
  cd frontend
  npm run build
  # Must complete successfully
  ```

- [ ] **Type Check Pass** (OPTIONAL but recommended)
  ```bash
  cd frontend
  npm run typecheck
  ```

### Git Checks ✅

- [ ] **Files Tracked**
  ```bash
  git status
  # Verify important files are not in .gitignore or untracked
  git ls-files backend/modules/ingestion.py
  ```

- [ ] **No Secrets in Commit**
  ```bash
  git diff HEAD~1 HEAD | grep -i "key\|secret\|token\|password"
  # Should return nothing
  ```

---

## Common Issues & Fixes

### ❌ "Backend tests failed"
1. Check error message
2. Run single failing test: `pytest tests/test_name.py -v`
3. Check .env variables are set correctly
4. Check database connectivity (Supabase mock in CI)

### ❌ "Frontend lint errors"
1. Run: `npm run lint -- --fix` (auto-fix where possible)
2. Check import statements (all React hooks imported)
3. Check for unused variables/imports

### ❌ "Syntax error: E9xx"
1. Search for the error in the file
2. Fix immediately - this blocks deployment
3. Re-run flake8 to verify fix

### ❌ "HTTP 403 / YouTube blocked"
1. Use videos with public captions (look for "CC" badge)
2. Ensure YOUTUBE_COOKIES_BROWSER is set in Render
3. Optionally set YOUTUBE_PROXY for IP-based blocks

---

## What Happens Without Checking

| Check Skipped | Result | Impact |
|---|---|---|
| Syntax | ❌ Build fails in CI | 30 min wasted diagnosing |
| Tests | ❌ Runtime errors in prod | Data corruption or crashes |
| Lint | ⚠️ Tech debt accumulates | Harder to debug later |
| Frontend build | ❌ Vercel deployment fails | Site goes down |
| Git secrets | 🚨 Security breach | Credentials leaked |

---

## Automation (CI/CD)

These checks run automatically on every push to `main`:

- ✅ **GitHub Actions** (`.github/workflows/lint.yml`)
  - Backend: flake8 + pytest
  - Frontend: npm lint + npm build
  - Runs on every push and PR

- ✅ **Vercel** (auto-deployment on main)
  - Frontend build check before deploying
  - Can rollback if fails

- ✅ **Render** (auto-deployment on main)
  - Backend build check before deploying
  - Can restart if needed

---

## Process for Next Time

**Before committing:**
```bash
# 1. Make changes
nano backend/modules/ingestion.py

# 2. Run validation
./scripts/validate_before_commit.sh

# 3. If errors, fix them
# ... make fixes ...
# ... re-run validation ...

# 4. Once all green
git add -A
git commit -m "fix: descriptive message"
git push origin main
```

**That's it!** CI will handle the rest.

---

## Questions?

- Check GitHub Actions logs: https://github.com/snsettitech/verified-digital-twin-brains/actions
- Check Render logs: https://dashboard.render.com/
- Check Vercel logs: https://vercel.com/dashboard
