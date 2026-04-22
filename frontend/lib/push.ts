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
    const activeReg = await navigator.serviceWorker.ready

    const existing = await activeReg.pushManager.getSubscription()
    if (existing) return existing

    const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY
    if (!vapidKey) throw new Error("NEXT_PUBLIC_VAPID_PUBLIC_KEY is not set")

    const convertedKey = urlBase64ToUint8Array(vapidKey)
    
    // Validate key before calling subscribe — gives a readable error instead of AbortError
    if (convertedKey.length !== 65) {
        throw new Error(
            `VAPID public key decoded to ${convertedKey.length} bytes — must be exactly 65. ` +
            `Key starts with: ${vapidKey.slice(0, 10)}...`
        )
    }
    
    if (convertedKey[0] !== 0x04) {
        throw new Error(
            `VAPID key first byte is 0x${convertedKey[0].toString(16)} — expected 0x04 (uncompressed EC point)`
        )
    }

    try {
        return await activeReg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedKey.buffer,  // ArrayBuffer, not Uint8Array (crucial for Android)
        })
    } catch (err) {
        const msg = err instanceof Error ? `${err.name}: ${err.message}` : String(err)
        throw new Error(`pushManager.subscribe failed: ${msg} | keyLen=${convertedKey.length} | UA=${navigator.userAgent}`)
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