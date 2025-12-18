import os
import uuid
import re
import json
import feedparser
import yt_dlp
from typing import List
from PyPDF2 import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi
from modules.clients import get_openai_client, get_pinecone_index
from modules.observability import supabase

def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_video_id(url: str) -> str:
    """
    Extracts the video ID from a YouTube URL.
    """
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11}).*'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def ingest_youtube_transcript(source_id: str, twin_id: str, url: str):
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")
    
    text = None
    try:
        # 1. Try fetching official transcript first (fastest)
        transcript_snippets = YouTubeTranscriptApi().fetch(video_id)
        text = " ".join([item.text for item in transcript_snippets])
    except Exception as e:
        print(f"Transcript API failed, falling back to Whisper: {e}")
        # 2. Fallback: Download audio and use Whisper
        try:
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            temp_filename = f"yt_{video_id}"
            
            ydl_opts = {
                'format': 'm4a/bestaudio/best',
                'outtmpl': os.path.join(temp_dir, f"{temp_filename}.%(ext)s"),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            audio_path = os.path.join(temp_dir, f"{temp_filename}.mp3")
            text = await transcribe_audio(audio_path)
            
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as fallback_e:
            print(f"Fallback also failed: {fallback_e}")
            raise ValueError(f"Could not ingest YouTube video: {fallback_e}")

    if not text:
        raise ValueError("No text could be extracted from the video")
        
    try:
        # Record source in Supabase
        supabase.table("sources").insert({
            "id": source_id,
            "twin_id": twin_id,
            "filename": f"YouTube: {video_id}",
            "file_size": len(text),
            "status": "processing"
        }).execute()
        
        num_chunks = await process_and_index_text(source_id, twin_id, text)
        
        supabase.table("sources").update({"status": "processed"}).eq("id", source_id).execute()
        return num_chunks
    except Exception as e:
        print(f"Error indexing YouTube content: {e}")
        raise e

async def ingest_podcast_rss(source_id: str, twin_id: str, url: str):
    """
    Ingests the latest episode from a podcast RSS feed.
    """
    try:
        feed = feedparser.parse(url)
        if not feed.entries:
            raise ValueError("No episodes found in RSS feed")
        
        latest_episode = feed.entries[0]
        audio_url = None
        for enclosure in latest_episode.enclosures:
            if enclosure.type.startswith('audio'):
                audio_url = enclosure.href
                break
        
        if not audio_url:
            raise ValueError("No audio URL found in the latest episode")

        # Download audio temporarily
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        filename = f"{uuid.uuid4()}.mp3"
        file_path = os.path.join(temp_dir, filename)

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(audio_url)
            with open(file_path, "wb") as f:
                f.write(response.content)

        # Transcribe and index
        num_chunks = await ingest_source(source_id, twin_id, file_path, f"Podcast: {latest_episode.title}")
        return num_chunks
    except Exception as e:
        print(f"Error ingesting podcast: {e}")
        raise e

async def ingest_x_thread(source_id: str, twin_id: str, url: str):
    """
    Ingests an X (Twitter) thread.
    Uses the syndication endpoint for simplicity.
    """
    tweet_id_match = re.search(r'status/(\d+)', url)
    if not tweet_id_match:
        raise ValueError("Invalid X (Twitter) URL")
    
    tweet_id = tweet_id_match.group(1)
    
    try:
        import httpx
        # Using the syndication endpoint to get tweet content
        syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(syndication_url)
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch tweet: {response.status_code}")
            
            data = response.json()
            text = data.get("text", "")
            user = data.get("user", {}).get("name", "Unknown")
            
            # Record source in Supabase
            supabase.table("sources").insert({
                "id": source_id,
                "twin_id": twin_id,
                "filename": f"X Thread: {tweet_id} by {user}",
                "file_size": len(text),
                "status": "processing"
            }).execute()

            num_chunks = await process_and_index_text(source_id, twin_id, text, metadata_override={"source_type": "x_thread"})
            
            supabase.table("sources").update({"status": "processed"}).eq("id", source_id).execute()
            return num_chunks
    except Exception as e:
        print(f"Error ingesting X thread: {e}")
        raise e

async def transcribe_audio(file_path: str) -> str:
    """
    Transcribes audio using OpenAI Whisper API.
    """
    client = get_openai_client()
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
    return transcript.text

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

async def analyze_chunk_content(text: str) -> dict:
    """
    Analyzes a chunk to generate synthetic questions, category (Fact/Opinion), and tone.
    """
    client = get_openai_client()
    try:
        # Using gpt-4o-mini for better reasoning with JSON output
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """Analyze the text chunk provided. Return a JSON object with:
                - 'questions': 3 brief questions this text chunk answers.
                - 'category': 'OPINION' if it contains beliefs, values, or personal perspectives. 'FACT' if it is objective information.
                - 'tone': A single word describing the style (e.g., 'Assertive', 'Casual', 'Technical', 'Thoughtful').
                - 'opinion_map': If category is 'OPINION', provide a JSON object with:
                    - 'topic': The main subject of the opinion.
                    - 'stance': A short description of the owner's position.
                    - 'intensity': A score from 1-10 on how strongly this opinion is held.
                  If category is 'FACT', set 'opinion_map' to null."""},
                {"role": "user", "content": text}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error analyzing chunk: {e}")
        return {"questions": [], "category": "FACT", "tone": "Neutral", "opinion_map": None}

