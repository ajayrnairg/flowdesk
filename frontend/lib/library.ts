import api from "./api"
import { KnowledgeItemOut } from "./knowledge"

// Types
export interface LibraryCollection {
    id: string
    name: string
    color: string | null
    emoji: string | null
    is_default: boolean
    item_count: number
    unread_count: number
    items: KnowledgeItemOut[]
}

export interface LibraryResponse {
    collections: LibraryCollection[]
    total_items: number
    total_unread: number
}

// API

export async function getLibrary(): Promise<LibraryResponse> {
    const res = await api.get<LibraryResponse>("/collections/library/overview")
    return res.data
}

export async function getCollection(collectionId: string): Promise<LibraryCollection> {
    const res = await api.get<LibraryCollection>(`/collections/${collectionId}`)
    return res.data
}

export async function getCollectionItems(
    collectionId: string,
    readStatus?: string
): Promise<KnowledgeItemOut[]> {
    const res = await api.get<KnowledgeItemOut[]>(
        `/collections/${collectionId}/items`,
        {
            params: { read_status: readStatus },
        }
    )
    return res.data
}

export async function updateReadStatus(
    itemId: string,
    readStatus: "READING" | "DONE" | "UNREAD"
): Promise<KnowledgeItemOut> {
    const res = await api.patch<KnowledgeItemOut>(
        `/knowledge/${itemId}/read-status`,
        { read_status: readStatus }
    )
    return res.data
}

export async function createCollection(
    name: string,
    color: string
): Promise<LibraryCollection> {
    const res = await api.post<LibraryCollection>("/collections", {
        name,
        color,
    })
    return res.data
}

export async function deleteCollection(collectionId: string): Promise<void> {
    await api.delete(`/collections/${collectionId}`)
}

export async function addItemToCollection(
    collectionId: string,
    knowledgeItemId: string
): Promise<void> {
    await api.post(`/collections/${collectionId}/items`, {
        knowledge_item_id: knowledgeItemId,
    })
}