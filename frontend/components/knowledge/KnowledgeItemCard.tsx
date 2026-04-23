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

    const content = (
        <div className="border rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition">
            {/* Cover */}
            <div className="relative h-40">
                {item.cover_image_url ? (
                    <img
                        src={item.cover_image_url}
                        className="w-full h-full object-cover"
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
                <h3 className="font-semibold line-clamp-2">
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

                    {!confirm ? (
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setConfirm(true)}
                        >
                            Delete
                        </Button>
                    ) : (
                        <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => onDelete(item.id)}
                        >
                            Sure?
                        </Button>
                    )}
                </div>
            </div>
        </div>
    )

    if (item.url) {
        return (
            <a href={item.url} target="_blank" rel="noopener noreferrer">
                {content}
            </a>
        )
    }

    return content
}