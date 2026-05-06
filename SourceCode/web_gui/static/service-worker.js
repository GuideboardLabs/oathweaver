self.addEventListener("push", (event) => {
  const payload = (() => {
    try {
      return event.data ? event.data.json() : {};
    } catch (_err) {
      return {};
    }
  })();

  const title = String(payload.title || "Oathweaver").trim() || "Oathweaver";
  const body = String(payload.body || "").trim();
  const url = String(payload.url || "/").trim() || "/";
  const data = {
    url,
    conversationId: String(payload.conversation_id || "").trim(),
    tag: String(payload.tag || "").trim(),
  };
  const options = {
    body,
    icon: String(payload.icon || "/static/branding/logo.png").trim(),
    badge: String(payload.badge || "/static/branding/logo.png").trim(),
    tag: String(payload.tag || "").trim() || undefined,
    data,
    renotify: Boolean(payload.renotify),
    requireInteraction: Boolean(payload.requireInteraction),
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = String(event.notification?.data?.url || "/").trim() || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if ("focus" in client) {
          try {
            client.navigate(targetUrl);
          } catch (_err) {}
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});
