import SwiftUI

/// Azioni esposte dalla finestra attiva ai menu dell'app.
struct MdActions {
    var showingSource: Bool
    var toggleSource: () -> Void
    var printDocument: () -> Void
    var exportPDF: () -> Void
    var zoomIn: () -> Void
    var zoomOut: () -> Void
    var zoomReset: () -> Void
    var reload: () -> Void
}

private struct MdActionsKey: FocusedValueKey {
    typealias Value = MdActions
}

extension FocusedValues {
    var mdActions: MdActions? {
        get { self[MdActionsKey.self] }
        set { self[MdActionsKey.self] = newValue }
    }
}

/// Menu dell'app: stampa, esportazione PDF, zoom e vista sorgente.
struct MdViewerCommands: Commands {
    @FocusedValue(\.mdActions) private var actions

    var body: some Commands {
        CommandGroup(replacing: .printItem) {
            Button("Stampa…") { actions?.printDocument() }
                .keyboardShortcut("p", modifiers: .command)
                .disabled(actions == nil)
            Button("Esporta come PDF…") { actions?.exportPDF() }
                .keyboardShortcut("e", modifiers: [.command, .shift])
                .disabled(actions == nil)
        }
        CommandGroup(after: .toolbar) {
            Button(actions?.showingSource == true ? "Mostra anteprima" : "Mostra sorgente Markdown") {
                actions?.toggleSource()
            }
            .keyboardShortcut("u", modifiers: [.command, .option])
            .disabled(actions == nil)

            Divider()

            Button("Ingrandisci") { actions?.zoomIn() }
                .keyboardShortcut("+", modifiers: .command)
                .disabled(actions == nil)
            Button("Riduci") { actions?.zoomOut() }
                .keyboardShortcut("-", modifiers: .command)
                .disabled(actions == nil)
            Button("Dimensioni effettive") { actions?.zoomReset() }
                .keyboardShortcut("0", modifiers: .command)
                .disabled(actions == nil)

            Divider()

            Button("Ricarica dal disco") { actions?.reload() }
                .keyboardShortcut("r", modifiers: .command)
                .disabled(actions == nil)
        }
    }
}
