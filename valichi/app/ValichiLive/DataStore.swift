import Foundation

/// Carica catalogo e dati: prima la copia impacchettata del catalogo (per
/// avere subito la struttura anche offline), poi le versioni remote dal repo.
/// Il catalogo remoto vince su quello nel bundle: un valico nuovo o un
/// matchName corretto arrivano senza passare da una release.
@MainActor
final class DataStore: ObservableObject {
    @Published private(set) var catalog: Catalog?
    @Published private(set) var latest: Latest?
    @Published private(set) var history: [HistorySample] = []
    @Published private(set) var lastError: String?
    @Published private(set) var refreshing = false

    func loadBundledCatalog() {
        guard catalog == nil,
              let url = Bundle.main.url(forResource: "catalog", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let bundled = try? JSONDecoder().decode(Catalog.self, from: data)
        else { return }
        catalog = bundled
    }

    func refresh() async {
        refreshing = true
        defer { refreshing = false }
        do {
            async let c: Catalog = fetch(APIConfig.catalogURL)
            async let l: Latest = fetch(APIConfig.latestURL)
            async let h: [HistorySample] = fetch(APIConfig.historyURL)
            let (cat, lat, his) = try await (c, l, h)
            catalog = cat
            latest = lat
            history = his
            lastError = nil
        } catch {
            // La copia bundled e l'ultimo stato scaricato restano in piedi:
            // un refresh fallito non deve svuotare la schermata.
            lastError = error.localizedDescription
        }
    }

    private func fetch<T: Decodable>(_ url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(T.self, from: data)
    }

    // MARK: - letture comode

    func state(for crossingID: String) -> CrossingState? {
        latest?.crossings[crossingID]
    }

    func sourceHealth(for crossing: Catalog.Crossing) -> SourceHealth? {
        guard let source = crossing.source else { return nil }
        return latest?.sources?[source]
    }

    struct ChartPoint: Identifiable {
        let id = UUID()
        let date: Date
        let wait: Int
    }

    /// La serie di un valico/direzione nelle ultime `hours` ore.
    func series(for crossingID: String, direction: String, hours: Int) -> [ChartPoint] {
        let key = "\(crossingID).\(direction)"
        let cutoff = Date().addingTimeInterval(-Double(hours) * 3600)
        return history.compactMap { sample in
            guard let date = ISO.date(sample.time), date > cutoff,
                  let wait = sample.w[key] else { return nil }
            return ChartPoint(date: date, wait: wait)
        }
    }
}
