package com.agentos.service

import android.app.*
import android.content.Intent
import android.os.IBinder
import android.os.Build
import androidx.core.app.NotificationCompat
import com.agentos.AgentOSApp
import com.agentos.core.WebSocketManager
import com.agentos.core.ContextReporter
import com.agentos.ui.MainActivity

/**
 * Persistent foreground service that keeps AgentOS running.
 * Maintains WebSocket connection and reports device context.
 */
class AgentForegroundService : Service() {

    private lateinit var wsManager: WebSocketManager
    private lateinit var contextReporter: ContextReporter

    override fun onCreate() {
        super.onCreate()
        wsManager = WebSocketManager()
        contextReporter = ContextReporter(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val serverUrl = intent?.getStringExtra("server_url") ?: "http://192.168.1.206:8000"

        // Start as foreground service with persistent notification
        val notification = buildNotification("AgentOS — Connecting...")
        startForeground(1, notification)

        // Connect to backend
        wsManager.connect(serverUrl)
        wsManager.onConnectionChange = { connected ->
            updateNotification(
                if (connected) "AgentOS — 13 agents active"
                else "AgentOS — Reconnecting..."
            )
        }

        // Start reporting context every 60 seconds
        contextReporter.startReporting(wsManager)

        return START_STICKY // Restart if killed by system
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        contextReporter.stop()
        wsManager.disconnect()
        super.onDestroy()
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, AgentOSApp.CHANNEL_ID)
            .setContentTitle("AgentOS")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val notification = buildNotification(text)
        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(1, notification)
    }
}
