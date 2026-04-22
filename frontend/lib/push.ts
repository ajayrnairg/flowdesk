import api from "./api"

// Convert VAPID key
export function urlBase64ToUint8Array(base64String: string): Uint8Array {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4)
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/")
    const rawData = window.atob(base64)
    return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)))
}

// Register SW
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
        return null
    }

    try {
        return await navigator.serviceWorker.register("/sw.js")
    } catch (err) {
        console.error("SW registration failed:", err)
        return null
    }
}

// Request permission
export async function requestPushPermission(): Promise<boolean> {
    if (typeof window === "undefined") return false

    const permission = await Notification.requestPermission()
    return permission === "granted"
}

// Subscribe — always waits for SW activation via navigator.serviceWorker.ready
// push.ts — update handleReset in PushNotificationSetup, or add to subscribeToPush
export async function subscribeToPush(): Promise<PushSubscription> {
    const activeReg = await navigator.serviceWorker.ready

    // Always unsubscribe first if an existing subscription exists — 
    // it might be registered under a different sender ID or stale VAPID key.
    // A fresh subscription is cheap; a stale one causes silent delivery failure.
    const existing = await activeReg.pushManager.getSubscription()
    if (existing) {
        await existing.unsubscribe()
    }

    const vapidKey = (process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "").trim()
    if (!vapidKey) throw new Error("NEXT_PUBLIC_VAPID_PUBLIC_KEY is not set")

    if (!window.isSecureContext) {
        throw new Error("Push notifications require a secure context (HTTPS)")
    }

    const convertedKey = urlBase64ToUint8Array(vapidKey)

    if (convertedKey.length !== 65) {
        throw new Error(`VAPID key is ${convertedKey.length} bytes — must be 65`)
    }

    try {
        return await activeReg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedKey.buffer as BufferSource, // ArrayBuffer cast for TS
        })
    } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        throw new Error(`subscribe failed: ${msg} | keyLen=${convertedKey.length}`)
    }
}

// Save subscription
export async function savePushSubscription(subscription: PushSubscription) {
    const json = subscription.toJSON()

    // NOTE: Backend schema expects { endpoint, keys: { p256dh, auth }, user_agent }
    await api.post("/notifications/subscriptions", {
        endpoint: json.endpoint,
        keys: {
            p256dh: json.keys?.p256dh,
            auth: json.keys?.auth,
        },
        user_agent: typeof navigator !== "undefined" ? navigator.userAgent : "unknown",
    })
}

// Full setup
export async function setupPushNotifications(): Promise<{
    success: boolean
    error?: string
}> {
    try {
        const registration = await registerServiceWorker()
        if (!registration) return { success: false, error: "SW not supported" }

        const permissionGranted = await requestPushPermission()
        if (!permissionGranted) {
            return { success: false, error: "Permission denied" }
        }

        const subscription = await subscribeToPush()
        await savePushSubscription(subscription)

        return { success: true }
    } catch (err: unknown) {
        const message = err instanceof Error ? `${err.name}: ${err.message}` : String(err)
        console.error('[setupPushNotifications] fatal:', err)
        return { success: false, error: message }
    }
}