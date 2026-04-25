import asyncio
from google import genai
from core.config import settings

# Initialize client globally
client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def generate_summary(title: str, raw_text: str, content_type: str) -> str:
    """
    Uses Gemini to generate a strict 2-sentence summary of the content.
    Fails safely by returning an empty string.
    """
    if not raw_text:
        return ""
        
    
    # Truncate to first 3000 chars to save tokens and ensure fast latency
    truncated_text = raw_text[:3000]
    
    prompt = (
        f"You are summarising a saved {content_type} for a personal knowledge base.\n"
        f"Title: {title}\n"
        f"Content (truncated): {truncated_text}\n"
        f"Write exactly 2 sentences summarising the key idea. "
        f"Be specific — mention the main concept or technology discussed. "
        f"Return only the 2 sentences, no preamble."
    )
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        # Silent failure on rate limits or API errors
        return ""