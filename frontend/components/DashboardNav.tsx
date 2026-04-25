"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BookOpen, Search, CalendarDays, Settings } from "lucide-react"

const navItems = [
    {
        label: "Planner",
        href: "/dashboard/planner",
        icon: CalendarDays,
    },
    {
        label: "Knowledge",
        href: "/dashboard/knowledge",
        icon: BookOpen,
    },
    {
        label: "Search",
        href: "/dashboard/search",
        icon: Search,
        shortcut: (
            <span className="ml-1.5 hidden sm:inline-flex items-center gap-0.5 text-[10px] font-medium bg-muted border border-border rounded px-1 py-0.5 text-muted-foreground leading-none">
                <span className="hidden sm:inline">⌘</span>
                <span className="sm:hidden">Ctrl</span>
                K
            </span>
        ),
    },
    {
        label: "Settings",
        href: "/dashboard/settings",
        icon: Settings,
    },
]

export default function DashboardNav() {
    const pathname = usePathname()

    return (
        <nav className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="max-w-5xl mx-auto px-4 h-14 flex items-center gap-1">
                {/* Brand */}
                <span className="font-bold text-lg mr-4 tracking-tight select-none">
                    FlowDesk
                </span>

                <div className="flex items-center gap-1 flex-1">
                    {navItems.map(({ label, href, icon: Icon, shortcut }) => {
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
                                {shortcut}
                            </Link>
                        )
                    })}
                </div>
            </div>
        </nav>
    )
}
