"use client"

import { useState } from "react"
import { Input } from "@/components/ui/input"
import { X, Search, Loader2 } from "lucide-react"

interface Props {
    onSearch: (query: string) => void
    loading?: boolean
}

export default function SearchInput({ onSearch, loading }: Props) {
    const [value, setValue] = useState("")

    const handleSubmit = () => {
        onSearch(value.trim())
    }

    const handleClear = () => {
        setValue("")
        onSearch("")
    }

    return (
        <div className="relative w-full max-w-2xl mx-auto">
            {/* Icon */}
            <div className="absolute left-3 top-1/2 -translate-y-1/2">
                {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                ) : (
                    <Search className="w-5 h-5 text-gray-400" />
                )}
            </div>

            <Input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSubmit()}
                placeholder="Ask anything about your saved content..."
                className="pl-10 pr-10 h-12 text-base"
            />

            {/* Clear */}
            {value && (
                <button
                    onClick={handleClear}
                    className="absolute right-3 top-1/2 -translate-y-1/2"
                >
                    <X className="w-4 h-4 text-gray-400" />
                </button>
            )}
        </div>
    )
}