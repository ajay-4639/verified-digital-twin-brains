# Roadmap: Verified Digital Twin Brain → Delphi-Grade Upgrade

*Checkpoint system active: Phase completions are automatically tagged and released.*

This roadmap outlines the evolution from a grounded Q&A engine to a **Delphi-grade** digital twin platform with enterprise trust, operational control, and scalable distribution.

**Status Legend:**
- `[x]` = Fully implemented
- `[~]` = Partially implemented (needs upgrade)
- `[ ]` = Not implemented

---

## Baseline: Completed Phases (Strong Foundation)

### Phase 1 (MVP) - Grounded Answers
**Status: Completed**

- [x] Multi-tenant database schema (Supabase).
- [x] Document ingestion pipeline (PDF extraction -> Chunking -> OpenAI Embeddings -> Pinecone).
- [x] RAG-based chat API with citation support.
- [x] Confidence-based escalation logic.
- [x] Basic Next.js dashboard and chat interface.

---

### Phase 2 - Cloud Agents & Verified Memory
**Status: Completed**

The goal is to move from a local Q&A script to a **live, agentic cloud brain** that can reason and verify knowledge.

- [x] **Cloud Migration readiness**: Added `Procfile` and `railway.json` for cloud deployment.
- [x] **Agentic Reasoning Loop**: Transitioned from static RAG to a dynamic LangGraph reasoning loop.
- [x] **Verified Memory Injection**: Implemented logic to turn owner's manual responses into high-priority vector embeddings.
- [x] **Early Tool Framework**: Established `modules/tools.py` architecture for future cloud tool expansion.
- [x] **Advanced Reranking**: Implement a re-ranking layer (Cohere/BGE) to improve retrieval precision.
- [x] **Owner Escalation Inbox**: UI for owners to view and resolve low-confidence questions.
- [x] **Twin Personalization**: System instructions and basic persona configuration.

---

### Phase 3 - Digital Persona & Multi-Modal Mind
**Status: Completed**

Moving from a basic RAG bot to a high-fidelity digital mind that clones the owner's knowledge and style.

- [x] **HyDE & Query Expansion**: Generate hypothetical answers to improve vector search depth.
- [x] **Context Enrichment**: Ingest documents with hypothetical questions and opinion/fact metadata tags.
- [x] **Multi-Modal Ingestion**: Scrapers for YouTube transcripts, Podcast audio (Whisper), and Social Media (Twitter/X threads).
- [x] **Persona Encoding**: Analysis of owner's writing style, common phrases, and opinion vectors for high-fidelity responses.

---

## Delphi-Grade Upgrade Phases

### Phase 4: Verified-First Knowledge Layer
**Status: Completed ✅** | **Effort: Medium** | **Priority: High**

**Goal:** Make "verified" deterministic and stable. Prevent repeat hallucinations after an owner correction.

**Current State:**
- [x] Verified answers stored as high-priority vectors in Pinecone (`inject_verified_memory`)
- [x] Retrieval prioritizes verified results and is enforced in orchestrator
- [x] Escalation workflow exists with canonical answer storage

**Implementation Summary:**
- [x] Postgres tables: `verified_qna`, `answer_patches`, `citations` ✅
- [x] Retrieval order enforced in Orchestrator: 1) Verified QnA match, 2) Vector retrieval, 3) Tool calls ✅
- [x] Owner workflow: Approve escalation → publish to `verified_qna`, Edit answer → creates patch version ✅
- [x] Response policy: "I don't know" when no verified/strong retrieval, routes to inbox ✅
- [x] Optional "general knowledge allowed" toggle per tenant (implemented in agent system prompt) ✅

**Exit Criteria:**
- [x] A question corrected once never regresses in future sessions ✅
- [x] Verified answers can be served with minimal citations UI noise, but retain provenance in logs ✅

**Risk Assessment:**
- **Low Risk**: Building on existing escalation workflow
- **Migration Path**: Existing verified vectors can be migrated to `verified_qna` table
- **Dependency**: Requires orchestrator refactor to enforce retrieval order

---

### Phase 5: Access Groups as First-Class Primitive
**Status: Next** | **Effort: Large** | **Priority: High**

**Goal:** Delphi-style segmentation. Different audiences see different knowledge, limits, tone, and allowed actions.

**Current State:**
- [ ] No access group system exists
- [ ] Single knowledge base per twin
- [ ] No audience segmentation

