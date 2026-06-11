package com.agentos.service

import android.service.wallpaper.WallpaperService
import android.view.SurfaceHolder
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * Live wallpaper that renders the AgentOS visualization.
 * Uses a WebView connected to the backend's wallpaper UI.
 */
class AgentWallpaperService : WallpaperService() {

    override fun onCreateEngine(): Engine = WallpaperEngine()

    inner class WallpaperEngine : Engine() {
        // Note: Full WebView in wallpaper requires careful lifecycle management.
        // For production, render to Canvas using data from WebSocket.

        override fun onSurfaceCreated(holder: SurfaceHolder) {
            super.onSurfaceCreated(holder)
            // Draw dark gradient background
            val canvas = holder.lockCanvas()
            if (canvas != null) {
                canvas.drawColor(0xFF0A0A1A.toInt())
                holder.unlockCanvasAndPost(canvas)
            }
        }

        override fun onVisibilityChanged(visible: Boolean) {
            super.onVisibilityChanged(visible)
            // Start/stop rendering based on visibility
        }
    }
}
