# Compounding Engineering: Troubleshooting Methodology

## Core Principle
**"Debug with instrumentation, not intuition."**

Every bug teaches us a pattern. Capture that pattern so it becomes automatic.

---

## The Systematic Debugging Loop

```
1. Observe the symptom (error message, unexpected behavior)
   ↓
2. Add instrumentation at the failure point
   ↓
3. Reproduce and read the EXACT error
   ↓
4. Check pattern library (this file + docs/ops/)
   ↓
5. Apply fix
   ↓
6. Document the pattern if new
```

---

## Pattern Library

### Authentication (401/403)
**File:** `docs/ops/AUTH_TROUBLESHOOTING.md`
**Key Lesson:** Always add debug logging to see exact JWT error before guessing
**Common Fix:** JWT audience mismatch, wrong secret, missing auth header

### Database (Foreign Key Violations)
**Pattern:** "violates foreign key constraint"
**Debug Step:** Check if parent record exists
**Example:** User record must exist before creating conversation
**Fix:** Ensure `/auth/sync-user` creates user before other endpoints run

### CORS Errors
**Pattern:** "blocked by CORS policy"
**Debug Step:** Check `main.py` CORS middleware
**Fix:** Add origin to `allow_origins` list

### Schema Mismatches (owner_id vs tenant_id)
**Pattern:** Query returns empty when data exists
**Debug Step:** Check column names in query vs schema
**Fix:** Use `tenant_id` for ownership in twins table (documented in LEARNINGS_LOG)

---

## Pre-Implementation Checklist

Before saying "implementation complete":

### 1. Local Testing (MANDATORY)
- [ ] Code works in local environment BEFORE deployment
- [ ] All user flows tested (login → create → use feature)
- [ ] Browser console: No red errors
- [ ] Backend terminal: No 400/500 errors
- [ ] Database: Records created as expected

### 2. Documentation
- [ ] Update relevant workflow if new pattern discovered
- [ ] Add to troubleshooting guide if auth-related
- [ ] Update LEARNINGS_LOG if schema quirk found

### 3. Verification Script
- [ ] Use `.agent/workflows/auth-verification.md` for auth changes
- [ ] Use `./scripts/preflight.ps1` before EVERY push

---

## When To Add Debug Logging

**Always add debug logging for:**
- Authentication/authorization code
- Database queries (especially inserts)
- External API calls
- Anything that fails silently

**Debug Logging Template:**
```python
print(f"[COMPONENT DEBUG] Variable: {value}")
print(f"[COMPONENT DEBUG] About to do X...")
try:
    result = do_thing()
    print(f"[COMPONENT DEBUG] Success: {result}")
except Exception as e:
    print(f"[COMPONENT DEBUG] ERROR: {str(e)}")
    raise
```

---

## Learning From Failures

### This Session's Lessons:

1. **JWT Audience Issue**
   - Symptom: 401 Unauthorized
   - Root Cause: Supabase JWTs have `aud="authenticated"` 
   - Fix: Add `audience="authenticated"` to jwt.decode()
   - Prevention: Check Supabase JWT structure before implementing auth
   - **File:** `docs/ops/AUTH_TROUBLESHOOTING.md` (now contains this)

2. **Schema Mismatches**
   - Symptom: Empty query results despite data existing
   - Root Cause: Using `owner_id` when schema has `tenant_id`
   - Fix: Grep for column names, update queries
   - Prevention: Check actual schema, don't assume column names
   - **File:** `docs/ops/LEARNINGS_LOG.md` (documents schema patterns)

3. **Local Testing Gap**
   - Symptom: Issues only found after deployment
   - Root Cause: Skipped local testing verification
   - Fix: Created `scripts/dev.ps1` and auth verification workflow
   - Prevention: NEVER deploy without local testing
   - **File:** `.agent/workflows/auth-verification.md` (new)

---

## Workflows Created From This Experience

1. **`scripts/dev.ps1`**: Start local dev environment
2. **`.agent/workflows/auth-verification.md`**: Pre-deployment auth checklist
3. **`docs/ops/AUTH_TROUBLESHOOTING.md`**: Auth debugging guide  
4. **`backend/test_jwt.py`**: JWT validation test script

---

## Future Process

### Before Implementing Any Auth Change:
```
1. Review docs/ops/AUTH_TROUBLESHOOTING.md
2. Add debug logging from the start
3. Test locally with scripts/dev.ps1
4. Run .agent/workflows/auth-verification.md checklist
5. Only then: deploy
```

### After Finding Any Bug:
```
1. Document the pattern in relevant guide
2. Update troubleshooting workflow if needed
3. Create test/verification script if pattern recurs
4. Commit as "Learn: [pattern description]"
```

---

## Command for Future Self

**When implementing authentication features:**
```powershell
# 1. Start with local dev
./scripts/dev.ps1

# 2. Before claiming done, run verification
# Read and test: .agent/workflows/auth-verification.md

# 3. If any auth issues, consult
# Read: docs/ops/AUTH_TROUBLESHOOTING.md

# 4. Only after ALL local tests pass
./scripts/preflight.ps1
git push
```

**Golden Rule:** If it doesn't work locally, it won't work in production.
