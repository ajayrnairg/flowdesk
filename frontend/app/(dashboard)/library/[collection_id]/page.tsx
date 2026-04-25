"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { getCollection, getCollectionItems, LibraryCollection } from "@/lib/library"
import { KnowledgeItemOut } from "@/lib/knowledge"
import LibraryItemCard from "@/components/library/LibraryItemCard"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Link from "next/link"
import { toast } from "sonner"
import { ArrowLeft } from "lucide-react"

type TabValue = "ALL" | "UNREAD" | "READING" | "DONE"

export default function CollectionPage() {
    const params = useParams()
    const collectionId = params.collection_id as string

    const [collection, setCollection] = useState<LibraryCollection | null>(null)
    const [items, setItems] = useState<KnowledgeItemOut[]>([])
    const [loading, setLoading] = useState(true)
    const [itemsLoading, setItemsLoading] = useState(false)
    const [activeTab, setActiveTab] = useState<TabValue>("ALL")

    useEffect(() => {
        const fetchCollection = async () => {
            try {
                const data = await getCollection(collectionId)
                setCollection(data)
            } catch (error) {
                toast.error("Failed to fetch collection details")
                console.error("Failed to fetch collection:", error)
            } finally {
                setLoading(false)
            }
        }
        fetchCollection()
    }, [collectionId])

    useEffect(() => {
        const fetchItems = async () => {
            setItemsLoading(true)
            try {
                const statusParam = activeTab === "ALL" ? undefined : activeTab
                const data = await getCollectionItems(collectionId, statusParam)
                setItems(data)
            } catch (error) {
                toast.error("Failed to load items")
                console.error("Failed to fetch items:", error)
            } finally {
                setItemsLoading(false)
            }
        }
        fetchItems()
    }, [collectionId, activeTab])

    if (loading) {
        return (
            <div className="p-6 space-y-6">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-8 w-64" />
                <div className="flex gap-2">
                    <Skeleton className="h-10 w-20" />
                    <Skeleton className="h-10 w-20" />
                    <Skeleton className="h-10 w-20" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-48 w-full" />
                    ))}
                </div>
            </div>
        )
    }

    if (!collection) {
        return (
            <div className="p-6 text-center">
                <h1 className="text-xl font-semibold">Collection not found</h1>
                <Link href="/dashboard/library" className="text-blue-600 hover:underline">
                    Back to Library
                </Link>
            </div>
        )
    }

    return (
        <div className="p-6 space-y-8 max-w-7xl mx-auto">
            {/* Header */}
            <div className="space-y-6">
                <Link
                    href="/dashboard/library"
                    className="group flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
                >
                    <div className="p-1 rounded bg-muted group-hover:bg-primary/10 transition-colors">
                        <ArrowLeft className="w-4 h-4" />
                    </div>
                    Back to Library
                </Link>

                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div className="flex items-center gap-4">
                        <div
                            className="w-2 h-12 rounded-full"
                            style={{ background: collection.color || "#ccc" }}
                        />
                        <div>
                            <h1 className="text-3xl font-bold tracking-tight">{collection.name}</h1>
                            <p className="text-muted-foreground text-sm">
                                {collection.item_count} items in this collection
                            </p>
                        </div>
                    </div>

                    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)}>
                        <TabsList className="bg-muted/50">
                            <TabsTrigger value="ALL">All</TabsTrigger>
                            <TabsTrigger value="UNREAD">Unread</TabsTrigger>
                            <TabsTrigger value="READING">Reading</TabsTrigger>
                            <TabsTrigger value="DONE">Done</TabsTrigger>
                        </TabsList>
                    </Tabs>
                </div>
            </div>

            {itemsLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-48 w-full" />
                    ))}
                </div>
            ) : items.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground border-2 border-dashed rounded-lg">
                    No items found for this filter.
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                    {items.map((item) => (
                        <LibraryItemCard key={item.id} item={item} />
                    ))}
                </div>
            )}
        </div>
    )
}