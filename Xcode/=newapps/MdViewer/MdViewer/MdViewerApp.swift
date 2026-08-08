import SwiftUI

/// MdViewer — un clone di MdPreview: visualizza, legge e stampa file Markdown.
@main
struct MdViewerApp: App {
    var body: some Scene {
        DocumentGroup(viewing: MarkdownDocument.self) { configuration in
            ContentView(document: configuration.document,
                        fileURL: configuration.fileURL)
        }
        .commands {
            MdViewerCommands()
        }
    }
}
