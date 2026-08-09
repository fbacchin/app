import Foundation

/// Gli URL dei dati aggregati dal collector (stesso schema di Gottardo Live:
/// il device legge SOLO i file del repo, mai le fonti nazionali).
enum APIConfig {
    static let base = URL(string: "https://raw.githubusercontent.com/fbacchin/app/main/valichi/")!

    static var catalogURL: URL { base.appendingPathComponent("catalog.json") }
    static var latestURL: URL { base.appendingPathComponent("data/latest.json") }
    static var historyURL: URL { base.appendingPathComponent("data/history.json") }

    static let supportURL = URL(string: "https://fbacchin.github.io/app/valichi/support-valichi.html")!
    static let privacyURL = URL(string: "https://fbacchin.github.io/app/valichi/privacy-valichi.html")!
}
