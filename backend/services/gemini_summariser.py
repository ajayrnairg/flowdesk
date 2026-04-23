import asyncio
import google.generativeai as genai
from core.config import settings

# Configure SDK globally
genai.configure(api_key=settings.GEMINI_API_KEY)

async def generate_summary(title: str, raw_text: str, content_type: str) -> str:
    """
    Uses Gemini to generate a strict 2-sentence summary of the content.
    Fails safely by returning an empty string.
    """
    if not raw_text:
        return ""
        
    # Free-tier friendly model
    model = genai.GenerativeModel("gemini-1.5-flash")
    
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
        # Generate content is sync; run in thread pool
        response = await asyncio.to_thread(model.generate_content, prompt)
        return response.text.strip()
    except Exception as e:
        # Silent failure on rate limits or API errors
        return ""