async def process_and_index_text(source_id: str, twin_id: str, text: str, metadata_override: dict = None):
    # 2. Chunk text
    chunks = chunk_text(text)
    
    # 3. Generate embeddings and upsert to Pinecone
    index = get_pinecone_index()
    vectors = []
    for i, chunk in enumerate(chunks):
        vector_id = str(uuid.uuid4())
        
        # Analyze chunk for enrichment
        analysis = await analyze_chunk_content(chunk)
        synth_questions = analysis.get("questions", [])
        
        # Enriched embedding: include synthetic questions to improve retrieval
        enriched_text = f"CONTENT: {chunk}\nQUESTIONS: {', '.join(synth_questions)}"
        embedding = get_embedding(enriched_text)
        
        metadata = {
            "source_id": source_id,
            "twin_id": twin_id,
            "text": chunk, # Keep original text for grounding
            "synthetic_questions": synth_questions,
            "category": analysis.get("category", "FACT"),
            "tone": analysis.get("tone", "Neutral")
        }
        
        # Add opinion mapping if present
        opinion_map = analysis.get("opinion_map")
        if opinion_map and isinstance(opinion_map, dict):
            metadata["opinion_topic"] = opinion_map.get("topic")
            metadata["opinion_stance"] = opinion_map.get("stance")
            metadata["opinion_intensity"] = opinion_map.get("intensity")
        
        if metadata_override:
            metadata.update(metadata_override)
            
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": metadata
        })
    
    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        index.upsert(vectors[i:i + 100], namespace=twin_id)
        
    return len(vectors)

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

    # 1. Extract text (PDF or Audio)
    if file_path.endswith('.pdf'):
        text = extract_text_from_pdf(file_path)
    elif file_path.endswith(('.mp3', '.wav', '.m4a', '.webm')):
        text = await transcribe_audio(file_path)
    else:
        # Generic text extraction for other types if needed, or error
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    
    num_chunks = await process_and_index_text(source_id, twin_id, text)
    
    # Update status to processed
    if filename:
        supabase.table("sources").update({"status": "processed"}).eq("id", source_id).execute()

    # Trigger background style analysis refresh to incorporate new knowledge/opinions
    try:
        from modules.agent import get_owner_style_profile
        import asyncio
        asyncio.create_task(get_owner_style_profile(twin_id, force_refresh=True))
    except Exception as e:
        print(f"Failed to trigger style refresh: {e}")

    return num_chunks

async def delete_source(source_id: str, twin_id: str):
    """
    Deletes a source from Supabase and its associated vectors from Pinecone.
    """
    # 1. Delete from Pinecone
    index = get_pinecone_index()
    try:
        # Note: Delete by filter requires metadata indexing enabled or serverless index
        index.delete(
            filter={
                "source_id": {"$eq": source_id}
            },
            namespace=twin_id
        )
    except Exception as e:
        print(f"Error deleting from Pinecone: {e}")
        # Continue to delete from Supabase even if Pinecone fails (maybe it was already gone)

    # 2. Delete from Supabase
    supabase.table("sources").delete().eq("id", source_id).eq("twin_id", twin_id).execute()
    
    return True
