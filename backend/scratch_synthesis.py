import asyncio
from services.synthesis_service import synthesise_answer
import logging
logging.basicConfig(level=logging.ERROR)

async def main():
    try:
        res = await synthesise_answer("what is this", [{"item_title": "test", "item_content_type": "article", "chunk_text": "hello world"}])
        print("RESULT:", res)
    except Exception as e:
        print("ERROR:", str(e))

if __name__ == "__main__":
    asyncio.run(main())
