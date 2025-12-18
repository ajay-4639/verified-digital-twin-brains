import os
import uuid
from typing import List
from PyPDF2 import PdfReader
from modules.clients import get_openai_client, get_pinecone_index
from modules.observability import supabase

def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

def get_embedding(text: str):
    client = get_openai_client()
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-large",
        dimensions=3072
    )
    return response.data[0].embedding

async def ingest_source(source_id: str, twin_id: str, file_path: str, filename: str = None):
    # 0. Check for existing sources with same name to handle "update"
    if filename:
        existing = supabase.table("sources").select("id").eq("twin_id", twin_id).eq("filename", filename).execute()
        if existing.data:
            print(f"File {filename} already exists. Updating source(s)...")
            # Delete ALL old versions first to keep knowledge clean
            for record in existing.data:
                old_source_id = record["id"]
                await delete_source(old_source_id, twin_id)
            # We keep the new source_id for the new record

    # 0.1 Record source in Supabase
    if filename:
        file_size = os.path.getsize(file_path)
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": filename,
            "file_size": file_size,
            "status": "processing"
        }).execute()

    # 1. Extract text
    text = extract_text_from_pdf(file_path)
    
    # 2. Chunk text
    chunks = chunk_text(text)
    
    # 3. Generate embeddings and upsert to Pinecone
    index = get_pinecone_index()
    vectors = []
    for i, chunk in enumerate(chunks):
        vector_id = str(uuid.uuid4())
        embedding = get_embedding(chunk)
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "source_id": source_id,
                "twin_id": twin_id,
                "text": chunk
            }
        })
    
    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        index.upsert(vectors[i:i + 100])
    
    # Update status to processed
    if filename:
        supabase.table("sources").update({"status": "processed"}).eq("id", source_id).execute()

    return len(vectors)

async def delete_source(source_id: str, twin_id: str):
    """
    Deletes a source from Supabase and its associated vectors from Pinecone.
    """
    # 1. Delete from Pinecone
    index = get_pinecone_index()
    try:
        # Note: Delete by filter requires metadata indexing enabled or serverless index
        index.delete(filter={
            "source_id": {"$eq": source_id},
            "twin_id": {"$eq": twin_id}
        })
    except Exception as e:
        print(f"Error deleting from Pinecone: {e}")
        # Continue to delete from Supabase even if Pinecone fails (maybe it was already gone)

    # 2. Delete from Supabase
    supabase.table("sources").delete().eq("id", source_id).eq("twin_id", twin_id).execute()
    
    return True
