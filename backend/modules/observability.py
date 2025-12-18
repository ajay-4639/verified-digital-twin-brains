from supabase import create_client, Client
import os
from dotenv import load_dotenv
from modules.clients import get_pinecone_index

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
# Fallback to anon key if service key is placeholder or missing
if not supabase_key or "your_supabase_service_role_key" in supabase_key:
    supabase_key = os.getenv("SUPABASE_KEY")
    
supabase: Client = create_client(supabase_url, supabase_key)

def create_conversation(twin_id: str, user_id: str = None):
    data = {"twin_id": twin_id}
    if user_id:
        data["user_id"] = user_id
    response = supabase.table("conversations").insert(data).execute()
    return response.data[0] if response.data else None

def log_interaction(conversation_id: str, role: str, content: str, citations: list = None, confidence_score: float = None):
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content
    }
    if citations:
        data["citations"] = citations
    if confidence_score is not None:
        data["confidence_score"] = confidence_score
        
    response = supabase.table("messages").insert(data).execute()
    return response.data[0] if response.data else None

def get_conversations(twin_id: str):
    response = supabase.table("conversations").select("*").eq("twin_id", twin_id).order("created_at", desc=True).execute()
    return response.data

def get_messages(conversation_id: str):
    response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    return response.data

def get_sources(twin_id: str):
    response = supabase.table("sources").select("*").eq("twin_id", twin_id).order("created_at", desc=True).execute()
    return response.data

async def get_knowledge_profile(twin_id: str):
    """
    Analyzes the twin's knowledge base to generate stats on facts vs opinions and tone.
    """
    index = get_pinecone_index()
    
    # Query Pinecone for a sample of vectors to analyze metadata
    # We use a dummy vector for a broad search within the namespace
    # Dimensions for text-embedding-3-large is 3072
    query_res = index.query(
        vector=[0.0] * 3072,
        top_k=1000, # Analyze up to 1000 chunks
        include_metadata=True,
        namespace=twin_id
    )
    
    matches = query_res.get("matches", [])
    total_chunks = len(matches)
    
    fact_count = 0
    opinion_count = 0
    tone_distribution = {}
    
    for match in matches:
        metadata = match.get("metadata", {})
        
        # Category: FACT or OPINION
        category = metadata.get("category", "FACT")
        if category == "OPINION":
            opinion_count += 1
        else:
            fact_count += 1
            
        # Tone Distribution
        tone = metadata.get("tone", "Neutral")
        tone_distribution[tone] = tone_distribution.get(tone, 0) + 1
    
    # Get top tone
    top_tone = "Neutral"
    if tone_distribution:
        top_tone = max(tone_distribution, key=tone_distribution.get)
        
    # Get total sources from Supabase
    sources_res = supabase.table("sources").select("id", count="exact").eq("twin_id", twin_id).execute()
    total_sources = sources_res.count if hasattr(sources_res, 'count') else len(sources_res.data)
    
    return {
        "total_chunks": total_chunks,
        "total_sources": total_sources,
        "fact_count": fact_count,
        "opinion_count": opinion_count,
        "tone_distribution": tone_distribution,
        "top_tone": top_tone
    }
