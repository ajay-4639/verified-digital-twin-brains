from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from modules.auth_guard import get_current_user, verify_owner
from modules.ingestion import (
    ingest_source, 
    delete_source, 
    ingest_youtube_transcript,
    ingest_podcast_rss,
    ingest_x_thread
)
from modules.retrieval import retrieve_context
from modules.agent import run_agent_stream
from modules.memory import inject_verified_memory
from modules.verified_qna import (
    create_verified_qna,
    get_verified_qna,
    edit_verified_qna,
    list_verified_qna
)
from modules.access_groups import (
    get_user_group,
    get_default_group,
    create_group,
    assign_user_to_group,
    add_content_permission,
    remove_content_permission,
    get_group_permissions,
    get_groups_for_content,
    list_groups,
    get_group,
    update_group,
    delete_group,
    get_group_members,
    set_group_limit,
    get_group_limits,
    set_group_override,
    get_group_overrides
)
from modules.escalation import create_escalation, resolve_escalation as resolve_db_escalation
from modules.observability import (
    log_interaction, 
    create_conversation, 
    get_conversations, 
    get_messages,
    get_sources,
    get_knowledge_profile,
    supabase
)
from modules.schemas import (
    ChatRequest, 
    ChatMetadata, 
    ChatContent, 
    ChatDone, 
    IngestionResponse,
    EscalationSchema,
    TwinSettingsUpdate,
    YouTubeIngestRequest,
    PodcastIngestRequest,
    XThreadIngestRequest,
    KnowledgeProfile,
    VerifiedQnACreateRequest,
    VerifiedQnAUpdateRequest,
    VerifiedQnASchema,
    AccessGroupSchema,
    GroupMembershipSchema,
    ContentPermissionSchema,
    GroupCreateRequest,
    GroupUpdateRequest,
    AssignUserRequest,
    ContentPermissionRequest
)
from modules.clients import get_pinecone_index, get_openai_client
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import Dict, Any
import os
import shutil
import uuid
import json
import asyncio
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

app = FastAPI(title="Verified Digital Twin Brain API")

# Add CORS middleware
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResolutionRequest(BaseModel):
    owner_answer: str

