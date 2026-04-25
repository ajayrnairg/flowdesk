"use client"

import { useEffect, useState } from "react"
import { getLibrary, LibraryCollection } from "@/lib/library"
import LibraryItemCard from "@/components/library/LibraryItemCard"
import CreateCollectionDialog from "@/components/library/CreateCollectionDialog"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { BookOpen, Filter, ChevronRight } from "lucide-react"
import Link from "next/link"

export default function LibraryPage() {
    const [collections, setCollections] = useState<LibraryCollection[]>([])
    const [loading, setLoading] = useState(true)
    const [readingOnly, setReadingOnly] = useState(false)

    const fetchLibrary = async () => {
        try {
            const data = await getLibrary()
            setCollections(data.collections)
        } catch {
            toast.error("Failed to load library")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchLibrary()
    }, [])

    const unreadTotal = collections.reduce(
        (sum, c) => sum + c.unread_count,
        0
    )

    return (
        <div className="p-6 space-y-8 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b pb-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg">
                        <BookOpen className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Library</h1>
                        <p className="text-muted-foreground text-sm">
                            Organize and track your reading progress
                        </p>
                    </div>
                    {unreadTotal > 0 && (
                        <Badge variant="secondary" className="h-6 px-2 text-xs font-semibold">
                            {unreadTotal} unread
                        </Badge>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant={readingOnly ? "default" : "outline"}
                        size="sm"
                        onClick={() => setReadingOnly(!readingOnly)}
                        className="gap-2"
                    >
                        <Filter className="w-4 h-4" />
                        {readingOnly ? "Reading Only" : "Show All"}
                    </Button>

                    <CreateCollectionDialog onCreated={fetchLibrary} />
                </div>
            </div>

            {/* Shelves */}
            {loading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <div key={i}>
                        <Skeleton className="h-6 w-40 mb-3" />
                        <div className="flex gap-3">
                            {Array.from({ length: 5 }).map((_, j) => (
                                <Skeleton key={j} className="w-44 h-40" />
                            ))}
                        </div>
                    </div>
                ))
                : collections.map((c) => {
                    const items = readingOnly
                        ? c.items.filter((i) => i.read_status === "READING")
                        : c.items

                    return (
                        <div key={c.id} className="space-y-4">
                            <Link
                                href={`/library/${c.id}`}
                                className="flex justify-between items-center border-l-4 pl-3 hover:bg-muted/50 py-1 transition-colors group"
                                style={{ borderColor: c.color || "transparent" }}
                            >
                                <div className="flex items-center gap-2">
                                    <h2 className="font-semibold text-lg">{c.name}</h2>
                                    <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground" />
                                </div>
                                <Badge variant="secondary" className="font-normal text-xs">
                                    {c.unread_count} unread
                                </Badge>
                            </Link>

                            {items.length === 0 ? (
                                <p className="text-sm text-gray-500">
                                    No items yet — save some content!
                                </p>
                            ) : (
                                <div className="flex overflow-x-auto gap-3 pb-3 scrollbar-hide">
                                    {items.map((item) => (
                                        <LibraryItemCard key={item.id} item={item} />
                                    ))}
                                </div>
                            )}
                        </div>
                    )
                })}
        </div>
    )
}