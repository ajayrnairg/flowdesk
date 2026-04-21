// Service Worker for FlowDesk

self.addEventListener("install", (event) => {
  // Activate immediately
  self.skipWaiting()
})

self.addEventListener("activate", (event) => {
  // Take control immediately
  event.waitUntil(self.clients.claim())
})

// Handle push event
self.addEventListener("push", (event) => {
  if (!event.data) return

  try {
    const data = event.data.json()
    if (!data || typeof data !== "object") throw new Error("Invalid payload")

    const title = data.title || "FlowDesk"
    const options = {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: {
        url: data.url || "/planner",
      },
    }

    event.waitUntil(
      self.registration.showNotification(title, options)
    )
  } catch (err) {
    console.error("Push event error (malformed JSON or invalid data):", err)
    
    // Fallback notification for malformed data if desired, or just silent fail
    event.waitUntil(
      self.registration.showNotification("FlowDesk", {
        body: "You have a new update",
        icon: "/icons/icon-192.png"
      })
    )
  }
})

// Handle notification click
self.addEventListener("notificationclick", (event) => {
  event.notification.close()

  const targetUrl = event.notification.data?.url || "/planner"

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(targetUrl) && "focus" in client) {
          return client.focus()
        }
      }
      return self.clients.openWindow(targetUrl)
    })
  )
})