**Gap Analysis:**
- Missing `access_groups`, `group_memberships`, `content_permissions` tables
- No enforcement points in retriever for group permissions
- No UI for creating/managing groups
- No group-level limits or overrides

**Deliverables:**
- [ ] Postgres tables: `access_groups`, `group_memberships`, `content_permissions`, `group_limits`, `group_overrides`
- [ ] Enforcement points: Retriever filters context by group permissions, Verified QnA filters by group, Tool access scoped by group
- [ ] UI: Create group, assign content, assign members, simulate group conversation in console

**Exit Criteria:**
- Same question asked by two groups produces different allowed answers based on configured permissions
- Hard limits are enforced per group and visible in admin analytics

**Risk Assessment:**
- **Medium Risk**: Requires significant refactoring of retrieval and agent logic
- **Migration Path**: Default "public" group for existing twins
- **Dependency**: Should follow Phase 4 (verified QnA) for content permission model

---

### Phase 6: Mind Ops Layer (Content Loading Dock + Training State Machine)
**Status: Planned** | **Effort: Large** | **Priority: Medium**

**Goal:** Operational reliability. Scale ingestion without corrupting the brain with low-quality content.

**Current State:**
- [~] Direct ingestion → Pinecone (no staging)
- [~] Basic source status tracking (`pending`, `processed`, `error`)
- [ ] No content health checks
- [ ] No training job system

**Gap Analysis:**
- Missing staging dock for sources before indexing
- No content health checks (empty extraction, duplicates, chunk anomalies)
- No training jobs table or worker
- No metadata hygiene (citation URLs, publish dates, sync constraints)
- No ingestion observability (logs, retriable failures, dead letter queue)

**Deliverables:**
- [ ] Content loading dock: Staged sources with metadata before indexing/training
- [ ] Bulk actions: Assign access group, set visibility, set publish date, author attribution
- [ ] Training jobs: `training_jobs` table and worker, statuses (queued, processing, needs_attention, complete)
- [ ] Content health checks: Empty extraction detection, duplicate detection via content hash, chunk count anomalies, missing metadata rules
- [ ] Metadata hygiene: Citation URL override, publish date tracking, keep-synced behavior for supported sources
- [ ] Observability: Ingestion logs per source, retriable failures and dead letter queue

**Exit Criteria:**
- Every source has a visible lifecycle and health status
- Ingestion failures are diagnosable without reading raw server logs
- You can run a content audit and see what is live, what is staged, and what is broken

**Risk Assessment:**
- **Medium Risk**: Requires new worker infrastructure and job queue
- **Migration Path**: Existing sources can be backfilled with health status
- **Dependency**: Can be built in parallel with Phase 4/5

---

### Phase 7: Omnichannel Distribution (Embed Widget + Share Link)
**Status: Planned** | **Effort: Medium** | **Priority: High**

**Goal:** Delphi-style distribution while keeping trust boundaries intact.

**Current State:**
- [~] Basic `ChatWidget.tsx` component exists but not production-ready
- [~] Widget points to `localhost`, no domain allowlists
- [ ] No API key system for third-party integration
- [ ] No shareable twin links
- [ ] No session model for anonymous/authenticated users

**Gap Analysis:**
- Widget needs domain allow-list enforcement
- Missing API keys scoped to tenant and group
- No rate limiting or abuse controls
- No public/private share link system
- No session management for anonymous vs authenticated users

**Deliverables:**
- [ ] Embeddable web widget: Domain allow-list, API keys scoped to tenant and group, rate limiting and abuse controls
- [ ] Shareable twin links: Public mode restricted to public content and public access group
- [ ] Session model: Anonymous sessions for public, authenticated sessions for private
- [ ] Channel adapters v1: Web chat is default, architecture prepared for Slack/WhatsApp later

**Exit Criteria:**
- A creator can embed the twin on a website with restricted domains
- Public users can only access explicitly public content, never private sources

**Risk Assessment:**
- **Low Risk**: Building on existing widget component
- **Migration Path**: Existing widget can be upgraded incrementally
- **Dependency**: Requires Phase 5 (Access Groups) for public/private content separation

---

### Phase 8: Actions Engine (Trigger → Plan → Draft → Approve → Execute)
**Status: Research & Development** | **Effort: Large** | **Priority: Medium**

**Goal:** Move from Q&A to outcomes, while preserving accountability.

