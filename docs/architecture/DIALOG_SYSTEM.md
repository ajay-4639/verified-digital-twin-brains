# Dialogue System Architecture (Current)

This document describes the flow of message processing and context retrieval in the Verified Digital Twin Brain.

## 1. Entry Points
The system handles chat via three main FastAPI routes in `backend/routers/chat.py`:
- `POST /twins/{twin_id}/chat`: Authenticated user chat.
- `POST /twins/{twin_id}/chat/widget`: Public chat for embedded widgets.
- `POST /twins/{twin_id}/share/{token}/chat`: Public chat via shareable links.

All routes utilize `StreamingResponse` for SSE-based real-time interaction.

## 2. Core Orchestration
Routes delegate to `run_agent_stream` in `backend/modules/agent.py`.
The current agent uses a **LangGraph** `StateGraph` with the following nodes:
- `planner`: (Optional/Lite) Decomposes queries into sub-queries.
- `retrieve`: Fetches context from multiple search paths.
- `synthesize`: Reconstructs the final answer based on retrieved context.

## 3. Retrieval Pipeline
Retrieval is centralized in `backend/modules/retrieval.py` and exposed as a tool in `backend/modules/tools.py`.
Flow:
1. **Verified QnA Match**: Checks for exact or near-exact matches in verified owner answers.
2. **Query Expansion**: Generates 3 query variations.
3. **HyDE**: Generates a hypothetical answer for better vector embedding search.
4. **Pinecone Search**: Executes vector searches in the twin's namespace.
5. **RRF Merge**: Merges multiple result lists using Reciprocal Rank Fusion.
6. **Permission Filtering**: Filters results based on group access permissions.

## 4. Memory Tiers
- **Conversation Memory**: Managed as a sliding window of historical messages in the graph state.
- **Owner Memory (Verified)**: Stored in the `owner_beliefs` table.
- **Stance Inference**: Automatically inferred from owner-verified responses.

## 5. Teaching Loop
When the system identifies a gap (low confidence or explicit request):
1. A **Clarification Thread** is created in `backend/modules/owner_memory_store.py`.
2. The owner resolves it via the `POST /twins/{twin_id}/clarifications/{id}/resolve` endpoint.
3. Resolution writes a new verified memory to `owner_beliefs` with metadata (provenance, topic).
