"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { BookOpen, Search, CalendarDays, Settings } from "lucide-react"
import { UserButton } from "@clerk/nextjs"

const navItems = [
    {
        label: "Planner",
        href: "/planner",
        icon: CalendarDays,
    },
    {
        label: "Knowledge",
        href: "/knowledge",
        icon: BookOpen,
    },
    {
        label: "Library",
        href: "/library",
        icon: BookOpen,
    },
    {
        label: "Search",
        href: "/search",
        icon: Search,
        hasShortcut: true,
    },
    {
        label: "Settings",
        href: "/settings",
        icon: Settings,
    },
]

export default function DashboardNav() {
    const pathname = usePathname()
    const [isMac, setIsMac] = useState(false)

    useEffect(() => {
        setIsMac(navigator.platform.toUpperCase().indexOf("MAC") >= 0)
    }, [])

    return (
        <nav className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-1">
                {/* Brand */}
                <span className="font-bold text-lg mr-4 tracking-tight select-none">
                    FlowDesk
                </span>

                <div className="flex items-center gap-1 flex-1">
                    {navItems.map(({ label, href, icon: Icon, hasShortcut }) => {
                        const active = pathname.startsWith(href)
                        return (
                            <Link
                                key={href}
                                href={href}
                                className={[
                                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                                    active
                                        ? "bg-primary text-primary-foreground"
                                        : "text-muted-foreground hover:text-foreground hover:bg-accent",
                                ].join(" ")}
                            >
                                <Icon className="w-4 h-4 shrink-0" />
                                <span className="hidden sm:inline">{label}</span>
                                {hasShortcut && (
                                    <span className="ml-1.5 hidden sm:inline-flex items-center gap-0.5 text-[10px] font-medium bg-muted border border-border rounded px-1 py-0.5 text-muted-foreground leading-none opacity-70">
                                        <span>{isMac ? "⌘" : "Ctrl"}</span>
                                        <span>K</span>
                                    </span>
                                )}
                            </Link>
                        )
                    })}
                </div>

                <div className="ml-4 flex items-center">
                    <UserButton />
                </div>
            </div>
        </nav>
    )
}
