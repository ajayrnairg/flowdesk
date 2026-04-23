"use client"

import { useEffect, useState, Suspense } from "react"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import api from "@/lib/api"
import { isLoggedIn } from "@/lib/auth"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
} from "@/components/ui/select"
import { toast } from "sonner"

function SaveForm() {
    const router = useRouter()
    const params = useSearchParams()
    const pathname = usePathname()

    const [loading, setLoading] = useState(false)
    const [success, setSuccess] = useState(false)

    const url = params.get("url") || ""
    const titleParam = params.get("title") || ""
    const textParam = params.get("text") || ""
    const type = params.get("type") || "article"

    const [title, setTitle] = useState(titleParam)
    const [selectedText, setSelectedText] = useState(textParam)

    // 🔐 Auth check
    useEffect(() => {
        if (!isLoggedIn()) {
            const currentUrl = `${pathname}?${params.toString()}`
            const returnUrl = encodeURIComponent(currentUrl)
            router.replace(`/login?redirect=${returnUrl}`)
        }
    }, [router, pathname, params])

    const handleSave = async () => {
        setLoading(true)

        try {
            // FIXED: Mapping frontend fields to backend BookmarkletPayload
            await api.post("/knowledge/bookmarklet", {
                url,
                page_title: title,
                selected_text: selectedText,
                content_type: type,
            })

            setSuccess(true)
        } catch (err) {
            toast.error("Failed to save")
        } finally {
            setLoading(false)
        }
    }

    return (
        <CardContent className="space-y-4">
            {/* URL */}
            <div>
                <p className="text-sm text-gray-500 mb-1">URL</p>
                <input
                    value={url}
                    readOnly
                    className="w-full border rounded px-3 py-2 text-sm bg-gray-100"
                />
            </div>

            {/* Title */}
            <div>
                <p className="text-sm text-gray-500 mb-1">Title</p>
                <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full border rounded px-3 py-2 text-sm"
                />
            </div>

            {/* Type */}
            <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">Content Type</span>
                <Badge>{type}</Badge>
            </div>

            {/* Selected text */}
            <div>
                <p className="text-sm text-gray-500 mb-1">Selected Text</p>
                <Textarea
                    value={selectedText}
                    onChange={(e) => setSelectedText(e.target.value)}
                    className="max-h-[200px] overflow-y-auto"
                    placeholder="Enter or edit the selected text..."
                />
            </div>

            {/* Collection selector */}
            <div>
                <p className="text-sm text-gray-500 mb-1">Collection</p>
                <Select disabled>
                    <SelectTrigger>
                        <SelectValue placeholder="Collections coming soon" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="dummy">None</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Save button */}
            {!success ? (
                <Button onClick={handleSave} disabled={loading}>
                    {loading ? "Saving..." : "Save to Knowledge Base"}
                </Button>
            ) : (
                <p className="text-green-600 text-sm">
                    ✅ Saved! You can close this tab.
                </p>
            )}
        </CardContent>
    )
}

export default function SavePage() {
    return (
        <div className="flex items-center justify-center min-h-screen p-4">
            <Card className="w-full max-w-lg">
                <CardHeader>
                    <CardTitle>Save to FlowDesk</CardTitle>
                </CardHeader>
                <Suspense fallback={<CardContent>Loading...</CardContent>}>
                    <SaveForm />
                </Suspense>
            </Card>
        </div>
    )
}