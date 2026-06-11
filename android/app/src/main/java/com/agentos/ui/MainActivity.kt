package com.agentos.ui

import android.content.Intent
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import androidx.appcompat.app.AppCompatActivity
import com.agentos.service.AgentForegroundService

/**
 * Main activity — setup server connection and show wallpaper WebView.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private var serverUrl = "http://192.168.1.206:8000"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Simple setup UI
        val prefs = getSharedPreferences("agentos", MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", serverUrl) ?: serverUrl

        // Start the foreground service
        startAgentService()

        // Load wallpaper in WebView
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = WebViewClient()
            loadUrl(serverUrl)
        }
        setContentView(webView)
    }

    private fun startAgentService() {
        val intent = Intent(this, AgentForegroundService::class.java).apply {
            putExtra("server_url", serverUrl)
        }
        startForegroundService(intent)
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
