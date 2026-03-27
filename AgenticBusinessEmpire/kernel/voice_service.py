import logging
import httpx
import os
import asyncio
from AgenticBusinessEmpire.core import config

logger = logging.getLogger("agenticbusinessempire.voice")

class VoiceService:
    """
    AgenticBusinessEmpire Local Voice Interface.
    Handles Speech-to-Text (STT) and Text-to-Speech (TTS) via local engines.
    """
    
    def __init__(self):
        self.stt_url = config.STT_ENDPOINT
        self.tts_url = config.TTS_ENDPOINT
        self.engine = config.VOICE_ENGINE

    async def vocalize(self, text: str, output_path: str = None) -> dict:
        """Convert text to speech locally."""
        if not output_path:
            output_path = os.path.join(config.RUNTIME_DIR, "audio", f"voice_{int(asyncio.get_event_loop().time())}.wav")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
        logger.info("[Voice] Vocalizing via %s: %s", self.engine, text[:30])
        
        async with httpx.AsyncClient() as client:
            try:
                # Piper or Coqui local server request
                resp = await client.post(self.stt_url, json={"text": text, "engine": self.engine})
                if resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return {"status": "success", "path": output_path}
                else:
                    return {"status": "error", "message": f"TTS Failure: {resp.status_code}"}
            except Exception as e:
                logger.error("[Voice] TTS Exception: %s", e)
                return {"status": "error", "message": str(e)}

    async def listen(self, audio_data: bytes) -> dict:
        """Convert speech to text locally using Whisper Engine."""
        logger.info("[Voice] Listening to audio stream...")
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(self.stt_url, content=audio_data)
                if resp.status_code == 200:
                    data = resp.json()
                    return {"status": "success", "text": data.get("text", "")}
                else:
                    return {"status": "error", "message": f"STT Failure: {resp.status_code}"}
            except Exception as e:
                logger.error("[Voice] STT Exception: %s", e)
                return {"status": "error", "message": str(e)}

# Singleton instance for kernel use
voice_service = VoiceService()
