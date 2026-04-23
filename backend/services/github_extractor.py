import httpx
import base64
from urllib.parse import urlparse
from core.config import settings

async def fetch_github_content(url: str) -> dict:
    """
    Uses the GitHub REST API to fetch repo metadata and decode the README.
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    # Needs at least owner and repo
    if len(path_parts) < 2:
        return {"error": "invalid_github_url"}
        
    owner, repo = path_parts[0], path_parts[1]
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"
        
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch Repository Metadata
            repo_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}", 
                headers=headers
            )
            
            if repo_resp.status_code != 200:
                return {"error": f"github_api_repo_{repo_resp.status_code}"}
                
            repo_data = repo_resp.json()
            title = repo_data.get("full_name", f"{owner}/{repo}")
            cover_image_url = repo_data.get("owner", {}).get("avatar_url")
            
            # 2. Fetch README Content
            readme_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme", 
                headers=headers
            )
            
            raw_text = ""
            if readme_resp.status_code == 200:
                readme_data = readme_resp.json()
                content_b64 = readme_data.get("content", "")
                # GitHub returns base64 encoded file content
                raw_text = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
                
            return {
                "title": title,
                "raw_text": raw_text,
                "cover_image_url": cover_image_url
            }
            
    except Exception as e:
        return {"error": str(e)}