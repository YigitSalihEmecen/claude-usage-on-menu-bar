// User-visible settings, persisted to UserDefaults.

import Foundation
import Observation
import ServiceManagement

enum MenuBarDisplay: String, CaseIterable, Identifiable {
    case percentAndTime
    case percent
    case time
    case iconOnly

    var id: String { rawValue }

    var label: String {
        switch self {
        case .percentAndTime: return "Usage and reset"
        case .percent: return "Usage only"
        case .time: return "Reset only"
        case .iconOnly: return "Icon only"
        }
    }

    var showsPercent: Bool { self == .percentAndTime || self == .percent }
    var showsTime: Bool { self == .percentAndTime || self == .time }
}

@MainActor
@Observable
final class Preferences {
    var display: MenuBarDisplay {
        didSet { defaults.set(display.rawValue, forKey: Key.display) }
    }

    /// Seconds between usage fetches.
    var refreshInterval: Int {
        didSet { defaults.set(refreshInterval, forKey: Key.refreshInterval) }
    }

    /// Fraction above which the menu bar tints as a warning.
    var warnThreshold: Double {
        didSet { defaults.set(warnThreshold, forKey: Key.warnThreshold) }
    }

    var launchAtLogin: Bool {
        didSet {
            guard launchAtLogin != oldValue else { return }
            applyLaunchAtLogin()
        }
    }

    private let defaults = UserDefaults.standard

    private enum Key {
        static let display = "menuBarDisplay"
        static let refreshInterval = "refreshInterval"
        static let warnThreshold = "warnThreshold"
    }

    static let refreshOptions = [30, 60, 120, 300]

    init() {
        display = MenuBarDisplay(rawValue: defaults.string(forKey: Key.display) ?? "") ?? .percentAndTime
        refreshInterval = defaults.object(forKey: Key.refreshInterval) as? Int ?? 60
        warnThreshold = defaults.object(forKey: Key.warnThreshold) as? Double ?? 0.8
        launchAtLogin = SMAppService.mainApp.status == .enabled
    }

    private func applyLaunchAtLogin() {
        do {
            if launchAtLogin {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
    }
}
