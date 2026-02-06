# Bug Backlog

| ID | Severity | Area | Description | Proof | File Paths | Fix Status |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-001 | P0 | Auth/Security | JWT secret printed to logs during auth debug. | Code inspection + new test ensuring secret not present in stdout. | `backend/modules/auth_guard.py:173-176`, `backend/tests/test_auth_guard_logging.py` | Fixed |
| BUG-002 | P1 | Share Links/Auth | Expired share tokens could validate as true if audit logging raised, bypassing expiry. | Failing test `test_expired_share_token` (before fix) now passing. | `backend/modules/share_links.py:146-164`, `backend/tests/test_auth_comprehensive.py:214-227` | Fixed |
| BUG-003 | P1 | Frontend Streaming | JSON line stream parsing dropped events when JSON split across chunks. | Repro script `proof/repro_stream_parser.py` (naive parser fails). | `frontend/components/Chat/ChatInterface.tsx:223-270`, `frontend/components/Chat/ChatWidget.tsx:130-170`, `frontend/components/console/tabs/ChatTab.tsx:130-165`, `frontend/app/dashboard/access-groups/[group_id]/console/page.tsx:84-121` | Fixed |
| BUG-004 | P1 | Frontend Streaming | Group console used stale state during stream updates, overwriting messages. | Code inspection; fixed with functional updates. | `frontend/app/dashboard/access-groups/[group_id]/console/page.tsx:46-127` | Fixed |
| BUG-005 | P1 | Test Reliability | Pytest crash on Windows due to `sys.stdout` reassignment in test module. | Pytest crash (ValueError: I/O operation on closed file) before fix. | `backend/tests/test_youtube_enterprise_pattern.py:10-15` | Fixed |
| BUG-006 | P1 | Test Reliability | P0 integration tests invoked real OpenAI/Pinecone due to mocks patching wrong imports. | Failing tests `test_chat_retrieval_fallback`/`test_graph_extraction_job_processing` before fix. | `backend/tests/test_p0_integration.py:34-214` | Fixed |
| BUG-007 | P1 (Suspected) | API Key Security | Domain validation bypass if `DEV_MODE` not set (defaults true). | Code inspection. | `backend/modules/auth_guard.py:17-25`, `backend/modules/auth_guard.py:52-77` | Open (Suspected) |
| BUG-008 | P1 (Suspected) | CORS | `allow_credentials=True` with env-driven origins could be unsafe if `ALLOWED_ORIGINS` misconfigured. | Code inspection. | `backend/main.py:19-35` | Open (Suspected) |
| BUG-009 | P2 (Suspected) | Performance | `/share/resolve/{handle}` scans all twins without indexed lookup. | Code inspection. | `backend/routers/chat.py:17-49` | Open (Suspected) |
| BUG-010 | P2 (Suspected) | SSE Reliability | Server stream does not detect client disconnects; potential wasted compute. | Code inspection. | `backend/routers/chat.py:115-410` | Open (Suspected) |
