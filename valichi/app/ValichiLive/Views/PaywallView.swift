import SwiftUI
import StoreKit

struct PaywallView: View {
    @EnvironmentObject private var data: DataStore
    @EnvironmentObject private var store: StoreManager
    @Environment(\.dismiss) private var dismiss
    let zone: Catalog.Zone

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(zone.localizedName)
                            .font(.title2.bold())
                        if let blurb = zone.localizedBlurb {
                            Text(blurb)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                        if let catalog = data.catalog {
                            let attivi = catalog.crossings(in: zone.id).filter(\.isActive)
                            Text("\(attivi.count) valichi attivi oggi — i nuovi entrano nel pacchetto senza costi aggiuntivi.")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }

                Section {
                    if let product = store.product(id: zone.product) {
                        purchaseRow(product,
                                    title: zone.localizedName,
                                    subtitle: "Sblocca questa zona")
                    }
                    if let europa = data.catalog?.europaProduct,
                       let product = store.product(id: europa.id) {
                        purchaseRow(product,
                                    title: "Tutta Europa",
                                    subtitle: "Tutte le zone, incluse quelle future")
                    }
                    if store.products.isEmpty {
                        Text(store.lastError ?? "Prodotti non disponibili. In sviluppo: seleziona Products.storekit nello scheme (Run → Options → StoreKit Configuration).")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                } footer: {
                    Text("Acquisti una tantum, niente abbonamenti. Ogni acquisto rimuove anche la pubblicità. Family Sharing supportato.")
                }

                Section {
                    Button("Ripristina acquisti") {
                        Task { await store.restore() }
                    }
                }
            }
            .navigationTitle("Sblocca")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Chiudi") { dismiss() }
                }
            }
            .onChange(of: store.purchased) { _, _ in
                if store.isUnlocked(zone: zone.id, catalog: data.catalog) {
                    dismiss()
                }
            }
        }
    }

    private func purchaseRow(_ product: Product, title: String, subtitle: String) -> some View {
        Button {
            Task { await store.purchase(product) }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.headline)
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Text(product.displayPrice)
                    .font(.headline)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .background(Color.accentColor.opacity(0.15), in: Capsule())
            }
        }
        .tint(.primary)
    }
}
