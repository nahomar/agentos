package com.agentos.core

import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Persistent WebSocket connection to the AgentOS backend.
 * Auto-reconnects with exponential backoff.
 */
class WebSocketManager {
    private var client: OkHttpClient? = null
    private var webSocket: WebSocket? = null
    private var serverUrl: String = ""
    private var reconnectDelay = 1000L
    private var isConnected = false

    var onConnectionChange: ((Boolean) -> Unit)? = null
    var onMessage: ((JSONObject) -> Unit)? = null

    fun connect(baseUrl: String) {
        serverUrl = baseUrl
        val wsUrl = baseUrl
            .replace("http://", "ws://")
            .replace("https://", "wss://") + "/ws"

        client = OkHttpClient.Builder()
            .readTimeout(0, TimeUnit.MILLISECONDS)
            .build()

        val request = Request.Builder().url(wsUrl).build()

        webSocket = client?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                reconnectDelay = 1000
                onConnectionChange?.invoke(true)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    onMessage?.invoke(JSONObject(text))
                } catch (e: Exception) {
                    // Ignore parse errors
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                onConnectionChange?.invoke(false)
                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                onConnectionChange?.invoke(false)
                scheduleReconnect()
            }
        })
    }

    fun send(data: JSONObject) {
        webSocket?.send(data.toString())
    }

    fun disconnect() {
        webSocket?.close(1000, "Shutting down")
        client?.dispatcher?.executorService?.shutdown()
    }

    private fun scheduleReconnect() {
        Thread {
            Thread.sleep(reconnectDelay)
            reconnectDelay = minOf(reconnectDelay * 2, 30000)
            connect(serverUrl)
        }.start()
    }
}
