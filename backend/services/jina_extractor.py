import httpx
from core.config import settings

async def fetch_with_jina(url: str) -> dict:
    """
    Uses Jina AI's Reader API to extract clean Markdown from any article.
    No authentication required.
    """
    timeout = httpx.Timeout(settings.JINA_TIMEOUT_SECONDS)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Jina Reader turns the target URL into an API path
            jina_url = f"https://r.jina.ai/{url}"
            headers = {
                "Accept": "application/json",
                "X-Return-Format": "markdown"
            }
            
            response = await client.get(jina_url, headers=headers)
            
            if response.status_code != 200:
                return {"error": f"http_{response.status_code}"}
                
            json_data = response.json()
            data = json_data.get("data", {})
            
            return {
                "title": data.get("title", ""),
                "raw_text": data.get("content", ""),
                # Jina sometimes extracts an image from OG tags, grab it if available
                "cover_image_url": data.get("image", None) 
            }
            
    except httpx.TimeoutException:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}

def estimate_read_minutes(text: str) -> int:
    """Estimates reading time assuming 200 words per minute."""
    if not text:
        return 1
    word_count = len(text.split())
    return max(1, round(word_count / 200))