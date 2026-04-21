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

    useEffect(() => {
        if (typeof window !== "undefined" && "Notification" in window) {
            setPermission(Notification.permission)
        }
    }, [])

    const handleEnable = async () => {
        if (!("serviceWorker" in navigator) || !("Notification" in window)) {
            alert("Push notifications are not supported by this browser.")
            return
        }

        setLoading(true)
        setSuccess(false)

        const result = await setupPushNotifications()

        setLoading(false)

        if (result.success) {
            setSuccess(true)
            setPermission("granted")
        }
    }

    const renderStatus = () => {
        if (permission === "granted") {
            return <Badge className="bg-green-600">Enabled</Badge>
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

                {success && (
                    <p className="text-sm text-green-600">
                        ✅ Notifications enabled
                    </p>
                )}

                <Button onClick={handleEnable} disabled={loading}>
                    {loading ? "Enabling..." : "Enable notifications"}
                </Button>
            </CardContent>
        </Card>
    )
}