**Current State:**
- [~] Tool framework exists (`modules/tools.py`)
- [~] Basic Composio integration scaffold
- [ ] No event model or triggers
- [ ] No draft/approve/execute pipeline
- [ ] No action execution logs

**Gap Analysis:**
- Missing `events` table for tracking (message_received, answer_sent, escalation_created, idle_timeout)
- No `action_triggers` with conditions (intent, keywords, confidence, channel, group)
- No draft-only mode or approval workflow
- No execution logs with tool inputs/outputs
- No tool connectors v1 (Gmail read, Calendar read, Draft email/event creation)

**Deliverables:**
- [ ] Event model: `events` table (message_received, answer_sent, escalation_created, idle_timeout)
- [ ] Triggers and rules: `action_triggers` with conditions (intent, keywords, confidence, channel, group)
- [ ] Action execution pipeline: Draft-only mode by default, approvals required for write actions, execution logs include tool inputs and outputs
- [ ] Tool connectors v1: Gmail read, Calendar read, Draft email and draft event creation, No autonomous writes without explicit approval

**Exit Criteria:**
- A user request can produce a draft action, route for approval, then execute with full audit trail
- You can replay an action decision with complete context and provenance

**Risk Assessment:**
- **High Risk**: Complex integration with external tools, requires careful security model
- **Migration Path**: Can start with read-only tools, add write actions incrementally
- **Dependency**: Requires Phase 5 (Access Groups) for group-scoped tool access

---

### Phase 9: Verification & Governance (Trust Layer)
**Status: Planned** | **Effort: Medium** | **Priority: High**

**Goal:** Delphi-grade trust posture. Verified identity, consent controls, and immutable auditability.

**Current State:**
- [~] Basic escalation workflow exists
- [~] Basic JWT auth exists
- [ ] No identity verification workflow
- [ ] No immutable audit log
- [ ] No consent/deletion workflows

**Gap Analysis:**
- Missing identity verification workflow (owner verification steps, verification status, badge logic)
- No consent and deletion workflows (revoke integration access, stop ingest, purge vectors)
- No immutable audit log (append-only event store, WORM storage optional)
- No policy enforcement (refusal rules per group, prompt injection defenses, tool sandboxing)

**Deliverables:**
- [ ] Identity verification workflow: Owner verification steps, verification status and badge logic
- [ ] Consent and deletion workflows: Revoke integration access → stop ingest → purge vectors for that source, right-to-delete sources and derived embeddings
- [ ] Immutable audit log: Append-only event store, WORM storage optional
- [ ] Policy enforcement: Refusal rules per group, prompt injection defenses, tool sandboxing rules and timeouts

**Exit Criteria:**
- You can prove who approved what, when, and why
- Deletion requests remove raw content and vectors, and stop future use

**Risk Assessment:**
- **Medium Risk**: Requires careful data retention and deletion logic
- **Migration Path**: Existing escalations can be backfilled into audit log
- **Dependency**: Requires Phase 5 (Access Groups) for group-level policies

---

### Phase 10: Enterprise Scale & Reliability
**Status: Vision** | **Effort: Large** | **Priority: Low (for MVP)**

**Goal:** High availability, cost controls, and operations readiness.

**Current State:**
- [~] Basic health check endpoint exists
- [ ] No comprehensive observability
- [ ] No cost controls or quotas
- [ ] No background job queue
- [ ] No autoscaling or disaster recovery

**Gap Analysis:**
- Missing observability (metrics: retrieval latency, answer latency, tool latency, token usage, escalations; tracing across components)
- No cost controls (quotas per tenant and group, caching where safe, batching for embeddings and reranking)
- No deployment hardening (background job queue, worker autoscaling, backups, disaster recovery runbook)

**Deliverables:**
- [ ] Observability: Metrics (retrieval latency, answer latency, tool latency, token usage, escalations), tracing across Orchestrator, retrieval, tools, workers
- [ ] Cost controls: Quotas per tenant and group, caching where safe, batching for embeddings and reranking
- [ ] Deployment hardening: Background job queue (Redis, SQS, or equivalent), worker autoscaling, backups, disaster recovery runbook

**Exit Criteria:**
- System continues operating under partial failures
- You can onboard multiple creators with predictable costs and stable performance

**Risk Assessment:**
- **Low Risk**: Can be built incrementally as scale demands
- **Migration Path**: Existing system can be instrumented first, then optimized
- **Dependency**: Should follow all core feature phases

---

## Quick Wins (High Impact, Low Effort)

