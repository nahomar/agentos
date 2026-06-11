package com.agentos.core

import android.content.Context
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import org.json.JSONObject

/**
 * Reports device context (location, battery, etc.) to the backend every 60 seconds.
 */
class ContextReporter(private val context: Context) {
    private var handler: Handler? = null
    private var wsManager: WebSocketManager? = null
    private val intervalMs = 60_000L

    fun startReporting(ws: WebSocketManager) {
        wsManager = ws
        handler = Handler(Looper.getMainLooper())
        handler?.post(reportRunnable)
    }

    fun stop() {
        handler?.removeCallbacks(reportRunnable)
    }

    private val reportRunnable = object : Runnable {
        override fun run() {
            reportContext()
            handler?.postDelayed(this, intervalMs)
        }
    }

    private fun reportContext() {
        val data = JSONObject()

        // Battery
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
        val battery = bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
        data.put("battery_level", battery)

        // Charging
        val charging = bm?.isCharging ?: false
        data.put("charging", charging)

        // Location (requires permission)
        try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
            val loc = lm?.getLastKnownLocation(LocationManager.PASSIVE_PROVIDER)
            if (loc != null) {
                data.put("lat", loc.latitude)
                data.put("lon", loc.longitude)
            }
        } catch (e: SecurityException) {
            // Location permission not granted
        }

        wsManager?.send(JSONObject().apply {
            put("type", "context_update")
            put("data", data)
        })
    }
}
