"use client"

import { useState } from "react"
import { createCollection } from "@/lib/library"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

const colors = [
    "#3B82F6",
    "#EF4444",
    "#10B981",
    "#F59E0B",
    "#8B5CF6",
    "#EC4899",
    "#06B6D4",
    "#6B7280",
]

export default function CreateCollectionDialog({ onCreated }: { onCreated: () => void }) {
    const [name, setName] = useState("")
    const [color, setColor] = useState(colors[0])

    const handleSubmit = async () => {
        if (!name.trim()) {
            toast.error("Name required")
            return
        }

        await createCollection(name, color)
        onCreated()
    }

    return (
        <Dialog>
            <DialogTrigger asChild>
                <Button>New Collection</Button>
            </DialogTrigger>

            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Create Collection</DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Collection Name</label>
                        <Input
                            placeholder="e.g. Research Papers, UI Inspiration..."
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">Theme Color</label>
                        <div className="flex gap-2 flex-wrap">
                            {colors.map((c) => (
                                <div
                                    key={c}
                                    onClick={() => setColor(c)}
                                    className={`w-8 h-8 rounded-full cursor-pointer transition-all hover:scale-110 ${color === c ? "ring-2 ring-offset-2 ring-slate-900 scale-110" : ""
                                        }`}
                                    style={{ background: c }}
                                />
                            ))}
                        </div>
                    </div>

                    <div className="pt-2">
                        <label className="text-sm font-medium mb-2 block">Preview</label>
                        <div
                            className="p-3 rounded-lg border-l-4 bg-muted/30"
                            style={{ borderColor: color }}
                        >
                            <h3 className="font-semibold">{name || "Collection Name"}</h3>
                            <p className="text-xs text-muted-foreground">0 items • 0 unread</p>
                        </div>
                    </div>
                </div>

                <Button onClick={handleSubmit} className="w-full">Create Collection</Button>
            </DialogContent>
        </Dialog>
    )
}