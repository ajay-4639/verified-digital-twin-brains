# Phase 4: Verified-First Knowledge Layer - Next Steps

## ✅ Implementation Complete

All code for Phase 4 has been implemented. Here's what to do next:

## Step 1: Apply Database Migration

**If you already have existing tables** (tenants, twins, users, etc.):
1. **Open Supabase Dashboard** → SQL Editor
2. **Copy and paste** the contents of `migration_phase4_verified_qna.sql`
3. **Run the migration** - This will create only the new Phase 4 tables:
   - `verified_qna`
   - `answer_patches`
   - `citations`

**If starting fresh**:
1. Use `supabase_schema.sql` for the complete schema

**Note**: The migration script uses `CREATE TABLE IF NOT EXISTS` so it's safe to run multiple times.

## Step 2: Verify Backend Environment

Make sure your `.env` file in the `backend/` directory has:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key
# OR
SUPABASE_SERVICE_KEY=your-service-role-key

OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...
```

## Step 3: Test the Backend

1. **Start the backend server**:
   ```bash
   cd backend
   python main.py
   ```

2. **Test the health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

   Should return: `{"status": "online", ...}`

3. **Verify Supabase connection** (optional):
   ```bash
   cd backend
   python -c "from modules.observability import supabase; print('Connected!')"
   ```

## Step 4: Run Migration Script (Optional)

If you have existing verified vectors in Pinecone that you want to migrate to the new `verified_qna` table:

```bash
cd backend
python scripts/migrate_verified_to_qna.py
```

Or for a specific twin:
```bash
python scripts/migrate_verified_to_qna.py <twin_id>
```

## Step 5: Test the Full Flow

### Test Escalation Resolution → Verified QnA Creation

1. **Create a low-confidence interaction** (or use existing escalation)
2. **Resolve the escalation** via `/escalations/{id}/resolve` endpoint or UI
3. **Verify the verified QnA was created**:
   ```bash
   curl http://localhost:8000/twins/{twin_id}/verified-qna \
     -H "Authorization: Bearer development_token"
   ```

### Test Verified-First Retrieval

1. **Ask a question** that matches a verified QnA entry
2. **Verify the response uses the verified answer** (should have `verified_qna_match: true`)
3. **Check confidence score** (should be 1.0 for verified answers)

## Step 6: Start Frontend (if using UI)

```bash
cd frontend
npm run dev
```

Then navigate to:
- **Escalations**: http://localhost:3000/dashboard/escalations
- **Verified QnA Management**: http://localhost:3000/dashboard/verified-qna

## Step 7: Verify Success Criteria

✅ **A question corrected once never regresses** - Test by:
   - Resolving an escalation with a specific answer
   - Asking the same question again
   - Verifying it returns the verified answer

✅ **Verified answers can be served with minimal citations UI noise** - Check that verified QnA responses include citations properly formatted

## Troubleshooting

### Error: "Failed to fetch (api.supabase.com)"

This usually means:
1. **Backend can't connect to Supabase** - Check environment variables
2. **Network/CORS issue** - Verify SUPABASE_URL is correct format
3. **Supabase project paused** - Check Supabase dashboard

### Error: "relation verified_qna does not exist"

The database migration hasn't been run yet. Go to Step 1.

### Error: "SUPABASE_URL environment variable is not set"

Check your `.env` file in the `backend/` directory.

## Next Phase

Once Phase 4 is tested and working, you can proceed to the next phase in your roadmap!
