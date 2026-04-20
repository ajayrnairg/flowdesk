"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { isLoggedIn } from "@/lib/auth"
import { Toaster } from "@/components/ui/sonner"

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const router = useRouter()

    useEffect(() => {
        if (!isLoggedIn()) {
            router.replace("/login")
        }
    }, [router])

    return <div className="min-h-screen">{children}<Toaster /></div>
}