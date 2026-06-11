import Foundation

class WebSocketManager: ObservableObject {
    var baseURL = "http://192.168.1.206:8000"  // Update to your Mac's IP
    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var reconnectDelay: TimeInterval = 1.0

    var onConnectionChange: ((Bool) -> Void)?
    var onMessage: (([String: Any]) -> Void)?

    func connect() {
        let wsURL = baseURL.replacingOccurrences(of: "http://", with: "ws://")
            .replacingOccurrences(of: "https://", with: "wss://")

        guard let url = URL(string: "\(wsURL)/ws") else { return }

        session = URLSession(configuration: .default)
        webSocket = session?.webSocketTask(with: url)
        webSocket?.resume()

        onConnectionChange?(true)
        reconnectDelay = 1.0

        receiveMessage()
    }

    func disconnect() {
        webSocket?.cancel(with: .goingAway, reason: nil)
        onConnectionChange?(false)
    }

    func send(_ data: [String: Any]) {
        guard let jsonData = try? JSONSerialization.data(withJSONObject: data),
              let jsonString = String(data: jsonData, encoding: .utf8) else { return }

        webSocket?.send(.string(jsonString)) { error in
            if let error = error {
                print("WebSocket send error: \(error)")
            }
        }
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .string(let text):
                    if let data = text.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                        self?.onMessage?(json)
                    }
                default:
                    break
                }
                self?.receiveMessage()

            case .failure(let error):
                print("WebSocket receive error: \(error)")
                self?.onConnectionChange?(false)
                self?.scheduleReconnect()
            }
        }
    }

    private func scheduleReconnect() {
        DispatchQueue.main.asyncAfter(deadline: .now() + reconnectDelay) { [weak self] in
            self?.reconnectDelay = min((self?.reconnectDelay ?? 1) * 1.5, 30)
            self?.connect()
        }
    }
}
