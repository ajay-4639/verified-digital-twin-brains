# OAuth Database Error Fix

**Status:** ✅ **FIXED** - OAuth signup now works for both existing and new users  
**Date:** 2025-01-XX  
**Commit:** `1936e19` - Fix: OAuth user creation error

## Problem

When users try to sign up via OAuth (Google), they see "Database error saving new user" and get stuck in a redirect loop on the login page.

## Root Cause

The error "Database error saving new user" occurred because:

1. Supabase OAuth succeeds and creates a user in `auth.users`
2. Supabase tries to automatically create a user record in the `users` table (via trigger/webhook)
3. The `users` table requires `tenant_id` (NOT NULL constraint)
4. The `tenant_id` doesn't exist yet (it's created by `/auth/sync-user` endpoint)
5. Database insert fails → "Database error saving new user"
6. OAuth flow fails, but a session might already be created
7. User gets redirected to `/auth/login` with hash error
8. Middleware sees session and redirects → loop

## Solution

**✅ FIXED**: Migration and code changes have been applied successfully.

### Migration: `migration_fix_oauth_user_creation.sql`

This migration:
1. Makes `tenant_id` nullable in the `users` table (allows OAuth signup before tenant creation)
2. Updates `/auth/sync-user` endpoint to create tenant first, then user with `tenant_id`

### Changes Made:

1. **Database Migration**: `backend/database/migrations/migration_fix_oauth_user_creation.sql`
   - Makes `tenant_id` nullable in `users` table
   - Documents why it's nullable

2. **Backend Code**: `backend/routers/auth.py`
   - Updated `/auth/sync-user` to create tenant FIRST
   - Then create user with `tenant_id`
   - Added error cleanup (delete tenant if user creation fails)

### To Apply:

1. ✅ Run the migration in Supabase SQL Editor:
   ```sql
   -- Copy contents of backend/database/migrations/migration_fix_oauth_user_creation.sql
   ```

2. ✅ Deploy the updated backend code (with the sync-user fix)

3. ✅ Test OAuth signup - should now work without errors

## Verification

**✅ VERIFIED**: OAuth signup now works correctly:
1. ✅ Migration applied successfully
2. ✅ Backend code deployed
3. ✅ OAuth signup works for new users
4. ✅ No "Database error saving new user" error
5. ✅ No redirect loop on login page
6. ✅ User redirected to onboarding/dashboard correctly

## Frontend Fixes Applied

The frontend code has been modified to:
1. Allow authenticated users to stay on `/auth/login` to see errors (prevents redirect loops)
2. Sign out users when hash errors are detected (clears invalid sessions)
3. Display error messages from both hash fragments and query parameters
4. Properly handle OAuth callback errors

These fixes ensure users see error messages and prevent redirect loops even when OAuth errors occur.

