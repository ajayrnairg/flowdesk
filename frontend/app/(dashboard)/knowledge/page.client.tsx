"use client"

import { useEffect, useState, useRef } from "react"
import {
    KnowledgeItemOut,
    ContentType,
} from "@/lib/knowledge"
import KnowledgeItemCard from "@/components/knowledge/KnowledgeItemCard"
import AddUrlDialog from "@/components/knowledge/AddUrlDialog"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import { RefreshCw, Mail } from "lucide-react"
import { useApi } from "@/hooks/useApi"

const filters = [
    { label: "All", value: undefined },
    { label: "Articles", value: "article" },
    { label: "Videos", value: "youtube" },
    { label: "GitHub", value: "github" },
    { label: "PDFs", value: "pdf" },
    { label: "Social", value: "twitter" }, // grouped
]

export default function KnowledgePageClient() {
    const { api: getAuthenticatedApi } = useApi()
    const [items, setItems] = useState<KnowledgeItemOut[]>([])
    const [loading, setLoading] = useState(true)
    const [reprocessing, setReprocessing] = useState(false)
    const [sendingDigest, setSendingDigest] = useState(false)
    const [query, setQuery] = useState("")
    const [active, setActive] = useState<string | undefined>(undefined)

    const controllerRef = useRef<AbortController | null>(null)

    const [dragCounter, setDragCounter] = useState(0)
    const isDragging = dragCounter > 0

    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setDragCounter((prev) => prev + 1)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setDragCounter((prev) => prev - 1)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
    }

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setDragCounter(0)

        const files = Array.from(e.dataTransfer.files)
        if (files.length === 0) return

        const file = files[0]
        if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
            toast.error("Only PDF files are supported")
            return
        }

        const formData = new FormData()
        formData.append("file", file)

        try {
            const api = await getAuthenticatedApi()
            await api.post("/knowledge/upload-pdf", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            })
            toast("PDF saved, extracting content...")
            fetchData()
        } catch {
            toast.error("Failed to upload PDF")
        }
    }

    const fetchData = async () => {
        if (controllerRef.current) controllerRef.current.abort()

        const controller = new AbortController()
        controllerRef.current = controller

        setLoading(true)

        try {
            const api = await getAuthenticatedApi()
            const res = await api.get<KnowledgeItemOut[]>("/knowledge", {
                params: {
                    content_type: active as ContentType,
                    q: query,
                },
                signal: controller.signal,
            })
            setItems(res.data)
        } catch (err) {
            if ((err as Error).name !== "CanceledError") {
                toast.error("Failed to load")
            }
        } finally {
            if (controllerRef.current === controller) {
                setLoading(false)
            }
        }
    }

    // debounce search
    useEffect(() => {
        const t = setTimeout(fetchData, 400)
        return () => clearTimeout(t)
    }, [query, active])

    const handleDelete = async (id: string) => {
        try {
            const api = await getAuthenticatedApi()
            await api.delete(`/knowledge/${id}`)
            setItems((prev) => prev.filter((i) => i.id !== id))
        } catch {
            toast.error("Delete failed")
        }
    }

    const handleReprocess = async () => {
        setReprocessing(true)
        try {
            const api = await getAuthenticatedApi()
            const res = await api.post("/knowledge/reprocess")
            toast.success(res.data.message)
            // Refresh the list after a short delay to see if status changed
            setTimeout(fetchData, 1000)
        } catch {
            toast.error("Reprocess request failed")
        } finally {
            setReprocessing(false)
        }
    }

    const handleSendDigest = async () => {
        setSendingDigest(true)
        try {
            const api = await getAuthenticatedApi()
            const res = await api.post("/notifications/send-my-digest")
            if (res.data.status === "sent") {
                toast.success(res.data.message)
            } else {
                toast.info(res.data.message)
            }
        } catch {
            toast.error("Failed to send digest")
        } finally {
            setSendingDigest(false)
        }
    }

    return (
        <div 
            className="p-6 space-y-6 relative min-h-screen"
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
        >
            {isDragging && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-white/80 backdrop-blur-sm border-4 border-dashed border-blue-500 rounded-xl m-4 pointer-events-none">
                    <h2 className="text-3xl font-semibold text-blue-600">Drop your PDF here</h2>
                </div>
            )}

            {/* Header */}
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-semibold">Knowledge Base</h1>
                <div className="flex gap-2">
                    <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={handleSendDigest}
                        disabled={sendingDigest}
                    >
                        <Mail className={`mr-2 h-4 w-4 ${sendingDigest ? "animate-bounce" : ""}`} />
                        {sendingDigest ? "Sending..." : "Send Digest Now"}
                    </Button>
                    <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={handleReprocess}
                        disabled={reprocessing}
                    >
                        <RefreshCw className={`mr-2 h-4 w-4 ${reprocessing ? "animate-spin" : ""}`} />
                        {reprocessing ? "Reprocessing..." : "Reprocess Failed"}
                    </Button>
                    <AddUrlDialog onAdded={fetchData} />
                </div>
            </div>

            {/* Filters */}
            <div className="flex gap-4 items-center">
                <Tabs
                    value={active || "all"}
                    onValueChange={(v) =>
                        setActive(v === "all" ? undefined : v)
                    }
                >
                    <TabsList>
                        {filters.map((f) => (
                            <TabsTrigger
                                key={f.label}
                                value={f.value || "all"}
                            >
                                {f.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </Tabs>

                <Input
                    placeholder="Search..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="max-w-sm"
                />
            </div>

            {/* Content */}
            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <div
                            key={i}
                            className="h-64 bg-gray-200 animate-pulse rounded-xl"
                        />
                    ))}
                </div>
            ) : items.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center space-y-4">
                    <div className="p-4 bg-gray-50 rounded-full">
                        <svg className="w-12 h-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                    </div>
                    <div className="space-y-1">
                        <h3 className="text-lg font-medium text-gray-900">No results for "{query || active}"</h3>
                        <p className="text-sm text-gray-500 max-w-xs mx-auto">
                            We couldn't find any items matching your search or filters.
                        </p>
                    </div>
                    {(query || active) && (
                        <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={() => { setQuery(""); setActive(undefined); }}
                        >
                            Clear search & filters
                        </Button>
                    )}
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {items.map((item) => (
                        <KnowledgeItemCard
                            key={item.id}
                            item={item}
                            onDelete={handleDelete}
                            onUpdate={(updatedItem) => {
                                setItems((prev) => 
                                    prev.map((i) => i.id === updatedItem.id ? updatedItem : i)
                                )
                            }}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}