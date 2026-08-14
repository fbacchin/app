import SwiftUI

@main
struct MieiLibriApp: App {
    @StateObject private var library = Library()

    var body: some Scene {
        WindowGroup {
            LibraryView()
                .environmentObject(library)
        }
        #if os(macOS)
        .defaultSize(width: 950, height: 640)
        #endif
    }
}
