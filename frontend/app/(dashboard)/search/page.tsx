"use client"

import { useEffect, useRef, useState } from "react"
import { searchKnowledge, SearchResponse } from "@/lib/search"
import SearchInput from "@/components/search/SearchInput"
import SourceCard from "@/components/search/SourceCard"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Sparkles } from "lucide-react"
import { toast } from "sonner"

export default function SearchPage() {

    const [query, setQuery] = useState("")
    const [result, setResult] = useState<SearchResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [history, setHistory] = useState<string[]>([])
    // Track the in-flight request so we can abort it on a new submission
    const abortRef = useRef<AbortController | null>(null)

    // Load history
    useEffect(() => {
        const stored = localStorage.getItem("search_history")
        if (stored) setHistory(JSON.parse(stored))
    }, [])

    const saveHistory = (q: string) => {
        const updated = [q, ...history.filter((h) => h !== q)].slice(0, 5)
        setHistory(updated)
        localStorage.setItem("search_history", JSON.stringify(updated))
    }

    const handleSearch = async (q: string) => {
        if (!q) return

        // Cancel any in-flight request before starting a new one
        abortRef.current?.abort()
        const controller = new AbortController()
        abortRef.current = controller

        setQuery(q)
        setLoading(true)
        setResult(null)

        try {
            const res = await searchKnowledge(q, controller.signal)
            setResult(res)
            saveHistory(q)
        } catch (err) {
            // Ignore aborted requests (user started a new search)
            if (err instanceof Error && err.name === "CanceledError") return
            toast.error("Search failed. Please try again.")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="p-6 space-y-8">
            {/* Search */}
            <SearchInput onSearch={handleSearch} loading={loading} />

            {/* History */}
            {history.length > 0 && (
                <div className="flex gap-2 flex-wrap justify-center">
                    {history.map((h) => (
                        <Button
                            key={h}
                            variant="secondary"
                            size="sm"
                            onClick={() => handleSearch(h)}
                        >
                            {h}
                        </Button>
                    ))}
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="space-y-4">
                    <Skeleton className="h-32 w-full rounded-xl" />
                    <div className="flex gap-4">
                        <Skeleton className="h-40 w-64" />
                        <Skeleton className="h-40 w-64" />
                        <Skeleton className="h-40 w-64" />
                    </div>
                </div>
            )}

            {/* Result */}
            {result && (
                <>
                    {/* Empty state: no sources returned */}
                    {result.sources.length === 0 ? (
                        <div className="text-center space-y-4">
                            <p className="text-gray-500">
                                No relevant content found.
                            </p>
                            <Button asChild>
                                <a href="/knowledge">Save more content</a>
                            </Button>
                        </div>
                    ) : (
                        <>
                            {/* Answer */}
                            <div className="relative border rounded-xl p-6 bg-white shadow-sm">
                                <Sparkles className="absolute top-4 left-4 w-5 h-5 text-purple-500" />

                                <p className="pl-8">{result.answer}</p>

                                <div className="flex gap-2 mt-4 text-sm text-gray-500">
                                    <span>Answered in {result.took_ms}ms</span>
                                    {result.cached && (
                                        <Badge variant="secondary">⚡ Cached</Badge>
                                    )}
                                </div>
                            </div>

                            {/* Sources */}
                            <div className="space-y-3">
                                <h2 className="font-semibold">
                                    Sources used ({result.sources.length})
                                </h2>

                                <div className="flex gap-4 overflow-x-auto pb-2">
                                    {result.sources.map((s) => (
                                        <SourceCard
                                            key={s.knowledge_item_id}
                                            source={s}
                                        />
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </>
            )}

            {/* Footer */}
            <p className="text-center text-xs text-gray-400 pt-6">
                Answers are generated from your saved content only.
            </p>
        </div>
    )
}