"use client"

import { useEffect, useState } from "react"
import { useApi } from "@/hooks/useApi"
import {
    Dialog,
    DialogTrigger,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

export default function AddUrlDialog({ onAdded }: { onAdded: () => void }) {
    const { api: getAuthenticatedApi } = useApi()
    const [url, setUrl] = useState("")
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)
    const [collections, setCollections] = useState<any[]>([])
    const [selectedCollectionId, setSelectedCollectionId] = useState<string>("")

    useEffect(() => {
        if (open) {
            const fetchCollections = async () => {
                try {
                    const api = await getAuthenticatedApi()
                    const res = await api.get("/collections")
                    setCollections(res.data)
                } catch (error) {
                    console.error("Failed to load collections", error)
                }
            }
            fetchCollections()
        }
    }, [open, getAuthenticatedApi])

    const isValidUrl = (val: string) => {
        try {
            new URL(val)
            return true
        } catch {
            return false
        }
    }

    const handleSubmit = async () => {
        if (!isValidUrl(url)) {
            toast.error("Invalid URL")
            return
        }

        setLoading(true)
        try {
            const api = await getAuthenticatedApi()
            const res = await api.post("/knowledge", { 
                url,
                collection_id: selectedCollectionId || undefined
            })

            if (res.data?.status === "use_bookmarklet") {
                toast("Use bookmarklet", {
                    description: "Twitter/LinkedIn detected. Use FlowDesk bookmarklet."
                })
            } else if (res.status === 202) {
                toast.success("Ingestion started")
            }

            setOpen(false)
            setUrl("")
            setSelectedCollectionId("")
            onAdded()
        } catch {
            toast.error("Failed to save")
        } finally {
            setLoading(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button>Save URL</Button>
            </DialogTrigger>

            <DialogContent className="max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Save URL</DialogTitle>
                    <DialogDescription>
                        Paste a URL to automatically extract content and summarize it.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 pt-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">URL</label>
                        <Input
                            placeholder="https://..."
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">Add to Collection (Optional)</label>
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

                    <Button onClick={handleSubmit} disabled={loading} className="w-full">
                        {loading ? "Saving..." : "Save to Knowledge Base"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}