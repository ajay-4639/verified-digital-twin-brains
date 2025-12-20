from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
if not supabase_key or "your_supabase_service_role_key" in supabase_key:
    supabase_key = os.getenv("SUPABASE_KEY")

# Validate environment variables before creating client
if not supabase_url:
    raise ValueError("SUPABASE_URL environment variable is not set. Please check your .env file.")
if not supabase_key:
    raise ValueError("SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable is not set. Please check your .env file.")

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    raise ValueError(f"Failed to initialize Supabase client: {e}. Please check your SUPABASE_URL and SUPABASE_KEY environment variables.")

async def create_escalation(message_id: str):
    response = supabase.table("escalations").insert({
        "message_id": message_id,
        "status": "open"
    }).execute()
    return response.data

async def resolve_escalation(escalation_id: str, owner_id: str, reply_content: str):
    # Add reply
    supabase.table("escalation_replies").insert({
        "escalation_id": escalation_id,
        "owner_id": owner_id,
        "content": reply_content
    }).execute()
    
    # Mark escalation as resolved
    # Note: Only setting status since resolved_by and resolved_at may not exist in all database schemas
    supabase.table("escalations").update({
        "status": "resolved"
    }).eq("id", escalation_id).execute()
    
    return True
