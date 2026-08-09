import Foundation
import StoreKit

/// Acquisti con StoreKit 2: i product ID arrivano dal catalogo (mappa
/// zona → prodotto), gli entitlement da Transaction.currentEntitlements.
/// Regole di sblocco:
///   - i valichi in catalog.app.free sono sempre visibili (il Gottardo);
///   - il prodotto della zona sblocca la zona;
///   - il prodotto "europa" (zone = "*") sblocca tutto, anche le zone future.
@MainActor
final class StoreManager: ObservableObject {
    @Published private(set) var products: [Product] = []
    @Published private(set) var purchased: Set<String> = []
    @Published private(set) var lastError: String?

    private var updatesTask: Task<Void, Never>?

    init() {
        // Le transazioni possono arrivare fuori dall'app (Family Sharing,
        // riscatti, Ask to Buy): il listener va su subito e per sempre.
        updatesTask = Task { [weak self] in
            for await update in Transaction.updates {
                if case .verified(let transaction) = update {
                    await transaction.finish()
                    await self?.refreshEntitlements()
                }
            }
        }
    }

    deinit {
        updatesTask?.cancel()
    }

    func bootstrap(with catalog: Catalog?) async {
        guard let catalog else { return }
        let ids = catalog.app.products.map(\.id)
        if products.isEmpty {
            do {
                products = try await Product.products(for: ids)
                lastError = nil
            } catch {
                lastError = error.localizedDescription
            }
        }
        await refreshEntitlements()
    }

    func refreshEntitlements() async {
        var owned: Set<String> = []
        for await entitlement in Transaction.currentEntitlements {
            if case .verified(let transaction) = entitlement,
               transaction.revocationDate == nil {
                owned.insert(transaction.productID)
            }
        }
        purchased = owned
    }

    func product(id: String) -> Product? {
        products.first { $0.id == id }
    }

    func purchase(_ product: Product) async {
        do {
            let result = try await product.purchase()
            switch result {
            case .success(let verification):
                if case .verified(let transaction) = verification {
                    await transaction.finish()
                    await refreshEntitlements()
                }
            case .userCancelled, .pending:
                break
            @unknown default:
                break
            }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func restore() async {
        // AppStore.sync() forza il refresh dal negozio (il pulsante che la
        // review di Apple vuole vedere); gli entitlement si rileggono comunque.
        try? await AppStore.sync()
        await refreshEntitlements()
    }

    // MARK: - sblocchi

    func isUnlocked(zone zoneID: String, catalog: Catalog?) -> Bool {
        guard let catalog else { return false }
        if let europa = catalog.europaProduct, purchased.contains(europa.id) {
            return true
        }
        if let product = catalog.product(forZone: zoneID), purchased.contains(product.id) {
            return true
        }
        return false
    }

    func canView(_ crossing: Catalog.Crossing, catalog: Catalog?) -> Bool {
        if catalog?.app.free.contains(crossing.id) == true { return true }
        return isUnlocked(zone: crossing.zone, catalog: catalog)
    }
}
