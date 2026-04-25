import api from "./api"

// Source type
export interface SearchSource {
    knowledge_item_id: string
    title: string | null
    content_type:
    | "article"
    | "youtube"
    | "github"
    | "twitter"
    | "linkedin"
    | "pdf"
    url: string | null
    chunk_excerpt: string
    similarity_score: number
}

// Full response type
export interface SearchResponse {
    query: string
    answer: string
    sources: SearchSource[]
    cached: boolean
    took_ms: number
}

// Search API
export async function searchKnowledge(
    query: string,
    signal?: AbortSignal
): Promise<SearchResponse> {
    const res = await api.post<SearchResponse>("/search", { query }, { signal })
    return res.data
}

// Reindex API
export async function reindexItem(itemId: string): Promise<void> {
    await api.get(`/search/reindex/${itemId}`)
}