import SwiftUI
import Charts

struct CrossingView: View {
    @EnvironmentObject private var data: DataStore
    let crossing: Catalog.Crossing
    @State private var chartHours = 24

    private var state: CrossingState? { data.state(for: crossing.id) }

    var body: some View {
        List {
            Section {
                ForEach(crossing.orderedDirections, id: \.self) { direction in
                    directionCard(direction)
                }
            } footer: {
                if let updated = ISO.date(state?.updated) {
                    HStack(spacing: 4) {
                        if state?.held == true {
                            Image(systemName: "pause.circle")
                            Text("Fonte muta: ultimo valore osservato ")
                        } else {
                            Text("Aggiornato ")
                        }
                        Text(updated, style: .relative)
                        Text(" fa")
                    }
                }
            }

            Section("Andamento") {
                Picker("Ore", selection: $chartHours) {
                    Text("12 h").tag(12)
                    Text("24 h").tag(24)
                    Text("48 h").tag(48)
                }
                .pickerStyle(.segmented)
                chart
                    .frame(height: 220)
                    .listRowSeparator(.hidden)
            }

            if let health = data.sourceHealth(for: crossing), health.ok == false {
                Section {
                    Label("Fonte momentaneamente non disponibile",
                          systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
                    .font(.footnote)
                }
            }

            if let note = crossing.note {
                Section("Note") {
                    Text(note)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(crossing.name)
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await data.refresh() }
    }

    private func directionCard(_ direction: String) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(crossing.label(for: direction))
                    .font(.subheadline)
                if let route = crossing.route {
                    Text(route)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Text(waitText(state?.wait(for: direction)))
                .font(.title3.bold())
                .foregroundStyle(waitColor(state?.wait(for: direction)))
        }
        .padding(.vertical, 4)
    }

    private struct Series {
        let label: String
        let points: [DataStore.ChartPoint]
    }

    private var chart: some View {
        let seriesList: [Series] = crossing.orderedDirections.map { direction in
            Series(label: crossing.label(for: direction),
                   points: data.series(for: crossing.id, direction: direction, hours: chartHours))
        }
        return Chart {
            ForEach(seriesList, id: \.label) { series in
                ForEach(series.points) { point in
                    LineMark(
                        x: .value("Ora", point.date),
                        y: .value("Minuti", point.wait)
                    )
                }
                .foregroundStyle(by: .value("Direzione", series.label))
                .interpolationMethod(.monotone)
            }
        }
        .chartYAxisLabel("min")
        .overlay {
            if seriesList.allSatisfy({ $0.points.isEmpty }) {
                Text("Ancora nessun campione in questa finestra")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }
}
