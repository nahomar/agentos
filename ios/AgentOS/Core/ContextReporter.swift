import Foundation
import UIKit

class ContextReporter {
    private var timer: Timer?

    func startReporting(wsManager: WebSocketManager, locationManager: LocationManager) {
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.report(wsManager: wsManager, locationManager: locationManager)
        }
        // Report immediately
        report(wsManager: wsManager, locationManager: locationManager)
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func report(wsManager: WebSocketManager, locationManager: LocationManager) {
        var contextData: [String: Any] = [
            "screen_on": UIApplication.shared.applicationState == .active,
            "battery_level": Int(UIDevice.current.batteryLevel * 100),
        ]

        if let location = locationManager.lastLocation {
            contextData["lat"] = location.coordinate.latitude
            contextData["lon"] = location.coordinate.longitude
        }

        wsManager.send([
            "type": "context_update",
            "data": contextData,
        ])
    }
}
