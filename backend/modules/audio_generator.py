# backend/modules/audio_generator.py
"""Audio Generator: Text-to-Speech using ElevenLabs.

Provides functions to convert text responses into audio streams.
Supports voice cloning and style configuration from twin settings.
"""

import os
import io
from typing import Optional, AsyncGenerator, Dict, Any
import logging

from modules.clients import get_elevenlabs_client
from modules.observability import supabase

logger = logging.getLogger(__name__)

# Default voice settings
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" - a default ElevenLabs voice
DEFAULT_MODEL_ID = "eleven_monolingual_v1"


def get_twin_voice_settings(twin_id: str) -> Dict[str, Any]:
    """
    Get voice settings for a specific twin.
    Returns voice_id, model_id, and style settings.
    """
    try:
        result = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
        if result.data:
            settings = result.data.get("settings", {})
            voice_settings = settings.get("voice", {})
            return {
                "voice_id": voice_settings.get("voice_id", DEFAULT_VOICE_ID),
                "model_id": voice_settings.get("model_id", DEFAULT_MODEL_ID),
                "stability": voice_settings.get("stability", 0.5),
                "similarity_boost": voice_settings.get("similarity_boost", 0.75),
                "style": voice_settings.get("style", 0.0),
                "use_speaker_boost": voice_settings.get("use_speaker_boost", True)
            }
    except Exception as e:
        logger.error(f"Error fetching twin voice settings: {e}")
    
    return {
        "voice_id": DEFAULT_VOICE_ID,
        "model_id": DEFAULT_MODEL_ID,
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True
    }


def generate_audio(text: str, twin_id: str = None) -> Optional[bytes]:
    """
    Generate audio from text using ElevenLabs TTS.
    
    Args:
        text: Text to convert to speech
        twin_id: Optional twin ID to use custom voice settings
    
    Returns:
        Audio bytes (MP3 format) or None if generation fails
    """
    client = get_elevenlabs_client()
    if not client:
        logger.warning("ElevenLabs client not available")
        return None
    
    # Get voice settings
    if twin_id:
        settings = get_twin_voice_settings(twin_id)
    else:
        settings = {
            "voice_id": DEFAULT_VOICE_ID,
            "model_id": DEFAULT_MODEL_ID,
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    
    try:
        # Generate audio
        audio = client.generate(
            text=text,
            voice=settings["voice_id"],
            model=settings["model_id"],
            voice_settings={
                "stability": settings.get("stability", 0.5),
                "similarity_boost": settings.get("similarity_boost", 0.75)
            }
        )
        
        # Collect audio bytes
        audio_bytes = b"".join(audio)
        return audio_bytes
        
    except Exception as e:
        logger.error(f"Error generating audio: {e}")
        return None


async def generate_audio_stream(text: str, twin_id: str = None) -> AsyncGenerator[bytes, None]:
    """
    Stream audio generation for real-time playback.
    
    Args:
        text: Text to convert to speech
        twin_id: Optional twin ID to use custom voice settings
    
    Yields:
        Audio chunks (bytes)
    """
    client = get_elevenlabs_client()
    if not client:
        logger.warning("ElevenLabs client not available")
        return
    
    # Get voice settings
    if twin_id:
        settings = get_twin_voice_settings(twin_id)
    else:
        settings = {
            "voice_id": DEFAULT_VOICE_ID,
            "model_id": DEFAULT_MODEL_ID,
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    
    try:
        # Generate streaming audio
        audio_stream = client.generate(
            text=text,
            voice=settings["voice_id"],
            model=settings["model_id"],
            stream=True,
            voice_settings={
                "stability": settings.get("stability", 0.5),
                "similarity_boost": settings.get("similarity_boost", 0.75)
            }
        )
        
        for chunk in audio_stream:
            yield chunk
            
    except Exception as e:
        logger.error(f"Error streaming audio: {e}")
        return


def list_available_voices() -> list:
    """
    List all available voices from ElevenLabs.
    Useful for voice selection UI.
    """
    client = get_elevenlabs_client()
    if not client:
        return []
    
    try:
        voices = client.voices.get_all()
        return [
            {
                "voice_id": v.voice_id,
                "name": v.name,
                "category": getattr(v, "category", "unknown"),
                "description": getattr(v, "description", "")
            }
            for v in voices.voices
        ]
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        return []


async def clone_voice(twin_id: str, audio_files: list, voice_name: str = None) -> Optional[str]:
    """
    Clone a user's voice from audio samples.
    
    Args:
        twin_id: Twin ID to associate the voice with
        audio_files: List of audio file paths or bytes
        voice_name: Optional custom name for the voice
    
    Returns:
        Voice ID of the cloned voice, or None if cloning fails
    """
    client = get_elevenlabs_client()
    if not client:
        return None
    
    try:
        # Create voice clone
        voice = client.clone(
            name=voice_name or f"Twin-{twin_id[:8]}",
            files=audio_files,
            description=f"Cloned voice for twin {twin_id}"
        )
        
        # Store voice_id in twin settings
        try:
            current_settings = supabase.table("twins").select("settings").eq("id", twin_id).single().execute()
            settings = current_settings.data.get("settings", {}) if current_settings.data else {}
            
            if "voice" not in settings:
                settings["voice"] = {}
            settings["voice"]["voice_id"] = voice.voice_id
            settings["voice"]["cloned"] = True
            
            supabase.table("twins").update({"settings": settings}).eq("id", twin_id).execute()
        except Exception as e:
            logger.error(f"Error saving voice settings: {e}")
        
        return voice.voice_id
        
    except Exception as e:
        logger.error(f"Error cloning voice: {e}")
        return None
