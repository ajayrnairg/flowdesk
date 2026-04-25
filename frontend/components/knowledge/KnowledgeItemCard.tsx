"use client"

import { KnowledgeItemOut } from "@/lib/knowledge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useState } from "react"

interface Props {
    item: KnowledgeItemOut
    onDelete: (id: string) => void
}

function getRelativeTime(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    if (days === 0) return "Today"
    if (days === 1) return "1 day ago"
    return `${days} days ago`
}

const gradientMap = {
    article: "from-blue-500 to-blue-700",
    youtube: "from-red-500 to-red-700",
    github: "from-gray-500 to-gray-700",
    pdf: "from-orange-500 to-orange-700",
    twitter: "from-purple-500 to-purple-700",
    linkedin: "from-purple-500 to-purple-700",
}

export default function KnowledgeItemCard({ item, onDelete }: Props) {
    const [confirm, setConfirm] = useState(false)

    const handleClick = () => {
        if (item.url) {
            window.open(item.url, "_blank")
        }
    }

    return (
        <div 
            onClick={handleClick}
            className="border rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition cursor-pointer group"
        >
            {/* Cover */}
            <div className="relative h-40">
                {item.cover_image_url ? (
                    <img
                        src={item.cover_image_url}
                        className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform"
                    />
                ) : (
                    <div
                        className={`w-full h-full bg-gradient-to-br ${gradientMap[item.content_type]}`}
                    />
                )}

                <Badge className="absolute top-2 right-2 capitalize">
                    {item.content_type}
                </Badge>
            </div>

            {/* Body */}
            <div className="p-4 space-y-2">
                <h3 className="font-semibold line-clamp-2 group-hover:text-primary transition-colors">
                    {item.title || "Untitled"}
                </h3>

                {/* Status */}
                {item.status === "done" && item.summary && (
                    <p className="text-sm text-gray-600 line-clamp-3">
                        {item.summary}
                    </p>
                )}

                {item.status === "processing" || item.status === "pending" ? (
                    <Badge variant="secondary" className="animate-pulse">
                        Processing...
                    </Badge>
                ) : null}

                {item.status === "failed" && (
                    <Badge variant="destructive">Failed to extract</Badge>
                )}

                {/* Footer */}
                <div className="flex justify-between items-center pt-2 text-xs text-gray-500">
                    <span>
                        {item.estimated_read_minutes
                            ? `${item.estimated_read_minutes} min`
                            : ""}
                    </span>

                    <span>{getRelativeTime(item.created_at)}</span>

                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        {!confirm ? (
                            <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setConfirm(true)}
                                className="h-7 text-[10px]"
                            >
                                Delete
                            </Button>
                        ) : (
                            <div className="flex items-center gap-1">
                                <Button
                                    size="sm"
                                    variant="destructive"
                                    onClick={() => onDelete(item.id)}
                                    className="h-7 text-[10px]"
                                >
                                    Sure?
                                </Button>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setConfirm(false)}
                                    className="h-7 text-[10px]"
                                >
                                    No
                                </Button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}