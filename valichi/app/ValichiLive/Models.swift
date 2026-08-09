import Foundation

// MARK: - catalog.json

struct Catalog: Codable {
    struct AppInfo: Codable {
        struct ProductRef: Codable, Identifiable {
            var id: String
            var type: String
            var zone: String
        }
        var workingName: String
        var free: [String]
        var products: [ProductRef]
    }

    struct Zone: Codable, Identifiable {
        var id: String
        var product: String
        var name: [String: String]
        var blurb: [String: String]?

        var localizedName: String { Catalog.pick(name) }
        var localizedBlurb: String? { blurb.map(Catalog.pick) }
    }

    struct Coord: Codable {
        var lat: Double
        var lon: Double
        var approx: Bool?
    }

    struct Crossing: Codable, Identifiable {
        var id: String
        var zone: String
        var status: String
        var source: String?
        var name: String
        var countries: [String]
        var route: String?
        var coord: Coord?
        var directions: [String: String]?
        var note: String?

        var isActive: Bool { status == "active" }

        /// Le direzioni in ordine stabile: prima l'uscita, poi l'entrata
        /// (o sud/nord per i tunnel), poi eventuali altre in ordine alfabetico.
        var orderedDirections: [String] {
            let order = ["exit", "entry", "south", "north"]
            let keys = Array((directions ?? [:]).keys)
            return keys.sorted { a, b in
                let ia = order.firstIndex(of: a) ?? order.count
                let ib = order.firstIndex(of: b) ?? order.count
                return ia == ib ? a < b : ia < ib
            }
        }

        func label(for direction: String) -> String {
            directions?[direction] ?? direction
        }
    }

    var version: Int
    var updated: String
    var app: AppInfo
    var zones: [Zone]
    var crossings: [Crossing]

    func crossings(in zoneID: String) -> [Crossing] {
        crossings.filter { $0.zone == zoneID }
    }

    func product(forZone zoneID: String) -> AppInfo.ProductRef? {
        app.products.first { $0.zone == zoneID }
    }

    var europaProduct: AppInfo.ProductRef? {
        app.products.first { $0.zone == "*" }
    }

    static func pick(_ localized: [String: String]) -> String {
        let lang = Locale.current.language.languageCode?.identifier ?? "en"
        return localized[lang] ?? localized["en"] ?? localized.values.first ?? ""
    }
}

// MARK: - data/latest.json

struct WaitValue: Codable {
    var wait: Int?
}

struct CrossingState: Codable {
    var updated: String?
    var held: Bool?
    var directions: [String: WaitValue]?

    func wait(for direction: String) -> Int? {
        directions?[direction]?.wait
    }

    /// L'attesa peggiore fra le direzioni note (per la riga in lista).
    var worstWait: Int? {
        directions?.values.compactMap(\.wait).max()
    }
}

struct SourceHealth: Codable {
    var ok: Bool
    var error: String?
    var url: String?
    var found: Int?
    var of: Int?
    var sampled: String?
}

struct Latest: Codable {
    var time: String
    var catalogVersion: Int?
    var crossings: [String: CrossingState]
    var sources: [String: SourceHealth]?
}

// MARK: - data/history.json

struct HistorySample: Codable {
    var time: String
    var w: [String: Int]
    var held: [String]?
}

// MARK: - date

enum ISO {
    static let formatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func date(_ string: String?) -> Date? {
        guard let string else { return nil }
        return formatter.date(from: string)
    }
}
