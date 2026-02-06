# Patch Plan

1. **Auth Log Redaction (P0)**
- Scope: Remove JWT secret logging and add regression test.
- Files: `backend/modules/auth_guard.py`, `backend/tests/test_auth_guard_logging.py`
- Status: Done

2. **Share Token Expiry Enforcement (P1)**
- Scope: Enforce expiry even if audit logging fails.
- Files: `backend/modules/share_links.py`, `backend/tests/test_auth_comprehensive.py`
- Status: Done

3. **Frontend Stream Buffering (P1)**
- Scope: Buffer JSON lines across chunks for chat streams.
- Files: `frontend/components/Chat/ChatInterface.tsx`, `frontend/components/Chat/ChatWidget.tsx`, `frontend/components/console/tabs/ChatTab.tsx`, `frontend/app/dashboard/access-groups/[group_id]/console/page.tsx`
- Status: Done

4. **Group Console State Fix (P1)**
- Scope: Replace stale state writes with functional updates for streaming.
- Files: `frontend/app/dashboard/access-groups/[group_id]/console/page.tsx`
- Status: Done

5. **Test Harness Stabilization (P1)**
- Scope: Fix stdout reassignment in tests and patch OpenAI/Pinecone mocks to avoid network.
- Files: `backend/tests/test_youtube_enterprise_pattern.py`, `backend/tests/test_p0_integration.py`
- Status: Done
