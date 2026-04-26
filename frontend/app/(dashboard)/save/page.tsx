"use client"

import { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useApi } from "@/hooks/useApi"
import { LibraryCollection } from "@/lib/library"
import { KnowledgeItemOut } from "@/lib/knowledge"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
} from "@/components/ui/select"
import { toast } from "sonner"

function SaveForm() {
    const { api: getAuthenticatedApi } = useApi()
    const router = useRouter()
    const params = useSearchParams()
    const pathname = usePathname()

    const [loading, setLoading] = useState(false)
    const [success, setSuccess] = useState(false)
    const [collections, setCollections] = useState<LibraryCollection[]>([])
    const [selectedCollectionId, setSelectedCollectionId] = useState<string>("")

    const url = params.get("url") || ""
    const titleParam = params.get("title") || ""
    const textParam = params.get("text") || ""
    const type = params.get("type") || "article"

    const [title, setTitle] = useState(titleParam)
    const [selectedText, setSelectedText] = useState(textParam)

    // Fetch Collections
    useEffect(() => {
        const fetch = async () => {
            try {
                const api = await getAuthenticatedApi()
                const res = await api.get("/collections")
                setCollections(res.data)
            } catch {
                toast.error("Failed to load collections")
            }
        }
        fetch()
    }, [getAuthenticatedApi])

    const handleSave = async () => {
        setLoading(true)

        try {
            const api = await getAuthenticatedApi()
            if (!selectedText.trim()) {
                // Let backend extract YouTube/GitHub/Articles automatically
                await api.post("/knowledge", { 
                    url,
                    collection_id: selectedCollectionId || undefined
                })
            } else {
                // Save highlighted text directly
                await api.post("/knowledge/bookmarklet", {
                    url,
                    page_title: title,
                    selected_text: selectedText,
                    content_type: type,
                    collection_id: selectedCollectionId || undefined
                })
            }

            setSuccess(true)
        } catch (err) {
            toast.error("Failed to save")
        } finally {
            setLoading(false)
        }
    }

    return (
        <CardContent className="space-y-4">
            {/* URL */}
            <div>
                <p className="text-sm text-gray-500 mb-1">URL</p>
                <input
                    value={url}
                    readOnly
                    className="w-full border rounded px-3 py-2 text-sm bg-gray-100"
                />
            </div>

            {/* Title */}
            <div>
                <p className="text-sm text-gray-500 mb-1">Title</p>
                <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full border rounded px-3 py-2 text-sm"
                />
            </div>

            {/* Type */}
            <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Content Type</span>
                <Badge>{type}</Badge>
            </div>

            {/* Selected text */}
            <div>
                <p className="text-sm text-gray-500 mb-1">Selected Text</p>
                <Textarea
                    value={selectedText}
                    onChange={(e) => setSelectedText(e.target.value)}
                    className="max-h-[200px] overflow-y-auto"
                    placeholder="Enter or edit the selected text..."
                />
            </div>

            {/* Collection selector */}
            <div>
                <p className="text-sm text-gray-500 mb-1">Collection (Optional)</p>
                <Select value={selectedCollectionId} onValueChange={setSelectedCollectionId}>
                    <SelectTrigger>
                        <SelectValue placeholder="Select a collection..." />
                    </SelectTrigger>
                    <SelectContent>
                        {collections.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                                <div className="flex items-center gap-2">
                                    <div 
                                        className="w-2 h-2 rounded-full" 
                                        style={{ backgroundColor: c.color || "gray" }}
                                    />
                                    {c.name}
                                </div>
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Save button */}
            {!success ? (
                <Button onClick={handleSave} disabled={loading} className="w-full">
                    {loading ? "Saving..." : "Save to Knowledge Base"}
                </Button>
            ) : (
                <p className="text-green-600 text-sm font-medium text-center">
                    ✅ Saved! You can close this tab now.
                </p>
            )}
        </CardContent>
    )
}

export default function SavePage() {
    return (
        <div className="flex items-center justify-center min-h-screen p-4">
            <Card className="w-full max-w-lg">
                <CardHeader>
                    <CardTitle>Save to FlowDesk</CardTitle>
                </CardHeader>
                <Suspense fallback={<CardContent>Loading...</CardContent>}>
                    <SaveForm />
                </Suspense>
            </Card>
        </div>
    )
}