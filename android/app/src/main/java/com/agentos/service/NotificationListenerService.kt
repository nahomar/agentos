package com.agentos.service

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.agentos.core.WebSocketManager
import org.json.JSONObject

/**
 * Listens to ALL phone notifications and forwards them to AgentOS backend.
 * Backend classifies priority and routes to appropriate agents.
 */
class AgentNotificationListener : NotificationListenerService() {

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val notification = sbn.notification ?: return
        val extras = notification.extras ?: return

        val app = sbn.packageName ?: ""
        val title = extras.getCharSequence("android.title")?.toString() ?: ""
        val text = extras.getCharSequence("android.text")?.toString() ?: ""

        if (title.isEmpty() && text.isEmpty()) return

        // Don't forward our own notifications
        if (app == packageName) return

        val payload = JSONObject().apply {
            put("app", app)
            put("title", title)
            put("text", text)
            put("timestamp", sbn.postTime / 1000.0)
            put("key", sbn.key)
        }

        // Forward to backend via HTTP
        Thread {
            try {
                val url = java.net.URL("http://192.168.1.206:8000/api/notifications/ingest")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.outputStream.write(payload.toString().toByteArray())
                conn.responseCode // Execute
                conn.disconnect()
            } catch (e: Exception) {
                // Silently fail — backend may be unreachable
            }
        }.start()
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        // Could track dismissed notifications
    }
}
