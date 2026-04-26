"use client"

import { KnowledgeItemOut } from "@/lib/knowledge"
import { useApi } from "@/hooks/useApi"
import { useState } from "react"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { MoreVertical } from "lucide-react"
import { toast } from "sonner"

const gradients = {
    article: "from-blue-500 to-blue-700",
    youtube: "from-red-500 to-red-700",
    github: "from-gray-500 to-gray-700",
    pdf: "from-orange-500 to-orange-700",
    twitter: "from-purple-500 to-purple-700",
    linkedin: "from-blue-600 to-blue-800",
}

export default function LibraryItemCard({ item }: { item: KnowledgeItemOut }) {
    const { api: getAuthenticatedApi } = useApi()
    const [localItem, setLocalItem] = useState(item)

    const handleStatus = async (status: "READING" | "DONE" | "UNREAD") => {
        const prev = localItem.read_status
        setLocalItem(prevItem => ({ ...prevItem, read_status: status }))

        try {
            const api = await getAuthenticatedApi()
            await api.patch(`/collections/items/${item.id}`, { read_status: status })
        } catch (error) {
            setLocalItem(prevItem => ({ ...prevItem, read_status: prev }))
            toast.error("Failed to update status")
        }
    }

    const handleDelete = async (id: string) => {
        try {
            const api = await getAuthenticatedApi()
            await api.delete(`/knowledge/${id}`)
            // Note: setItems would need to be passed as a prop or handled via context to refresh list
        } catch {
            toast.error("Delete failed")
        }
    }

    const handleClick = () => {
        if (localItem.url) {
            window.open(localItem.url, "_blank")
        }

        if (localItem.read_status === "UNREAD") {
            handleStatus("READING")
        }
    }

    const statusDot = {
        UNREAD: "bg-blue-500",
        READING: "bg-yellow-400",
        DONE: "bg-green-500",
    }

    return (
        <div className="w-44 group">
            <div onClick={handleClick} className="cursor-pointer space-y-2">
                {/* Image */}
                <div className="relative">
                    {localItem.cover_image_url ? (
                        <img
                            src={localItem.cover_image_url}
                            className="w-full h-28 object-cover rounded-lg transition-transform group-hover:scale-[1.02]"
                        />
                    ) : (
                        <div
                            className={`w-full h-28 rounded-lg bg-gradient-to-br transition-transform group-hover:scale-[1.02] ${gradients[localItem.content_type]
                                }`}
                        />
                    )}

                    {/* Status */}
                    <div
                        className={`absolute top-2 right-2 w-3 h-3 rounded-full border-2 border-white ${statusDot[localItem.read_status]}`}
                    />
                </div>

                {/* Info */}
                <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium line-clamp-2 leading-tight group-hover:text-primary transition-colors">
                            {localItem.title || "Untitled"}
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex justify-between items-center -mt-4 relative z-10">
                <div className="flex-1 min-w-0">
                    {localItem.estimated_read_minutes && (
                        <p className="text-xs text-muted-foreground">
                            {localItem.estimated_read_minutes} min
                        </p>
                    )}
                </div>

                {/* Menu */}
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button 
                            size="icon" 
                            variant="ghost" 
                            className="h-8 w-8 -mr-2 hover:bg-muted"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <MoreVertical className="w-4 h-4" />
                        </Button>
                    </DropdownMenuTrigger>

                    <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleStatus("READING")}>
                            Mark as Reading
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleStatus("DONE")}>
                            Mark as Done
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleStatus("UNREAD")}>
                            Mark as Unread
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    )
}