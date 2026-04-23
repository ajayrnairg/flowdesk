from urllib.parse import urlparse, parse_qs

def detect_content_type(url: str) -> str:
    """
    Parses the domain to classify the content type.
    Defaults to 'article' for standard web pages.
    """
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        
        if "youtube.com" in netloc or "youtu.be" in netloc:
            return "youtube"
        if "github.com" in netloc:
            return "github"
        if "twitter.com" in netloc or "x.com" in netloc:
            return "twitter"
        if "linkedin.com" in netloc:
            return "linkedin"
            
        return "article"
    except Exception:
        return "article"

def extract_youtube_video_id(url: str) -> str | None:
    """
    Extracts the video ID from both standard and shortened YouTube URLs.
    """
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        
        # Handle https://youtu.be/ID
        if "youtu.be" in netloc:
            return parsed.path.lstrip("/")
            
        # Handle https://www.youtube.com/watch?v=ID
        if "youtube.com" in netloc:
            qs = parse_qs(parsed.query)
            return qs.get("v", [None])[0]
            
        return None
    except Exception:
        return None