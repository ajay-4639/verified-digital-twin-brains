# backend/routers/audio.py
"""Audio API endpoints for Text-to-Speech functionality.

Provides endpoints for:
- Generating audio from text
- Streaming audio responses
- Listing available voices
- Voice settings management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional, List
import io

from modules.auth_guard import get_current_user, verify_twin_ownership
from modules.audio_generator import (
    generate_audio, 
    generate_audio_stream, 
    list_available_voices,
    get_twin_voice_settings
)
from modules.observability import supabase

router = APIRouter(tags=["audio"])


class TTSRequest(BaseModel):
    """Request for text-to-speech generation."""
    text: str
    voice_id: Optional[str] = None  # Override default voice


class VoiceSettingsRequest(BaseModel):
    """Request to update voice settings."""
    voice_id: str
    stability: Optional[float] = 0.5
    similarity_boost: Optional[float] = 0.75
    style: Optional[float] = 0.0
    use_speaker_boost: Optional[bool] = True


@router.post("/audio/tts/{twin_id}")
async def text_to_speech(
    twin_id: str, 
    request: TTSRequest, 
    user=Depends(get_current_user)
):
    """
    Generate audio from text for a specific twin.
    Returns MP3 audio bytes.
    """
    verify_twin_ownership(twin_id, user)
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(request.text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")
    
    audio_bytes = generate_audio(request.text, twin_id)
    
    if not audio_bytes:
        raise HTTPException(
            status_code=503, 
            detail="Audio generation unavailable. Check ELEVENLABS_API_KEY."
        )
    
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename=twin_{twin_id[:8]}_audio.mp3"
        }
    )


@router.post("/audio/tts/{twin_id}/stream")
async def text_to_speech_stream(
    twin_id: str, 
    request: TTSRequest, 
    user=Depends(get_current_user)
):
    """
    Stream audio generation for real-time playback.
    Returns chunked MP3 audio stream.
    """
    verify_twin_ownership(twin_id, user)
    
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    async def audio_generator():
        async for chunk in generate_audio_stream(request.text, twin_id):
            yield chunk
    
    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg"
    )


@router.get("/audio/voices")
async def get_voices(user=Depends(get_current_user)):
    """
    List all available ElevenLabs voices.
    """
    voices = list_available_voices()
    
    if not voices:
        raise HTTPException(
            status_code=503, 
            detail="Voice listing unavailable. Check ELEVENLABS_API_KEY."
        )
    
    return {"voices": voices}


@router.get("/audio/settings/{twin_id}")
async def get_voice_settings(twin_id: str, user=Depends(get_current_user)):
    """
    Get current voice settings for a twin.
    """
    verify_twin_ownership(twin_id, user)
    
    settings = get_twin_voice_settings(twin_id)
    return {"settings": settings}


@router.put("/audio/settings/{twin_id}")
async def update_voice_settings(
    twin_id: str, 
    request: VoiceSettingsRequest, 
    user=Depends(get_current_user)
):
    """
    Update voice settings for a twin.
    """
    verify_twin_ownership(twin_id, user)
    
    try:
        # Get current settings
        result = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        settings = result.data.get("settings", {}) if result.data else {}
        
        # Update voice settings
        if "voice" not in settings:
            settings["voice"] = {}
        
        settings["voice"].update({
            "voice_id": request.voice_id,
            "stability": request.stability,
            "similarity_boost": request.similarity_boost,
            "style": request.style,
            "use_speaker_boost": request.use_speaker_boost
        })
        
        # Save
        supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
        
        return {"success": True, "settings": settings["voice"]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")
