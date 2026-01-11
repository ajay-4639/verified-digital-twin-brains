# Process Queue Troubleshooting Guide

## Common Failure Scenarios

### 1. Authentication Error (401)

**Symptoms:**
- Button click shows "Failed to process queue"
- Browser console shows 401 Unauthorized
- Error message: "Not authenticated"

**Causes:**
- Auth token expired
- Missing Authorization header
- Invalid Supabase session

**Fix:**
- Refresh the page to get a new auth token
- Check browser DevTools → Application → Local Storage → `sb-*-auth-token`
- Verify you're logged in

### 2. Access Denied (403)

**Symptoms:**
- Error: "Not authorized to perform this action"
- Status code: 403

**Causes:**
- User doesn't own the twin
- `verify_owner` dependency failing

**Fix:**
- Verify you're the owner of the twin
- Check `twins` table: `tenant_id` should match your user's `tenant_id`

### 3. Missing twin_id (400)

**Symptoms:**
- Error: "twin_id query parameter is required"
- Status code: 400

**Causes:**
- Frontend not passing `twin_id` in query string
- `activeTwin` is null/undefined

**Fix:**
- Check `useTwin()` hook returns valid `activeTwin`
- Verify twin is selected/loaded before clicking button

### 4. No Jobs Found

**Symptoms:**
- Success response but `processed: 0`
- Message: "Processed 0 job(s)"

**Causes:**
- No queued jobs in database
- Jobs already processed
- Queue is empty

**Fix:**
- Check if source is already "Live" (already processed)
- Verify training job exists: `GET /training-jobs?twin_id=XXX&status=queued`
- Approve a source to create a new job

### 5. Job Processing Failed

**Symptoms:**
- `processed: 0, failed: 1`
- Error details in `errors` array
- Source stays "Approved"

**Common Causes:**

**a) Missing source text:**
```
Error: Source has no extracted text content
```
**Fix:** Re-upload the source

**b) OpenAI API error:**
```
Error: OpenAI API error: ...
```
**Fix:** 
- Check `OPENAI_API_KEY` is set
- Verify API key is valid
- Check OpenAI account has credits

**c) Pinecone error:**
```
Error: Pinecone error: ...
```
**Fix:**
- Check `PINECONE_API_KEY` is set
- Verify `PINECONE_INDEX_NAME` is correct
- Check Pinecone index exists

**d) Database error:**
```
Error: Database error: ...
```
**Fix:**
- Check Supabase connection
- Verify `SUPABASE_SERVICE_KEY` is set
- Check database logs

### 6. Timeout Error

**Symptoms:**
- Request hangs for >30 seconds
- Browser shows timeout
- No response

**Causes:**
- Job processing takes too long
- Network timeout
- Backend is slow/unresponsive

**Fix:**
- Check backend logs for processing status
- Verify backend is running
- Try processing fewer jobs at once

### 7. Network Error

**Symptoms:**
- "Connection error while processing queue"
- No response from server
- CORS error in console

**Causes:**
- Backend is down
- Wrong backend URL
- CORS misconfiguration

**Fix:**
- Check backend is running (Render dashboard)
- Verify `NEXT_PUBLIC_BACKEND_URL` is correct
- Check CORS settings in `backend/main.py`

## Diagnostic Steps

### Step 1: Check Browser Console

1. Open DevTools (F12)
2. Go to Console tab
3. Click "Process Queue" button
4. Look for errors

**Common errors:**
- `Failed to fetch` → Backend is down or CORS issue
- `401 Unauthorized` → Auth token expired
- `403 Forbidden` → Access denied
- `400 Bad Request` → Missing/invalid parameters

### Step 2: Check Network Tab

1. Open DevTools → Network tab
2. Click "Process Queue" button
3. Find POST request to `/training-jobs/process-queue`
4. Check:
   - **Status Code**: Should be 200 for success
   - **Request URL**: Should include `?twin_id=XXX`
   - **Request Headers**: Should have `Authorization: Bearer ...`
   - **Response**: Check JSON response for error details

### Step 3: Check Backend Logs

1. Go to Render Dashboard
2. Select your backend service
3. Go to Logs tab
4. Look for `[Process Queue]` messages
5. Check for error stack traces

**Look for:**
- `[Process Queue] Processing job XXX`
- `[Process Queue] Error processing job XXX: ...`
- Stack traces showing where it failed

### Step 4: Verify Job Exists

**Via API:**
```bash
GET /training-jobs?twin_id=YOUR_TWIN_ID&status=queued
```

**Expected:**
```json
[
  {
    "id": "...",
    "source_id": "...",
    "status": "queued",
    "job_type": "ingestion"
  }
]
```

**If empty:**
- No jobs to process
- Source might already be processed
- Check source status: `GET /sources/YOUR_TWIN_ID`

### Step 5: Test Source Has Content

**Check source:**
```bash
GET /sources/YOUR_TWIN_ID
```

**Look for source with:**
- `staging_status: "approved"`
- `content_text: "..."` (should have text)
- `chunk_count: null` or `0` (not yet indexed)

**If `content_text` is empty:**
- Source extraction failed
- Re-upload the source

## Quick Fixes

### Fix 1: Refresh and Retry
1. Hard refresh browser (Ctrl+F5)
2. Re-login if needed
3. Try Process Queue again

### Fix 2: Check Backend Health
```bash
GET /health
```
Should return: `{"status": "healthy"}`

### Fix 3: Verify Environment Variables
Check Render dashboard → Environment:
- `OPENAI_API_KEY` ✓
- `PINECONE_API_KEY` ✓
- `PINECONE_INDEX_NAME` ✓
- `SUPABASE_SERVICE_KEY` ✓

### Fix 4: Re-approve Source
If job failed:
1. Go to staging page
2. Find the failed source
3. Reject it
4. Re-approve it (creates new job)
5. Process queue again

## Getting Help

When reporting issues, include:

1. **Error Message**: Exact error text from UI
2. **Browser Console**: Any errors in console
3. **Network Response**: Response from `/training-jobs/process-queue`
4. **Backend Logs**: Relevant log lines from Render
5. **Source Status**: Source `staging_status` and `chunk_count`
6. **Job Status**: Training job `status` and `error_message`

## Example Debugging Session

```bash
# 1. Check if backend is up
curl https://your-backend-url/health

# 2. Check if jobs exist
curl -H "Authorization: Bearer TOKEN" \
  "https://your-backend-url/training-jobs?twin_id=XXX&status=queued"

# 3. Check source status
curl -H "Authorization: Bearer TOKEN" \
  "https://your-backend-url/sources/XXX"

# 4. Try processing manually
curl -X POST \
  -H "Authorization: Bearer TOKEN" \
  "https://your-backend-url/training-jobs/process-queue?twin_id=XXX"
```

