from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
import asyncio
import json
from transcription.services.transcription_service import TranscriptionService

@csrf_exempt
async def transcribe_stream_view(request):
    """Handle streaming audio transcription"""
    if request.method == "POST":
        # Get the audio chunk from the request
        audio_chunk = request.FILES.get('audio')
        if not audio_chunk:
            return JsonResponse({"error": "No audio data"}, status=400)
            
        transcription_service = TranscriptionService()
        
        # Validate audio format
        if not transcription_service.validate_audio_format(audio_chunk.name):
            return JsonResponse(
                {"error": f"Unsupported audio format. Supported formats: {', '.join(TranscriptionService.ALLOWED_FORMATS)}"},
                status=400
            )

        async def event_stream():
            try:
                # Process the audio chunk
                transcribed_text = await transcription_service.transcribe_chunk(audio_chunk)
                
                # Send the transcribed text
                if transcribed_text:
                    yield f"data: {json.dumps({'text': transcribed_text})}\n\n"
                else:
                    yield f"data: {json.dumps({'text': ''})}\n\n"
                    
            except ValidationError as e:
                yield f"event: error\ndata: {str(e)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: {str(e)}\n\n"

        return StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # Important for nginx
            }
        )
    
    return JsonResponse({"error": "Method not allowed"}, status=405) 