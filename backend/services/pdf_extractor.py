import io
import asyncio
import pdfplumber

async def extract_pdf_text(file_bytes: bytes, filename: str) -> dict:
    """
    Extracts raw text from PDF bytes. Rejects files larger than 10MB.
    Runs pdfplumber synchronously inside a worker thread.
    """
    # Max file size check: 10MB
    if len(file_bytes) > 10 * 1024 * 1024:
        return {"error": "file_too_large"}

    def _sync_extract():
        text_blocks = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text_blocks.append(extracted)
        
        # Clean up excessive whitespace
        raw_text = "\n".join(text_blocks).strip()
        return raw_text, page_count

    try:
        # Strip the .pdf extension for a cleaner default title
        title = filename[:-4] if filename.lower().endswith('.pdf') else filename
        
        raw_text, page_count = await asyncio.to_thread(_sync_extract)
        
        return {
            "title": title,
            "raw_text": raw_text,
            "page_count": page_count
        }
    except Exception as e:
        return {"error": str(e)}