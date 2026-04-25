"use client"

import { SearchSource } from "@/lib/search"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

const typeStyles = {
    article: "border-blue-500",
    youtube: "border-red-500",
    github: "border-gray-500",
    pdf: "border-orange-500",
    twitter: "border-purple-500",
    linkedin: "border-blue-600",
}

function getScoreColor(score: number) {
    if (score > 0.8) return "bg-green-500"
    if (score > 0.6) return "bg-yellow-500"
    return "bg-red-500"
}

export default function SourceCard({ source }: { source: SearchSource }) {
    const percentage = Math.round(source.similarity_score * 100)

    return (
        <div
            className={`min-w-[280px] border-l-4 ${typeStyles[source.content_type]
                } bg-white p-4 rounded-xl shadow-sm`}
        >
            <div className="space-y-2">
                <Badge className="capitalize">{source.content_type}</Badge>

                <h4 className="font-medium line-clamp-2">
                    {source.title || "Untitled"}
                </h4>

                <p className="text-sm text-gray-500 italic line-clamp-3">
                    {source.chunk_excerpt}
                </p>

                {/* Score bar */}
                <div>
                    <div className="w-full h-2 bg-gray-200 rounded">
                        <div
                            className={`h-2 rounded ${getScoreColor(
                                source.similarity_score
                            )}`}
                            style={{ width: `${percentage}%` }}
                        />
                    </div>
                    <p className="text-xs mt-1">{percentage}% match</p>
                </div>

                {source.url && (
                    <Button
                        size="sm"
                        variant="outline"
                        asChild
                    >
                        <a href={source.url} target="_blank">
                            Open source
                        </a>
                    </Button>
                )}
            </div>
        </div>
    )
}