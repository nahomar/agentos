package com.agentos

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.agentos.service.AgentForegroundService

/**
 * Restarts the AgentOS foreground service after device reboot.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            val prefs = context.getSharedPreferences("agentos", Context.MODE_PRIVATE)
            val serverUrl = prefs.getString("server_url", "http://192.168.1.206:8000") ?: return

            val serviceIntent = Intent(context, AgentForegroundService::class.java).apply {
                putExtra("server_url", serverUrl)
            }
            context.startForegroundService(serviceIntent)
        }
    }
}
