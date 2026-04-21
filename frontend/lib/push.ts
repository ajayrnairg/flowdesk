import api from "./api"

// Convert VAPID key
export function urlBase64ToUint8Array(base64String: string): Uint8Array {
    // 1. Strip PEM headers/footers and remove all whitespace/newlines
    const cleanString = base64String
        .replace(/-----BEGIN.*?-----/g, "")
        .replace(/-----END.*?-----/g, "")
        .replace(/\s/g, "");

    // 2. Add padding if necessary
    const padding = "=".repeat((4 - (cleanString.length % 4)) % 4);
    
    // 3. Convert URL-safe Base64 to standard Base64
    const base64 = (cleanString + padding)
        .replace(/-/g, "+")
        .replace(/_/g, "/");

    const rawData = window.atob(base64);
    return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
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

// Subscribe
export async function subscribeToPush(
    registration: ServiceWorkerRegistration
): Promise<PushSubscription | null> {
    try {
        const existing = await registration.pushManager.getSubscription()
        if (existing) return existing

        const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY
        if (!vapidKey) throw new Error("Missing VAPID key")

        const convertedKey = urlBase64ToUint8Array(vapidKey)

        return await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: convertedKey as unknown as BufferSource,
        })
    } catch (err) {
        console.error("Subscription failed:", err)
        return null
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

        const subscription = await subscribeToPush(registration)
        if (!subscription) {
            return { success: false, error: "Subscription failed" }
        }

        await savePushSubscription(subscription)

        return { success: true }
    } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err)
        console.error("[setupPushNotifications] fatal:", message)
        return { success: false, error: message }
    }
}