"use client"

import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"
import Link from "next/link"
import type { ReactNode } from "react"
import { CheckSquare, BookMarked, BookOpen, Search, Settings } from "lucide-react"

import { Toaster } from "@/components/ui/sonner"
import { registerServiceWorker } from "@/lib/push"
import DashboardNav from "@/components/DashboardNav"

const navItems = [
    { name: "Planner", href: "/planner", icon: CheckSquare },
    { name: "Knowledge", href: "/knowledge", icon: BookMarked },
    { name: "Library", href: "/library", icon: BookOpen },
    { name: "Search", href: "/search", icon: Search },
    { name: "Settings", href: "/settings", icon: Settings },
]

function MobileBottomNav() {
    const pathname = usePathname()
    
    return (
        <nav className="md:hidden fixed bottom-0 w-full bg-white border-t flex justify-around items-center h-16 z-50 px-2 pb-safe">
            {navItems.map((item) => {
                const isActive = pathname.startsWith(item.href)
                const Icon = item.icon
                return (
                    <Link
                        key={item.name}
                        href={item.href}
                        className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${
                            isActive ? "text-primary" : "text-gray-400 hover:text-gray-600"
                        }`}
                    >
                        <Icon className="w-5 h-5" />
                        <span className="text-[10px] font-medium">{item.name}</span>
                    </Link>
                )
            })}
        </nav>
    )
}

export default function DashboardLayout({
    children,
}: {
    children: ReactNode
}) {
    const router = useRouter()

    // 🔐 Auth protection is now handled by middleware.ts

    // 🔔 Register service worker (client-only)
    useEffect(() => {
        registerServiceWorker()
    }, [])

    // ⌨️ Global Cmd+K / Ctrl+K shortcut → navigate to Search
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                router.push("/search")
            }
        }
        window.addEventListener("keydown", handler)
        return () => window.removeEventListener("keydown", handler)
    }, [router])

    return (
        <div className="min-h-screen flex flex-col">
            <DashboardNav />

            <main className="flex-1 pb-16 md:pb-0">
                {children}
            </main>

            <MobileBottomNav />

            {/* ✅ Toast system (sonner) */}
            <Toaster />
        </div>
    )
}