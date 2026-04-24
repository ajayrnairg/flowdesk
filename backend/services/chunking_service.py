from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text: str) -> list[str]:
    """
    Splits raw text into overlapping chunks optimized for Gemini embeddings.
    """
    if not text or not text.strip():
        return []

    # 800 chars is roughly 200 tokens (safe for 2048 token limit).
    # 150 char overlap ensures context is not lost at the boundary of chunks.
    chunk_size = 800
    
    if len(text) < chunk_size:
        return [text.strip()]

    # Priorities: paragraph -> newline -> sentence -> word -> character
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    raw_chunks = splitter.split_text(text)
    
    # Post-process: strip whitespace and filter out noise (chunks < 50 chars)
    processed_chunks = []
    for chunk in raw_chunks:
        cleaned_chunk = chunk.strip()
        if len(cleaned_chunk) >= 50:
            processed_chunks.append(cleaned_chunk)
            
    return processed_chunks