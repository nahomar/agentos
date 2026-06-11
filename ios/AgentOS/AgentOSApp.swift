import SwiftUI

@main
struct AgentOSApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .onAppear {
                    appState.start()
                }
        }
    }
}

class AppState: ObservableObject {
    @Published var isConnected = false
    @Published var agents: [AgentInfo] = []
    @Published var feedItems: [FeedItem] = []

    let wsManager = WebSocketManager()
    let contextReporter = ContextReporter()
    let locationManager = LocationManager()

    func start() {
        wsManager.onConnectionChange = { [weak self] connected in
            DispatchQueue.main.async { self?.isConnected = connected }
        }

        wsManager.onMessage = { [weak self] message in
            DispatchQueue.main.async {
                self?.feedItems.insert(FeedItem(from: message), at: 0)
                if self?.feedItems.count ?? 0 > 100 {
                    self?.feedItems = Array(self!.feedItems.prefix(100))
                }
            }
        }

        wsManager.connect()
        locationManager.start()

        // Report context every 60 seconds
        contextReporter.startReporting(
            wsManager: wsManager,
            locationManager: locationManager
        )

        // Fetch agents
        Task { await fetchAgents() }
    }

    func fetchAgents() async {
        guard let url = URL(string: "\(wsManager.baseURL)/api/agents") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let agents = try JSONDecoder().decode([AgentInfo].self, from: data)
            DispatchQueue.main.async { self.agents = agents }
        } catch {
            print("Failed to fetch agents: \(error)")
        }
    }
}

struct AgentInfo: Codable, Identifiable {
    var id: String { name }
    let name: String
    let emoji: String
    let color: String
    let app: String
    let status: String
    let current_task: String
    let personality: String
}

struct FeedItem: Identifiable {
    let id = UUID()
    let sender: String
    let content: String
    let type: String
    let emoji: String
    let color: String
    let timestamp: Date

    init(from message: [String: Any]) {
        self.sender = message["sender"] as? String ?? "System"
        self.content = message["content"] as? String ?? ""
        self.type = message["type"] as? String ?? "system"
        let meta = message["metadata"] as? [String: Any] ?? [:]
        self.emoji = meta["emoji"] as? String ?? "🤖"
        self.color = meta["color"] as? String ?? "#FFFFFF"
        let ts = message["timestamp"] as? Double ?? Date().timeIntervalSince1970
        self.timestamp = Date(timeIntervalSince1970: ts)
    }
}
