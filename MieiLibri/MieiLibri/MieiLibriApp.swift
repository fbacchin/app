import SwiftUI

@main
struct MieiLibriApp: App {
    @StateObject private var library = Library()
    @State private var messaggio: String?

    var body: some Scene {
        WindowGroup {
            LibraryView()
                .environmentObject(library)
                // L'app viene aperta dalla pagina di conferma dell'email, che
                // le passa i token dell'accesso appena convalidato.
                .onOpenURL { url in
                    Task {
                        if let esito = await library.handleCallback(url) {
                            messaggio = esito
                        }
                    }
                }
                .alert(
                    "Account",
                    isPresented: Binding(
                        get: { messaggio != nil },
                        set: { if !$0 { messaggio = nil } }
                    )
                ) {
                    Button("Va bene", role: .cancel) { messaggio = nil }
                } message: {
                    Text(messaggio ?? "")
                }
        }
        #if os(macOS)
        .defaultSize(width: 950, height: 640)
        #endif
    }
}
