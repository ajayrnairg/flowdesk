# From existing files...
from .content_detector import detect_content_type, extract_youtube_video_id
from .jina_extractor import fetch_with_jina
from .youtube_extractor import fetch_youtube_content
from .github_extractor import fetch_github_content
from .pdf_extractor import extract_pdf_text
from .gemini_summariser import generate_summary
from .ingestion_orchestrator import run_ingestion_pipeline, run_summary_only

# New RAG services
from .chunking_service import chunk_text
from .embedding_service import embed_texts, embed_query
from .rag_indexer import index_knowledge_item
from .search_service import semantic_search
from .synthesis_service import synthesise_answer

__all__ = [
    # Content detection & extraction
    "detect_content_type",
    "extract_youtube_video_id",
    "fetch_with_jina",
    "fetch_youtube_content",
    "fetch_github_content",
    "extract_pdf_text",
    
    # Orchestration & LLM Summaries
    "generate_summary",
    "run_ingestion_pipeline",
    "run_summary_only",
    
    # RAG Pipeline
    "chunk_text",
    "embed_texts",
    "embed_query",
    "index_knowledge_item",
    "semantic_search",
    "synthesise_answer",
]