import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

async def synthesise_answer(query: str, chunks: list[dict]) -> str:
    """
    Generates a conversational answer strictly based on the retrieved RAG chunks.
    """
    if not chunks:
        return (
            "I could not find relevant information in your knowledge base for this query. "
            "Try saving more content related to this topic."
        )

    # Build the context string linking sources to their chunk text
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"[Source {i}: {chunk['item_title']} ({chunk['item_content_type']})]\n"
            f"{chunk['chunk_text']}"
        )
    
    context = "\n\n---\n\n".join(context_parts)
    
    prompt = f"""You are a personal knowledge assistant. Answer the user's query using
ONLY the sources provided below. Do not use any outside knowledge.

If the sources do not contain enough information to answer, say so clearly.

At the end of your answer, list which sources you used as [Source 1], [Source 2] etc.
Keep your answer concise — 3 to 5 sentences unless the query requires more detail.

USER QUERY: {query}

SOURCES:
{context}

ANSWER:"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        # Generate the response asynchronously using the provided context
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return "Could not generate an answer. Here are the relevant sources:"