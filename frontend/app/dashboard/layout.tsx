"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import type { ReactNode } from "react"

import { isLoggedIn } from "@/lib/auth"
import { Toaster } from "@/components/ui/sonner"
import { registerServiceWorker } from "@/lib/push"


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

    return (
        <div className="min-h-screen">
            {children}

            {/* ✅ Toast system (sonner) */}
            <Toaster />
        </div>
    )
}