@app.get("/health")
# ... (keep health_check as is)
async def health_check():
    health_status = {
        "status": "online",
        "services": {
            "pinecone": "unknown",
            "openai": "unknown"
        }
    }
    
    try:
        get_pinecone_index()
        health_status["services"]["pinecone"] = "connected"
    except Exception as e:
        health_status["services"]["pinecone"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    try:
        get_openai_client().models.list()
        health_status["services"]["openai"] = "connected"
    except Exception as e:
        health_status["services"]["openai"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    return health_status

@app.post("/chat/{twin_id}")
async def chat(twin_id: str, request: ChatRequest, user=Depends(get_current_user)):
    query = request.query
    conversation_id = request.conversation_id
    group_id = request.group_id
    
    # Determine user's group
    if not group_id:
        # Check if conversation has a group_id set
        if conversation_id:
            conv_response = supabase.table("conversations").select("group_id").eq("id", conversation_id).single().execute()
            if conv_response.data and conv_response.data.get("group_id"):
                group_id = conv_response.data["group_id"]
        
        # If still no group_id, get user's default group
        if not group_id:
            user_id = user.get("user_id")
            if user_id:
                user_group = await get_user_group(user_id, twin_id)
                if user_group:
                    group_id = user_group["id"]
            
            # Fallback to default group if user has no group
            if not group_id:
                default_group = await get_default_group(twin_id)
                group_id = default_group["id"]
    
    # 1. Logging User Message
    if not conversation_id:
        # Create a new conversation in Supabase with group_id
        conv_data = {
            "twin_id": twin_id,
            "user_id": user.get("user_id"),
            "group_id": group_id
        }
        conv_response = supabase.table("conversations").insert(conv_data).execute()
        conversation_id = conv_response.data[0]["id"] if conv_response.data else str(uuid.uuid4())
    else:
        # Update conversation with group_id if not already set
        conv_response = supabase.table("conversations").select("group_id").eq("id", conversation_id).single().execute()
        if conv_response.data and not conv_response.data.get("group_id"):
            supabase.table("conversations").update({"group_id": group_id}).eq("id", conversation_id).execute()
        
    # 2. Get history (fetch BEFORE logging the new message to avoid duplicates)
    history = []
    if conversation_id:
        msgs = get_messages(conversation_id)
        # Convert to LangChain messages
        for m in msgs[-5:]:
            if m["role"] == "user":
                history.append(HumanMessage(content=m["content"]))
            else:
                history.append(AIMessage(content=m["content"]))

    log_interaction(conversation_id, "user", query)

    # 3. Get Twin Personality (System Prompt)
    system_prompt = None
    twin_res = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
    if twin_res.data and twin_res.data.get("settings"):
        system_prompt = twin_res.data["settings"].get("system_prompt")

    async def stream_generator():
        # Variables to track final state
        final_content = ""
        citations = []
        confidence_score = 0.0
        sent_metadata = False

        async for event in run_agent_stream(twin_id, query, history, system_prompt, group_id=group_id):
            # The event is a dict from LangGraph updates
            if "tools" in event:
                # Update citations and confidence from tool results
                citations = event["tools"].get("citations", citations)
                confidence_score = event["tools"].get("confidence_score", confidence_score)
                
                # Send metadata as soon as we have tool results (if not sent)
                if not sent_metadata:
                    metadata = ChatMetadata(
                        confidence_score=confidence_score,
                        citations=citations,
                        conversation_id=conversation_id
                    )
                    yield metadata.model_dump_json() + "\n"
                    sent_metadata = True

            if "agent" in event:
                msg = event["agent"]["messages"][-1]
                if isinstance(msg, AIMessage) and msg.content:
                    # We might get the full content here or chunks depending on how we set up LLM
                    # In LangGraph updates mode, we usually get the full message at that node completion
                    # For token-by-token, we'd need a different streaming setup.
                    # For now, let's yield what we have.
                    chunk = msg.content[len(final_content):]
                    if chunk:
                        final_content += chunk
                        content_chunk = ChatContent(content=chunk)
                        yield content_chunk.model_dump_json() + "\n"

        # If metadata was never sent (e.g., no tool called), send it now
        if not sent_metadata:
            metadata = ChatMetadata(
                confidence_score=confidence_score,
                citations=citations,
                conversation_id=conversation_id
            )
            yield metadata.model_dump_json() + "\n"

        # 4. Final Logging
        msg = log_interaction(
            conversation_id, 
            "assistant", 
            final_content, 
            citations, 
            confidence_score
        )
        
        # 5. Escalation check
        escalated = False
        if confidence_score < 0.7:
            await create_escalation(msg["id"])
            escalated = True
        
        done = ChatDone(escalated=escalated)
        yield done.model_dump_json() + "\n"

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

@app.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(escalation_id: str, request: ResolutionRequest, user=Depends(verify_owner)):
    import json
    import time
    import traceback
    from datetime import datetime
    
    try:
        # 1. Fetch escalation and original message to get question
        from modules.observability import supabase
        esc_res = supabase.table("escalations").select(
            "*, messages(*, conversations(twin_id))"
        ).eq("id", escalation_id).single().execute()
        
        if not esc_res.data:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        # Extract question from the original message that triggered escalation
        # NOTE: messages.content is the ASSISTANT message, not the user question
        # We need to get the user message from the conversation instead
        assistant_message = esc_res.data["messages"]
        conversation_id = assistant_message.get("conversation_id")
        assistant_created_at = assistant_message.get("created_at")
        
        if not conversation_id:
            raise ValueError(f"Could not find conversation_id for escalation {escalation_id}")
        
        # Fetch all user messages in the conversation, then filter in Python
        question = None
        try:
            all_user_msgs = supabase.table("messages").select("*").eq(
                "conversation_id", conversation_id
            ).eq("role", "user").order("created_at", desc=True).execute()
            
            # Find the user message that comes before the assistant message
            if all_user_msgs.data:
                from datetime import datetime
                try:
                    # Parse assistant timestamp for comparison
                    if isinstance(assistant_created_at, str):
                        assistant_created_at_clean = assistant_created_at.replace('Z', '+00:00')
                        assistant_ts = datetime.fromisoformat(assistant_created_at_clean)
                    else:
                        assistant_ts = assistant_created_at
                    
                    # Find the first user message (most recent) that was created before assistant message
                    for user_msg in all_user_msgs.data:
                        user_created_at = user_msg.get("created_at")
                        if isinstance(user_created_at, str):
                            user_created_at_clean = user_created_at.replace('Z', '+00:00')
                            user_ts = datetime.fromisoformat(user_created_at_clean)
                        else:
                            user_ts = user_created_at
                        
                        if user_ts < assistant_ts:
                            question = user_msg.get("content")
                            break
                except Exception as e:
                    # Fallback: use the most recent user message
                    if all_user_msgs.data:
                        question = all_user_msgs.data[0].get("content")
        except Exception as e:
            question = None
        
        # Fallback to assistant message content if no user question found
        if not question:
            question = assistant_message.get("content")
        
        twin_id = esc_res.data["messages"]["conversations"]["twin_id"]
        owner_id = user.get("user_id")
        
        # 2. Update the database state (mark as resolved, add reply)
        await resolve_db_escalation(escalation_id, owner_id, request.owner_answer)
        
        # 3. Create verified QnA entry in Postgres (this also calls inject_verified_memory for backward compatibility)
        verified_qna_id = await create_verified_qna(
            escalation_id=escalation_id,
            question=question,
            answer=request.owner_answer,
            owner_id=owner_id,
            citations=None,  # Can be enhanced to extract citations from escalation context
            twin_id=twin_id
        )
        
        # 4. Trigger background style analysis refresh (don't block on this)
        try:
            from modules.agent import get_owner_style_profile
            asyncio.create_task(get_owner_style_profile(twin_id, force_refresh=True))
        except Exception as bg_error:
            # Log but don't fail the request if background task setup fails
            print(f"Warning: Failed to start background style profile refresh: {bg_error}")
        
        return {
            "status": "success",
            "verified_qna_id": verified_qna_id,
            "message": "Escalation resolved and verified QnA created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/youtube/{twin_id}")
async def ingest_youtube(twin_id: str, request: YouTubeIngestRequest, user=Depends(verify_owner)):
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_youtube_transcript(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ingest/podcast/{twin_id}")
async def ingest_podcast(twin_id: str, request: PodcastIngestRequest, user=Depends(verify_owner)):
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_podcast_rss(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ingest/x/{twin_id}")
async def ingest_x(twin_id: str, request: XThreadIngestRequest, user=Depends(verify_owner)):
    source_id = str(uuid.uuid4())
    try:
        num_chunks = await ingest_x_thread(source_id, twin_id, request.url)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ingest/{twin_id}")
async def ingest(twin_id: str, file: UploadFile = File(...), user=Depends(verify_owner)):
    # Save file temporarily
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    source_id = str(uuid.uuid4())
    
    try:
        num_chunks = await ingest_source(source_id, twin_id, file_path, file.filename)
        return {"status": "success", "chunks_ingested": num_chunks, "source_id": source_id}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/conversations/{twin_id}")
async def list_conversations(twin_id: str, user=Depends(get_current_user)):
    return get_conversations(twin_id)

@app.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: str, user=Depends(get_current_user)):
    return get_messages(conversation_id)

@app.delete("/sources/{twin_id}/{source_id}")
async def remove_source(twin_id: str, source_id: str, user=Depends(verify_owner)):
    try:
        await delete_source(source_id, twin_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sources/{twin_id}")
async def list_sources(twin_id: str, user=Depends(get_current_user)):
    return get_sources(twin_id)

@app.get("/twins/{twin_id}/knowledge-profile", response_model=KnowledgeProfile)
async def knowledge_profile(twin_id: str, user=Depends(get_current_user)):
    try:
        profile = await get_knowledge_profile(twin_id)
        return profile
    except Exception as e:
        print(f"Error fetching knowledge profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/twins/{twin_id}")
async def get_twin(twin_id: str, user=Depends(verify_owner)):
    response = supabase.table("twins").select("*").eq("id", twin_id).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Twin not found")
    return response.data

@app.patch("/twins/{twin_id}")
async def update_twin(twin_id: str, update: TwinSettingsUpdate, user=Depends(verify_owner)):
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    response = supabase.table("twins").update(update_data).eq("id", twin_id).execute()
    return response.data

@app.get("/escalations")  # Removed response_model to allow extra fields
async def list_escalations(user=Depends(verify_owner)):
    # Fetch escalations with assistant messages
    response = supabase.table("escalations").select("*, messages(*)").order("created_at", desc=True).execute()
    
    # For each escalation, fetch the user question (the message before the assistant message in the conversation)
    result = []
    for esc in (response.data or []):
        assistant_msg = esc.get("messages")
        if assistant_msg:
            conversation_id = assistant_msg.get("conversation_id")
            assistant_created_at = assistant_msg.get("created_at")
            
            # Get the most recent user message in this conversation that was created before the assistant message
            user_question = None
            try:
                # Fetch all user messages in the conversation, ordered by created_at descending (most recent first)
                all_user_msgs = supabase.table("messages").select("*").eq(
                    "conversation_id", conversation_id
                ).eq("role", "user").order("created_at", desc=True).execute()
                
                # Find the user message that comes before the assistant message
                if all_user_msgs.data:
                    from datetime import datetime
                    try:
                        # Parse assistant timestamp for comparison
                        if isinstance(assistant_created_at, str):
                            # Handle ISO format strings
                            assistant_created_at_clean = assistant_created_at.replace('Z', '+00:00')
                            assistant_ts = datetime.fromisoformat(assistant_created_at_clean)
                        else:
                            assistant_ts = assistant_created_at
                        
                        # Find the first user message (most recent) that was created before assistant message
                        for user_msg in all_user_msgs.data:
                            user_created_at = user_msg.get("created_at")
                            if isinstance(user_created_at, str):
                                user_created_at_clean = user_created_at.replace('Z', '+00:00')
                                user_ts = datetime.fromisoformat(user_created_at_clean)
                            else:
                                user_ts = user_created_at
                            
                            if user_ts < assistant_ts:
                                user_question = user_msg.get("content")
                                break
                    except Exception as e:
                        # Fallback: use the most recent user message
                        if all_user_msgs.data:
                            user_question = all_user_msgs.data[0].get("content")
            except Exception as e:
                user_question = None
            
            # Add user question to the escalation data
            # Convert to dict and add the user_question field
            esc_dict = {}
            if isinstance(esc, dict):
                esc_dict.update(esc)
            else:
                esc_dict = dict(esc)
            
            if user_question:
                esc_dict["user_question"] = user_question
            else:
                # Fallback: if no user message found, use assistant message content (shouldn't happen normally)
                esc_dict["user_question"] = assistant_msg.get("content")
        else:
            esc_dict = dict(esc) if isinstance(esc, dict) else {}
            esc_dict.update(esc) if hasattr(esc, '__dict__') else None
            esc_dict["user_question"] = None
        
        result.append(esc_dict)
    
    return result

@app.get("/twins/{twin_id}/verified-qna")  # Removed response_model to allow dynamic fields
async def list_twin_verified_qna(twin_id: str, visibility: Optional[str] = None, user=Depends(get_current_user)):
    """
    List all verified QnA entries for a twin.
    Optional visibility filter: 'private', 'shared', 'public'
    """
    try:
        qna_list = await list_verified_qna(twin_id, visibility, group_id=group_id)
        # Format with citations and patches for each entry
        result = []
        for qna in qna_list:
            try:
                full_qna = await get_verified_qna(qna["id"])
                if full_qna:
                    result.append(full_qna)
            except Exception as e:
                # Log error but continue processing other entries
                print(f"Error fetching full QnA for {qna.get('id')}: {e}")
                # Still include the basic QnA entry even if fetching full details fails
                result.append(qna)
        return result
    except Exception as e:
        import traceback
        print(f"Error listing verified QnA: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/verified-qna/{qna_id}", response_model=VerifiedQnASchema)
async def get_verified_qna_endpoint(qna_id: str, user=Depends(get_current_user)):
    """
    Get specific verified QnA with citations and patch history.
    """
    try:
        qna = await get_verified_qna(qna_id)
        if not qna:
            raise HTTPException(status_code=404, detail="Verified QnA not found")
        return qna
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/verified-qna/{qna_id}")
async def update_verified_qna(qna_id: str, request: VerifiedQnAUpdateRequest, user=Depends(verify_owner)):
    """
    Edit verified answer (creates patch entry for version history).
    Body: { "answer": "...", "reason": "..." }
    """
    try:
        await edit_verified_qna(
            qna_id=qna_id,
            new_answer=request.answer,
            reason=request.reason,
            owner_id=user.get("user_id")
        )
        return {"status": "success", "message": "Verified QnA updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/verified-qna/{qna_id}")
async def delete_verified_qna(qna_id: str, user=Depends(verify_owner)):
    """
    Soft delete verified QnA (set is_active = false).
    Optionally purges from Pinecone (future enhancement).
    Note: verify_owner dependency already ensures user is an owner.
    """
    try:
        # Check if QnA exists
        qna_res = supabase.table("verified_qna").select("twin_id, twins(tenant_id)").eq("id", qna_id).single().execute()
        if not qna_res.data:
            raise HTTPException(status_code=404, detail="Verified QnA not found")
        
        # Verify the QnA belongs to a twin in the user's tenant
        twin_tenant_id = qna_res.data.get("twins", {}).get("tenant_id")
        if twin_tenant_id and twin_tenant_id != user.get("tenant_id"):
            raise HTTPException(status_code=403, detail="Verified QnA does not belong to your tenant")
        
        # Soft delete
        supabase.table("verified_qna").update({"is_active": False}).eq("id", qna_id).execute()
        
        # TODO: Optionally purge from Pinecone by searching for matching vectors
        # This would require storing vector_id in verified_qna or searching by metadata
        
        return {"status": "success", "message": "Verified QnA deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Access Groups API Endpoints
# ============================================================================

@app.get("/twins/{twin_id}/access-groups")
async def list_access_groups(twin_id: str, user=Depends(verify_owner)):
    """
    List all access groups for a twin.
    """
    try:
        groups = await list_groups(twin_id)
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/twins/{twin_id}/access-groups")
async def create_access_group(
    twin_id: str, 
    request: GroupCreateRequest, 
    user=Depends(verify_owner)
):
    """
    Create a new access group for a twin.
    """
    try:
        group_id = await create_group(
            twin_id=twin_id,
            name=request.name,
            description=request.description,
            is_public=request.is_public,
            settings=request.settings or {}
        )
        group = await get_group(group_id)
        return group
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/access-groups/{group_id}")
async def get_access_group(group_id: str, user=Depends(get_current_user)):
    """
    Get access group details.
    """
    try:
        group = await get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Access group not found")
        return group
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/access-groups/{group_id}")
async def update_access_group(
    group_id: str, 
    request: GroupUpdateRequest, 
    user=Depends(verify_owner)
):
    """
    Update access group.
    """
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        await update_group(group_id, updates)
        group = await get_group(group_id)
        return group
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/access-groups/{group_id}")
async def delete_access_group(group_id: str, user=Depends(verify_owner)):
    """
    Delete an access group (cannot delete default group).
    """
    try:
        await delete_group(group_id)
        return {"message": "Access group deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/access-groups/{group_id}/members")
async def list_group_members(group_id: str, user=Depends(get_current_user)):
    """
    List all members of an access group.
    """
    try:
        members = await get_group_members(group_id)
        return members
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/twins/{twin_id}/group-memberships")
async def assign_user_to_group_endpoint(
    twin_id: str,
    request: AssignUserRequest,
    user=Depends(verify_owner)
):
    """
    Assign user to a group (replaces existing membership for that twin).
    """
    try:
        from modules.access_groups import assign_user_to_group as assign_user
        await assign_user(request.user_id, twin_id, request.group_id)
        return {"message": "User assigned to group successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/group-memberships/{membership_id}")
async def remove_group_membership(
    membership_id: str, 
    user=Depends(verify_owner)
):
    """
    Remove user from group (deactivate membership).
    """
    try:
        supabase.table("group_memberships").update({"is_active": False}).eq("id", membership_id).execute()
        return {"message": "User removed from group successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/access-groups/{group_id}/permissions")
async def grant_content_permissions(
    group_id: str,
    request: ContentPermissionRequest,
    user=Depends(verify_owner)
):
    """
    Grant group access to content (sources or verified QnA).
    """
    try:
        # Get twin_id from group
        group = await get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        twin_id = group["twin_id"]
        
        # Grant permissions for each content_id
        for content_id in request.content_ids:
            await add_content_permission(group_id, request.content_type, content_id, twin_id)
        
        return {"message": f"Granted access to {len(request.content_ids)} content item(s)"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/access-groups/{group_id}/permissions/{content_type}/{content_id}")
async def revoke_content_permission(
    group_id: str,
    content_type: str,
    content_id: str,
    user=Depends(verify_owner)
):
    """
    Revoke group access to specific content.
    """
    try:
        await remove_content_permission(group_id, content_type, content_id)
        return {"message": "Permission revoked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/access-groups/{group_id}/permissions")
async def list_group_permissions(group_id: str, user=Depends(get_current_user)):
    """
    List all content accessible to a group.
    """
    try:
        permissions = await get_group_permissions(group_id)
        return permissions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/content/{content_type}/{content_id}/groups")
async def get_content_groups(
    content_type: str,
    content_id: str,
    user=Depends(get_current_user)
):
    """
    Get all groups that have access to specific content.
    """
    try:
        group_ids = await get_groups_for_content(content_type, content_id)
        # Fetch group details
        groups = []
        for gid in group_ids:
            group = await get_group(gid)
            if group:
                groups.append(group)
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/access-groups/{group_id}/limits")
async def set_group_limit_endpoint(
    group_id: str,
    limit_type: str = Query(...),
    limit_value: int = Query(...),
    user=Depends(verify_owner)
):
    """
    Set a limit for a group.
    Query params: limit_type, limit_value
    """
    try:
        await set_group_limit(group_id, limit_type, limit_value)
        return {"message": f"Limit {limit_type} set to {limit_value}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/access-groups/{group_id}/limits")
async def list_group_limits(group_id: str, user=Depends(get_current_user)):
    """
    List all limits for a group.
    """
    try:
        limits = await get_group_limits(group_id)
        return limits
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/access-groups/{group_id}/overrides")
async def set_group_override_endpoint(
    group_id: str,
    request: Dict[str, Any],
    user=Depends(verify_owner)
):
    """
    Set an override for a group.
    Body: { "override_type": "...", "override_value": ... }
    override_type: 'system_prompt', 'temperature', 'max_tokens', 'tool_access'
    """
    try:
        override_type = request.get("override_type")
        override_value = request.get("override_value")
        if not override_type or override_value is None:
            raise HTTPException(status_code=400, detail="override_type and override_value are required")
        await set_group_override(group_id, override_type, override_value)
        return {"message": f"Override {override_type} set successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/access-groups/{group_id}/overrides")
async def list_group_overrides(group_id: str, user=Depends(get_current_user)):
    """
    List all overrides for a group.
    """
    try:
        overrides = await get_group_overrides(group_id)
        return overrides
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import socket

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    if is_port_in_use(port):
        print(f"ERROR: Port {port} is already in use.")
        print(f"Please kill the process using this port or set a different port via the PORT environment variable.")
    else:
        print(f"Starting server on {host}:{port}...")
        uvicorn.run(app, host=host, port=port)
