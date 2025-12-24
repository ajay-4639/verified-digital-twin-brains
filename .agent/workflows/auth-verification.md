---
description: Pre-deployment verification checklist for authentication changes
---

# Authentication Pre-Deployment Checklist

## Before Pushing Auth Changes

// turbo-all

### 1. Local Environment Setup
```powershell
# Verify .env files are correct
cat backend/.env | Select-String "JWT_SECRET"  # Should be 88+ chars
cat frontend/.env.local | Select-String "BACKEND_URL"  # Should be localhost:8000
```

### 2. Start Local Services
```powershell
# Terminal 1: Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend  
cd frontend
npm run dev
```

### 3. Test Authentication Flow

#### Step 1: Initial Page Load
```
Navigate to: http://localhost:3000/dashboard/right-brain
Expected: Redirects to login (if not logged in)
```

#### Step 2: After Login
```
Check browser console: NO 401 errors
Check backend terminal: 
  ✓ POST /auth/sync-user HTTP/1.1" 200 OK
  ✓ GET /auth/my-twins HTTP/1.1" 200 OK
```

#### Step 3: Create Twin
```
Click "Start Interview Now"
Expected: Twin created successfully
Backend shows: POST /twins HTTP/1.1" 200 OK
```

#### Step 4: Use Interview
```
Type "hello" in interview
Expected: Host responds (no 500 errors)
Backend shows: POST /cognitive/interview/{id} HTTP/1.1" 200 OK
```

### 4. Check for Common Issues

Run this in backend terminal window - if you see these, auth is BROKEN:

```
❌ "Invalid audience"         → Fix: Add audience="authenticated" to jwt.decode()
❌ "Signature verification"   → Fix: Check JWT_SECRET matches Supabase
❌ "401 Unauthorized"          → Fix: Review auth_guard.py logic  
❌ "CORS policy"               → Fix: Check CORS middleware allows localhost:3000
```

### 5. Verify User Creation

After first login, check database:
```sql
-- Run in Supabase SQL Editor
SELECT id, email, full_name FROM users WHERE email = 'your-test-email@example.com';
-- Should return 1 row
```

### 6. Clean Up Debug Logging

Before pushing:
```powershell
# Remove [JWT DEBUG] and [AUTH DEBUG] print statements
# Or comment them out for future debugging
```

---

## Quick Auth Test Script

Create `backend/test_auth_flow.py`:
```python
"""Quick test to verify JWT decode works"""
import os
from dotenv import load_dotenv
from jose import jwt

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"

# Sample token structure (get real one from browser)
print(f"JWT_SECRET length: {len(JWT_SECRET)}")
print(f"First 10 chars: {JWT_SECRET[:10]}...")

# Test decode with audience
try:
    # You'll need to paste a real token here
    sample_token = input("Paste token from browser (or Enter to skip): ")
    if sample_token:
        payload = jwt.decode(
            sample_token,
            JWT_SECRET,
            algorithms=[ALGORITHM],
            audience="authenticated"
        )
        print("✅ JWT decode successful!")
        print(f"User ID: {payload.get('sub')}")
except Exception as e:
    print(f"❌ Error: {e}")
```

Run: `python backend/test_auth_flow.py`

---

## When Everything Works

You should see this flow with NO errors:

```
Browser Console:
  - No red errors
  - TwinContext loads twins successfully

Backend Terminal:
  [JWT DEBUG] Token length: 1318
  [JWT DEBUG] Secret length: 88
  [JWT DEBUG] Secret first 10: yNHpVZTDOX...
  ✓ 200 OK on all auth endpoints

Database:
  - User record exists
  - Twin record exists
  - Can start interview
```

---

## Then Deploy

```powershell
# Switch to production mode
./scripts/dev-deploy.md  # Follow "Switch to Production & Deploy"

# Or manually:
# 1. Update frontend/.env.local to production URL
# 2. Run preflight
# 3. git add, commit, push
```
