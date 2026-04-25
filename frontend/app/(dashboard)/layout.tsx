"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import type { ReactNode } from "react"

import { isLoggedIn } from "@/lib/auth"
import { Toaster } from "@/components/ui/sonner"
import { registerServiceWorker } from "@/lib/push"
import DashboardNav from "@/components/DashboardNav"


export default function DashboardLayout({
    children,
}: {
    children: ReactNode
}) {
    const router = useRouter()

    // 🔐 Auth protection
    useEffect(() => {
        if (!isLoggedIn()) {
            router.replace("/login")
        }
    }, [router])

    // 🔔 Register service worker (client-only)
    useEffect(() => {
        registerServiceWorker()
    }, [])

    // ⌨️ Global Cmd+K / Ctrl+K shortcut → navigate to Search
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                router.push("/dashboard/search")
            }
        }
        window.addEventListener("keydown", handler)
        return () => window.removeEventListener("keydown", handler)
    }, [router])

    return (
        <div className="min-h-screen flex flex-col">
            <DashboardNav />

            <main className="flex-1">
                {children}
            </main>

            {/* ✅ Toast system (sonner) */}
            <Toaster />
        </div>
    )
}