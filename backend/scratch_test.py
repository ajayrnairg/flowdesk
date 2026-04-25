import asyncio
from google import genai
from core.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def main():
    res = await client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL, 
        contents=['hi', 'there'], 
        config={'task_type': 'RETRIEVAL_DOCUMENT', 'output_dimensionality': 768}
    )
    for e in res.embeddings:
        print(len(e.values))

if __name__ == "__main__":
    asyncio.run(main())
