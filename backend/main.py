from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
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
    KnowledgeProfile
)
from modules.clients import get_pinecone_index, get_openai_client
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import os
import shutil
import uuid
import json
import asyncio
from typing import List
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
    
    # 1. Logging User Message
    if not conversation_id:
        # Create a new conversation in Supabase
        conv = create_conversation(twin_id, user.get("user_id"))
        conversation_id = conv["id"] if conv else str(uuid.uuid4())
        
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

        async for event in run_agent_stream(twin_id, query, history, system_prompt):
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
    try:
        # 1. Update the database state (mark as resolved, add reply)
        await resolve_db_escalation(escalation_id, user.get("user_id"), request.owner_answer)
        
        # 2. Inject into Pinecone for long-term memory
        vector_id = await inject_verified_memory(escalation_id, request.owner_answer)
        
        # 3. Fetch twin_id to trigger style update
        from modules.observability import supabase
        esc_res = supabase.table("escalations").select("messages(conversations(twin_id))").eq("id", escalation_id).single().execute()
        if esc_res.data:
            twin_id = esc_res.data["messages"]["conversations"]["twin_id"]
            # Trigger background style analysis refresh
            from modules.agent import get_owner_style_profile
            asyncio.create_task(get_owner_style_profile(twin_id, force_refresh=True))
        
        return {"status": "success", "vector_id": vector_id}
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

@app.get("/escalations", response_model=List[EscalationSchema])
async def list_escalations(user=Depends(verify_owner)):
    # Simple fetch for all escalations
    response = supabase.table("escalations").select("*, messages(*)").order("created_at", desc=True).execute()
    return response.data

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