These can be implemented quickly to improve the platform:

1. **Enhanced Health Check** (Phase 10, partial)
   - Add detailed service status (Pinecone, OpenAI, Supabase connectivity)
   - Add basic metrics endpoint (request count, average latency)
   - **Effort: Small** | **Impact: Medium**

2. **Basic Content Health Checks** (Phase 6, partial)
   - Add duplicate detection via content hash during ingestion
   - Add empty extraction detection
   - **Effort: Small** | **Impact: Medium**

3. **Improved Escalation UI** (Phase 4, partial)
   - Add "Approve as Verified Answer" button directly in escalation inbox
   - Pre-populate verified QnA form with escalation context
   - **Effort: Small** | **Impact: High**

4. **Widget Domain Allowlist** (Phase 7, partial)
   - Add simple domain validation in widget API endpoint
   - Store allowed domains in twin settings
   - **Effort: Small** | **Impact: Medium**

5. **Basic Audit Log** (Phase 9, partial)
   - Add `audit_events` table with basic event logging
   - Log all escalations, verified answer approvals, source deletions
   - **Effort: Small** | **Impact: High**

---

## Implementation Priority Matrix

### Immediate Next Steps (Strict Priority Order)

1. **Phase 4: Verified-First Knowledge Layer** ⭐
   - **Why First**: Prevents regression, foundation for all other phases
   - **Blocks**: Phase 5 (Access Groups needs verified QnA for permissions)
   - **Quick Win**: Enhanced escalation UI can be done in parallel

2. **Phase 5: Access Groups**
   - **Why Second**: Enables B2B use cases, required for Phase 7 (Omnichannel)
   - **Blocks**: Phase 7 (Public/private content separation)
   - **Dependencies**: Phase 4 (verified QnA for content permissions)

3. **Phase 7: Omnichannel Distribution**
   - **Why Third**: High user value, enables distribution
   - **Dependencies**: Phase 5 (Access Groups for public/private)
   - **Can Start**: Widget improvements can begin in parallel

4. **Phase 6: Mind Ops Layer**
   - **Why Fourth**: Operational reliability, can be built in parallel
   - **Dependencies**: None (can start immediately)
   - **Quick Win**: Basic health checks can be done first

5. **Phase 9: Verification & Governance**
   - **Why Fifth**: Trust posture, required before scale
   - **Dependencies**: Phase 5 (Access Groups for group policies)
   - **Quick Win**: Basic audit log can be done first

6. **Phase 8: Actions Engine**
   - **Why Sixth**: Complex, requires solid foundation
   - **Dependencies**: Phase 5 (Access Groups for tool access scoping)
   - **Can Start**: Read-only tool connectors can begin early

7. **Phase 10: Enterprise Scale**
   - **Why Last**: Only needed at scale
   - **Dependencies**: All core features should be stable first
   - **Can Start**: Observability can be added incrementally

---

## Gap Analysis Summary

| Feature | Current State | Delphi-Grade State | Gap | Phase |
|---------|--------------|-------------------|-----|-------|
| Verified Answers | Vectors in Pinecone | Postgres `verified_qna` table | Canonical storage, versioning | Phase 4 |
| Access Groups | None | Full segmentation system | All tables, enforcement, UI | Phase 5 |
| Content Staging | Direct ingestion | Staging dock + health checks | Health checks, training jobs | Phase 6 |
| Embed Widget | Basic component | Production-ready with allowlists | Domain allowlists, API keys, rate limiting | Phase 7 |
| Actions Engine | Tool framework | Draft → Approve → Execute | Event model, triggers, approval workflow | Phase 8 |
| Identity Verification | Basic JWT | Full verification workflow | Verification steps, badges | Phase 9 |
| Audit Log | None | Immutable append-only | Event store, WORM storage | Phase 9 |
| Observability | Basic health check | Full metrics + tracing | Metrics, tracing, cost controls | Phase 10 |

---

## Release Strategy

Every phase ships with:
- ✅ A demo script
- ✅ A rollback plan
- ✅ Test coverage for tenant isolation and group permissions
- ✅ Instrumentation for usage and failure modes

---

## Notes

- **Phase 1-3**: Strong foundation completed ✅
- **Phase 4-10**: Delphi-grade upgrade path
- **Quick Wins**: Can be implemented in parallel with main phases
- **Priority Order**: Based on dependencies and user value
- **Risk Mitigation**: Each phase includes migration paths for existing data
