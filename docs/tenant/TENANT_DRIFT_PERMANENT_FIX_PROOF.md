# Tenant Drift Permanent Fix Proof

Date: 2026-02-08

## Scope
- Incident: owner twin disappeared from account due to tenant drift / orphan tenant mapping.
- Impacted twin: `c3cd4ad0-d4cc-4e82-a020-82b48de72d42` (`Sham`)
- Share token checked: `fa9b08c9-11db-460f-b5e7-f4ed9fb2cb97`

## Root Cause
1. The twin existed but was attached to a tenant that had no active user mapping.
2. User identity churn (new auth user ID for same owner email) allowed new user rows / tenant drift instead of re-linking.
3. `sync_user` create path always returned `needs_onboarding=true`, which can force onboarding flow even when recovered tenant already has twins.

## Code Fixes
- `backend/modules/auth_guard.py`
  - Added email-based tenant recovery in `resolve_tenant_id(...)`.
  - Re-links current `user_id` to the most recently active tenant for same non-deleted email.
  - Only creates a new tenant when no valid recovery path exists.
- `backend/routers/auth.py`
  - Normalizes email (`lower().strip()`).
  - Uses canonical `resolve_tenant_id(...)` in both existing-user and first-login paths.
  - In create path, computes onboarding state from tenant twins (`needs_onboarding=not has_twins`).
  - Uses timezone-aware timestamp for `created_at`.
- `backend/scripts/repair_tenant_drift.py`
  - Added deterministic dry-run/apply repair flow for orphaned/misaligned twins.
  - Archives name-conflicting active duplicates before move.
  - Retags tenant-scoped related rows.
  - Added no-op safety when twin is already in target tenant.

## Regression Tests Added
- `backend/tests/test_resolve_tenant_id_email_recovery.py`
  - `test_resolve_tenant_id_recovers_by_email_without_new_tenant`
  - `test_resolve_tenant_id_email_recovery_prefers_most_recent_active`
- `backend/tests/test_sync_user_tenant_recovery.py`
  - `test_sync_user_reuses_recovered_tenant_instead_of_new_creation`

## Test Execution Proof
### Tenant recovery regression tests
Command:
`cd backend && pytest -q tests/test_resolve_tenant_id_email_recovery.py tests/test_sync_user_tenant_recovery.py tests/test_resolve_tenant_id.py`

Result:
- `5 passed`

### Auth/tenant integration tests
Command:
`cd backend && pytest -q tests/test_auth_my_twins.py tests/test_twins_create_idempotency.py tests/test_tenant_guard.py tests/test_auth_comprehensive.py`

Result:
- `23 passed, 8 skipped`

### Interview-related regression safety check
Command:
`cd backend && pytest -q tests/test_interview_session.py tests/test_interview_integration.py tests/test_interview_finalize_diagnostics.py`

Result:
- `24 passed`

## Live Supabase MCP Proof
Project: `jvtffdbuwyhmcynauety`

### Current owner user mapping
SQL:
`select id, email, tenant_id, created_at, last_active_at from users where email = 'sainathsetti@gmail.com' order by coalesce(last_active_at, created_at) desc;`

Result:
- user `94ffb06e-647c-43a6-aabc-a4ea77e619bb`
- tenant `398260f6-e7fd-4a8e-a8ea-32cce50474ce`

### Twin is now in active tenant with share token intact
SQL:
`select id, name, tenant_id, settings->>'deleted_at' as deleted_at, settings->'widget_settings'->>'share_token' as share_token, settings->'widget_settings'->>'public_share_enabled' as public_share_enabled from twins where id = 'c3cd4ad0-d4cc-4e82-a020-82b48de72d42';`

Result:
- twin `c3cd4ad0-d4cc-4e82-a020-82b48de72d42`
- tenant `398260f6-e7fd-4a8e-a8ea-32cce50474ce`
- `deleted_at = null`
- share token `fa9b08c9-11db-460f-b5e7-f4ed9fb2cb97`
- public sharing enabled

### Orphan tenant verification
SQL:
`select t.id as tenant_id, count(distinct u.id) as user_count, count(distinct tw.id) as twin_count from tenants t left join users u on u.tenant_id = t.id left join twins tw on tw.tenant_id = t.id where t.id in ('398260f6-e7fd-4a8e-a8ea-32cce50474ce','f7302438-c115-4936-ad73-b118149a95c6') group by t.id order by t.id;`

Result:
- tenant `398260f6-e7fd-4a8e-a8ea-32cce50474ce`: `user_count=1`, `twin_count=3`
- tenant `f7302438-c115-4936-ad73-b118149a95c6`: `user_count=0`, `twin_count=0`

## API-Path Proof (`/auth/my-twins` logic)
Command:
`cd backend && python - <<PY ... call routers.auth.get_my_twins(user={"user_id":"94ff...","email":"sainathsetti@gmail.com"}) ... PY`

Observed output:
- resolved tenant: `398260f6-e7fd-4a8e-a8ea-32cce50474ce`
- returned twins count: `1`
- returned twin ids: `['c3cd4ad0-d4cc-4e82-a020-82b48de72d42']`

This confirms `my-twins` resolution path returns the expected active twin.

## Repair Script Dry-Run Proof
Command:
`cd backend && python scripts/repair_tenant_drift.py --twin-id c3cd4ad0-d4cc-4e82-a020-82b48de72d42 --target-email sainathsetti@gmail.com`

Result:
- `mode: dry_run`
- `target_user.tenant_id: 398260f6-e7fd-4a8e-a8ea-32cce50474ce`
- action emitted: `noop` (`Twin already belongs to target tenant`)

This confirms idempotent safety after repair.

## Remaining Risks
- Other historical tenants in the environment still contain duplicate names (`Sham`) belonging to different accounts/tenants. This is not a cross-tenant access bug by itself, but can create operator confusion. Cleanup should be done per-account ownership verification.
- Interview memory extraction quality issues are a separate pipeline problem and are not fixed by this tenant-drift patch.
