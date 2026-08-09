import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var data: DataStore
    @EnvironmentObject private var store: StoreManager
    @State private var paywallZone: Catalog.Zone?

    var body: some View {
        NavigationStack {
            Group {
                if let catalog = data.catalog {
                    list(for: catalog)
                } else if let error = data.lastError {
                    ContentUnavailableView {
                        Label("Dati non disponibili", systemImage: "wifi.exclamationmark")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("Riprova") { Task { await data.refresh() } }
                    }
                } else {
                    ProgressView("Carico i valichi…")
                }
            }
            .navigationTitle("Valichi Live")
            .toolbar {
                Menu {
                    Button("Ripristina acquisti") { Task { await store.restore() } }
                    Link("Supporto", destination: APIConfig.supportURL)
                    Link("Privacy", destination: APIConfig.privacyURL)
                } label: {
                    Image(systemName: "gearshape")
                }
            }
            .task {
                data.loadBundledCatalog()
                await data.refresh()
                await store.bootstrap(with: data.catalog)
            }
            .refreshable { await data.refresh() }
            .sheet(item: $paywallZone) { zone in
                PaywallView(zone: zone)
            }
        }
    }

    private func list(for catalog: Catalog) -> some View {
        List {
            if let time = ISO.date(data.latest?.time) {
                Section {
                    HStack(spacing: 6) {
                        Image(systemName: "clock")
                        Text("Aggiornato ")
                        Text(time, style: .relative)
                        Text(" fa")
                    }
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .listRowBackground(Color.clear)
                }
            }
            ForEach(catalog.zones) { zone in
                Section {
                    ForEach(catalog.crossings(in: zone.id)) { crossing in
                        row(for: crossing, zone: zone, catalog: catalog)
                    }
                } header: {
                    HStack {
                        Text(zone.localizedName)
                        if !store.isUnlocked(zone: zone.id, catalog: catalog) {
                            Image(systemName: "lock.fill")
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func row(for crossing: Catalog.Crossing,
                     zone: Catalog.Zone,
                     catalog: Catalog) -> some View {
        if !crossing.isActive {
            CrossingRow(crossing: crossing, state: nil, free: false, comingSoon: true)
                .foregroundStyle(.secondary)
        } else if store.canView(crossing, catalog: catalog) {
            NavigationLink {
                CrossingView(crossing: crossing)
            } label: {
                CrossingRow(crossing: crossing,
                            state: data.state(for: crossing.id),
                            free: catalog.app.free.contains(crossing.id),
                            comingSoon: false)
            }
        } else {
            Button {
                paywallZone = zone
            } label: {
                HStack {
                    CrossingRow(crossing: crossing, state: nil, free: false, comingSoon: false)
                    Spacer()
                    Image(systemName: "lock.fill")
                        .foregroundStyle(.secondary)
                }
            }
            .tint(.primary)
        }
    }
}

struct CrossingRow: View {
    let crossing: Catalog.Crossing
    let state: CrossingState?
    let free: Bool
    let comingSoon: Bool

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(crossing.name)
                        .font(.headline)
                    if free {
                        Text("GRATIS")
                            .font(.caption2.bold())
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.green.opacity(0.2), in: Capsule())
                    }
                }
                if let route = crossing.route {
                    Text(route)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            if comingSoon {
                Text("In arrivo")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else if let state {
                WaitBadge(wait: state.worstWait, held: state.held == true)
            }
        }
    }
}

struct WaitBadge: View {
    let wait: Int?
    let held: Bool

    var body: some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text(waitText(wait))
                .font(.subheadline.bold())
                .foregroundStyle(waitColor(wait))
            if held {
                Text("mantenuto")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

func waitText(_ wait: Int?) -> String {
    guard let wait else { return "—" }
    if wait == 0 { return "libero" }
    if wait >= 60 {
        let h = wait / 60
        let m = wait % 60
        return m == 0 ? "~\(h) h" : "~\(h) h \(m) min"
    }
    return "~\(wait) min"
}

func waitColor(_ wait: Int?) -> Color {
    guard let wait else { return .gray }
    switch wait {
    case ..<15: return .green
    case ..<45: return .yellow
    case ..<120: return .orange
    default: return .red
    }
}
