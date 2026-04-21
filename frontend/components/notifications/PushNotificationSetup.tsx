"use client"

import { useEffect, useState } from "react"
import { setupPushNotifications } from "@/lib/push"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

export default function PushNotificationSetup() {
    const [permission, setPermission] = useState<NotificationPermission>("default")
    const [loading, setLoading] = useState(false)
    const [success, setSuccess] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [vapidDebug, setVapidDebug] = useState<string | null>(null)

    useEffect(() => {
        if (typeof window !== "undefined" && "Notification" in window) {
            setPermission(Notification.permission)
        }
        // Show what VAPID key is actually loaded at runtime
        const key = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? "(not set)"
        let byteLen = "?"
        try {
            const padding = "=".repeat((4 - (key.length % 4)) % 4)
            const b64 = (key + padding).replace(/-/g, "+").replace(/_/g, "/")
            byteLen = String(atob(b64).length)
        } catch { /* ignore */ }
        setVapidDebug(`key[0..20]="${key.slice(0, 20)}..." len=${key.length} decoded=${byteLen}B`)
    }, [])

    const runSetup = async () => {
        setLoading(true)
        setSuccess(false)
        setError(null)

        const result = await setupPushNotifications()

        setLoading(false)

        if (result.success) {
            setSuccess(true)
            setPermission("granted")
        } else {
            setError(result.error ?? "Unknown error")
        }
    }

    const handleEnable = async () => {
        if (!("serviceWorker" in navigator) || !("Notification" in window)) {
            alert("Push notifications are not supported by this browser.")
            return
        }
        await runSetup()
    }

    /** Unsubscribes from the browser push manager, then re-subscribes fresh */
    const handleReset = async () => {
        if (!("serviceWorker" in navigator)) return

        setLoading(true)
        setError(null)
        setSuccess(false)

        try {
            const reg = await navigator.serviceWorker.ready
            const existing = await reg.pushManager.getSubscription()
            if (existing) {
                await existing.unsubscribe()
            }
        } catch (err) {
            console.warn("Unsubscribe failed:", err)
        }

        await runSetup()
    }

    const renderStatus = () => {
        if (success) {
            return <Badge className="bg-green-600">Enabled ✓</Badge>
        }
        if (permission === "granted") {
            return <Badge variant="secondary">Granted (re-sync needed)</Badge>
        }
        if (permission === "denied") {
            return <Badge variant="destructive">Blocked</Badge>
        }
        return <Badge variant="secondary">Not enabled</Badge>
    }

    return (
        <Card className="max-w-md">
            <CardHeader>
                <CardTitle>Push Notifications</CardTitle>
            </CardHeader>

            <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                    <span>Status</span>
                    {renderStatus()}
                </div>

                {permission === "denied" && (
                    <p className="text-sm text-red-500">
                        Notifications are blocked. Please enable them in your browser settings.
                    </p>
                )}

                {error && (
                    <p className="text-sm text-red-500">
                        ❌ Error: {error}
                    </p>
                )}

                {success && (
                    <p className="text-sm text-green-600">
                        ✅ Subscription saved — you will receive notifications!
                    </p>
                )}

                <div className="flex gap-2">
                    <Button onClick={handleEnable} disabled={loading}>
                        {loading ? "Working..." : "Enable notifications"}
                    </Button>
                    {permission === "granted" && !success && (
                        <Button variant="outline" onClick={handleReset} disabled={loading}>
                            Reset & Re-sync
                        </Button>
                    )}
                </div>

                {/* Debug info — remove after confirming mobile works */}
                {vapidDebug && (
                    <p className="text-xs text-slate-400 font-mono break-all">
                        🔑 {vapidDebug}
                    </p>
                )}
            </CardContent>
        </Card>
    )
}