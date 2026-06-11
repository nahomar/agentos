import SwiftUI
import WebKit

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @State private var showNativeUI = false

    var body: some View {
        ZStack {
            // Main wallpaper view (WebView)
            WallpaperWebView(baseURL: appState.wsManager.baseURL)
                .ignoresSafeArea()

            // Floating toggle button
            VStack {
                HStack {
                    Spacer()
                    Button(action: { showNativeUI.toggle() }) {
                        Image(systemName: showNativeUI ? "xmark.circle.fill" : "square.grid.2x2.fill")
                            .font(.title2)
                            .foregroundColor(.white)
                            .padding(12)
                            .background(.ultraThinMaterial)
                            .clipShape(Circle())
                    }
                    .padding(.trailing, 16)
                    .padding(.top, 8)
                }
                Spacer()
            }

            // Native overlay (when toggled)
            if showNativeUI {
                NativeDashboard()
                    .transition(.move(edge: .bottom))
            }
        }
        .animation(.spring(), value: showNativeUI)
    }
}

// MARK: - WebView for Wallpaper

struct WallpaperWebView: UIViewRepresentable {
    let baseURL: String

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.scrollView.isScrollEnabled = false
        if let url = URL(string: baseURL) {
            webView.load(URLRequest(url: url))
        }
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

// MARK: - Native Dashboard

struct NativeDashboard: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 16) {
                // Handle
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.white.opacity(0.3))
                    .frame(width: 36, height: 4)
                    .padding(.top, 12)

                // Connection status
                HStack {
                    Circle()
                        .fill(appState.isConnected ? Color.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(appState.isConnected ? "Live" : "Disconnected")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    Spacer()
                    Text("\(appState.agents.count) agents")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                }
                .padding(.horizontal, 20)

                // Agent grid
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 12) {
                    ForEach(appState.agents) { agent in
                        AgentCell(agent: agent)
                    }
                }
                .padding(.horizontal, 16)

                // Recent feed
                ScrollView {
                    LazyVStack(spacing: 8) {
                        ForEach(appState.feedItems.prefix(20)) { item in
                            FeedRow(item: item)
                        }
                    }
                    .padding(.horizontal, 16)
                }
                .frame(maxHeight: 200)
            }
            .frame(maxHeight: UIScreen.main.bounds.height * 0.6)
            .background(.ultraThinMaterial)
            .cornerRadius(20)
        }
    }
}

struct AgentCell: View {
    let agent: AgentInfo

    var body: some View {
        VStack(spacing: 4) {
            Text(agent.emoji)
                .font(.title)
                .frame(width: 50, height: 50)
                .background(Color.white.opacity(0.1))
                .clipShape(Circle())

            Text(agent.name)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(.white.opacity(0.9))
        }
    }
}

struct FeedRow: View {
    let item: FeedItem

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Text(item.emoji)
                .font(.title3)

            VStack(alignment: .leading, spacing: 2) {
                Text(item.sender)
                    .font(.caption.bold())
                    .foregroundColor(.white.opacity(0.9))

                Text(item.content)
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.6))
                    .lineLimit(2)
            }

            Spacer()
        }
        .padding(10)
        .background(Color.white.opacity(0.05))
        .cornerRadius(10)
    }
}
