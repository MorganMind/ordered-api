from openai import AsyncOpenAI
import asyncio
from typing import BinaryIO
import tempfile
import os

class TranscriptionService:
    ALLOWED_FORMATS = ['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm']
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB limit for Whisper API

    def __init__(self):
        self.openai_client = AsyncOpenAI()
        
    async def transcribe_chunk(self, audio_file: BinaryIO) -> str:
        """
        Transcribe a single chunk of audio using Whisper API
        
        Args:
            audio_file: File-like object containing audio data
        Returns:
            str: Transcribed text
        """
        try:
            # Create a temporary file to store the audio chunk
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                # Write the audio data to the temp file
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)
                temp_file.flush()

                # Check file size
                file_size = os.path.getsize(temp_file.name)
                if file_size > self.MAX_FILE_SIZE:
                    raise ValueError(f"Audio file too large: {file_size} bytes")
                print(f"Audio file size: {temp_file.name} {file_size} bytes")
                # Send to Whisper API
                with open(temp_file.name, 'rb') as audio:
                    response = await self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        response_format="text",
                        language="en"  # You can make this configurable
                    )

            # Clean up temp file
            os.unlink(temp_file.name)
            return response

        except Exception as e:
            print(f"Transcription error: {e}")
            raise

    @staticmethod
    def validate_audio_format(filename: str) -> bool:
        """Check if the audio file format is supported"""
        ext = filename.split('.')[-1].lower()
        return ext in TranscriptionService.ALLOWED_FORMATS 