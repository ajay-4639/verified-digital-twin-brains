# Backend Authentication Troubleshooting Guide

## When You See: 401 Unauthorized

### Systematic Debugging Process

#### 1. Add Debug Instrumentation FIRST
Before guessing, add logging to see the EXACT failure point:

```python
# In auth_guard.py or similar
print(f"[AUTH DEBUG] Token length: {len(token)}")
print(f"[AUTH DEBUG] Secret length: {len(JWT_SECRET)}")
print(f"[AUTH DEBUG] Secret first 10 chars: {JWT_SECRET[:10]}...")

try:
    payload = jwt.decode(...)
except JWTError as e:
    print(f"[AUTH DEBUG] ERROR: {str(e)}")  # This is KEY
    raise
```

**Why**: The error message tells you EXACTLY what's wrong (e.g., "Invalid audience", "Signature verification failed", "Token expired")

---

#### 2. Common JWT Issues & Solutions

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Invalid audience` | JWT has `aud` claim but decoder doesn't expect it | Add `audience="authenticated"` to `jwt.decode()` |
| `Signature verification failed` | Wrong JWT_SECRET | Get correct secret from Supabase Dashboard → Settings → API |
| `Token has expired` | Token is old | User needs to log out and back in |
| `Invalid token format` | Missing "Bearer " prefix | Check authorization header format |

---

#### 3. Verification Checklist

Before claiming auth is working, test these flows locally:

- [ ] `/auth/sync-user` returns 200 (creates user record)
- [ ] `/auth/my-twins` returns 200 (fetches twins)
- [ ] POST /twins returns 200 (can create twin)
- [ ] Refresh browser, auth persists

---

#### 4. JWT Secret Configuration

**For Supabase:**
- Use the **"JWT Secret"** (or "Legacy JWT Secret"), NOT "JWT Signing Keys"
- Algorithm is HS256 (symmetric)
- Audience is `"authenticated"` for user tokens

---

## When You See: 403 Forbidden

### Common Causes:
1. **Twin ownership check failed**: User doesn't own the twin they're trying to access
2. **RLS policies**: Row-level security blocking the query
3. **Missing auth header**: Request doesn't have `Authorization: Bearer <token>`

### Debug Steps:
```python
# In verify_twin_access or similar
print(f"[ACCESS DEBUG] User ID: {user.get('user_id')}")
print(f"[ACCESS DEBUG] Twin ID: {twin_id}")
print(f"[ACCESS DEBUG] Checking ownership...")
```

---

## When You See: CORS Errors

### Quick Fix:
Check `main.py` has `http://localhost:3000` in `allow_origins`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", ...],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## General Debugging Workflow

```
1. Read the error message (don't skip this!)
   ↓
2. Add debug logging at the failure point
   ↓
3. Reproduce the error and read the debug output
   ↓
4. Check this guide for common patterns
   ↓
5. Apply fix
   ↓
6. Remove debug logging (or keep for production monitoring)
```

---

## Testing Authentication Locally

### Script to test JWT decode:
```bash
cd backend
python test_jwt.py
# Paste a token from browser DevTools
```

### Get a token from browser:
1. F12 → Application → Local Storage
2. Find `sb-*-auth-token` key
3. Copy the `access_token` value

---

## Common Mistakes to Avoid

❌ **Don't assume JWT_SECRET is correct** - Always verify it matches Supabase  
❌ **Don't skip debug logging** - Guessing wastes time  
❌ **Don't test only in production** - Test auth locally first  
❌ **Don't ignore CORS errors** - They block requests before auth even runs
