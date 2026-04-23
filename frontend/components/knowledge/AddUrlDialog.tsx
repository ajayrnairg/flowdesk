"use client"

import { useState } from "react"
import api from "@/lib/api"
import {
    Dialog,
    DialogTrigger,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

export default function AddUrlDialog({ onAdded }: { onAdded: () => void }) {
    const [url, setUrl] = useState("")
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)

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
            const res = await api.post("/knowledge", { url })

            if (res.data?.status === "use_bookmarklet") {
                toast("Use bookmarklet", {
                    description: "Twitter/LinkedIn detected. Use FlowDesk bookmarklet."
                })
            } else if (res.status === 202) {
                toast("Saving...", {
                    description: "Content will be ready shortly"
                })
            }

            setOpen(false)
            setUrl("")
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

            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Save URL</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                    <Input
                        placeholder="https://..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                    />

                    <Button onClick={handleSubmit} disabled={loading}>
                        {loading ? "Saving..." : "Save"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    )
}