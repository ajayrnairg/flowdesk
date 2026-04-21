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
export async function subscribeToPush(): Promise<PushSubscription> {
    // .ready resolves only when the SW is fully ACTIVATED and controlling the page.
    // Using the registration from .register() is NOT sufficient on mobile — it
    // resolves when the SW is parsed/registered, not yet activated.
    const activeReg = await navigator.serviceWorker.ready

    const existing = await activeReg.pushManager.getSubscription()
    if (existing) return existing

    const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY
    if (!vapidKey) throw new Error("Missing VAPID key env var")

    const convertedKey = urlBase64ToUint8Array(vapidKey)

    return await activeReg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: convertedKey as unknown as BufferSource,
    })
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
        const message = err instanceof Error ? err.message : String(err)
        console.error("[setupPushNotifications] fatal:", message)
        return { success: false, error: message }
    }
}