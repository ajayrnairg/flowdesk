import api from "./api"

// Types
export type ContentType =
    | "article"
    | "youtube"
    | "github"
    | "twitter"
    | "linkedin"
    | "pdf"

export type KnowledgeStatus =
    | "pending"
    | "processing"
    | "done"
    | "failed"

export interface KnowledgeItemOut {
    id: string
    url: string | null
    title: string | null
    summary: string | null
    content_type: ContentType
    status: KnowledgeStatus
    cover_image_url: string | null
    estimated_read_minutes: number | null
    is_processed: boolean
    created_at: string
}

// Constants (useful for UI mapping)
export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
    article: "Article",
    youtube: "Video",
    github: "GitHub",
    twitter: "Twitter",
    linkedin: "LinkedIn",
    pdf: "PDF",
}

// API functions
export async function getKnowledgeItems(filters?: {
    content_type?: ContentType
    status?: KnowledgeStatus
    q?: string
    signal?: AbortSignal
}): Promise<KnowledgeItemOut[]> {
    const res = await api.get<KnowledgeItemOut[]>("/knowledge", {
        params: {
            content_type: filters?.content_type,
            status: filters?.status,
            q: filters?.q,
        },
        signal: filters?.signal,
    })
    return res.data
}

export async function deleteKnowledgeItem(id: string): Promise<void> {
    await api.delete(`/knowledge/${id}`)
}