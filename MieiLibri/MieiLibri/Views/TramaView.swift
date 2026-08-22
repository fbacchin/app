import SwiftUI

/// La trama per esteso, aperta toccandone l'anteprima fra i risultati.
struct TramaView: View {
    var titolo: String
    var autori: String
    var anno: String?
    var testo: String
    var coverURL: URL?

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(alignment: .top, spacing: 14) {
                        BookCoverView(image: nil, url: coverURL, width: 66)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(titolo)
                                .font(.title3.bold())
                            Text(autori)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                            if let anno {
                                Text(anno)
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        Spacer(minLength: 0)
                    }

                    Divider()

                    TestoGiustificato(testo: testo, stile: .corpo, attenuato: false)
                }
                .padding(20)
            }
            .navigationTitle("Trama")
            .inlineNavigationTitle()
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Chiudi") { dismiss() }
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 520, minHeight: 480)
        #endif
    }
}
