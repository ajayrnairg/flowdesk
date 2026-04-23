import asyncio
import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from services.content_detector import extract_youtube_video_id

async def fetch_youtube_content(url: str) -> dict:
    """
    Fetches YouTube metadata via oEmbed and the transcript via youtube_transcript_api.
    """
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return {"error": "invalid_youtube_url"}

    # 1. Fetch metadata via YouTube's public oEmbed endpoint
    title = ""
    cover_image_url = None
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        async with httpx.AsyncClient() as client:
            resp = await client.get(oembed_url)
            if resp.status_code == 200:
                data = resp.json()
                title = data.get("title", "")
                cover_image_url = data.get("thumbnail_url")
    except Exception as e:
        pass # Non-fatal if oEmbed fails, proceed to transcript

    # 2. Fetch transcript (synchronous library, so we offload to a thread)
    try:
        transcript_list = await asyncio.to_thread(
            YouTubeTranscriptApi.get_transcript, video_id
        )
        
        # Join all text blocks into a single string
        raw_text = " ".join([t.get("text", "") for t in transcript_list])
        
        return {
            "title": title,
            "raw_text": raw_text,
            "cover_image_url": cover_image_url
        }
        
    except Exception as e:
        error_str = str(e).lower()
        if "disabled" in error_str or "found" in error_str or "transcripts" in error_str:
            # Graceful degradation if no subtitles exist
            return {
                "title": title,
                "raw_text": "",
                "cover_image_url": cover_image_url,
                "error": "no_transcript"
            }
        return {"error": str(e)}