import edge_tts
import os
import uuid
import asyncio
from django.conf import settings

AUDIO_DIR = os.path.join(settings.BASE_DIR, 'temp_audio')

if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR, exist_ok=True)

async def generate_speech(text, voice="en-US-AvaNeural"):
    """
    Generates an MP3 file from text using edge-tts.
    Returns the absolute path to the generated file.
    """
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filepath)
    
    return filepath

def cleanup_old_audio():
    """
    Optional: Clean up files older than X minutes/hours
    For now, just a placeholder if needed for startup or periodic tasks.
    """
    for f in os.listdir(AUDIO_DIR):
        try:
            os.remove(os.path.join(AUDIO_DIR, f))
        except:
            pass
