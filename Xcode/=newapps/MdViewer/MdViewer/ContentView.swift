import AppKit
import SwiftUI
import WebKit

/// Finestra del documento: anteprima renderizzata, vista sorgente, zoom,
/// stampa ed esportazione PDF.
struct ContentView: View {
    let document: MarkdownDocument
    let fileURL: URL?

    @StateObject private var proxy = WebViewProxy()
    @AppStorage("MdViewerPageZoom") private var zoom: Double = 1.0
    @State private var showSource = false
    @State private var overrideText: String?
    @State private var reloadToken = 0

    /// Testo mostrato: quello ricaricato dal disco, se presente, altrimenti il documento.
    private var text: String { overrideText ?? document.text }

    var body: some View {
        ZStack {
            MarkdownWebView(html: MarkdownRenderer.page(for: text),
                            baseURL: fileURL?.deletingLastPathComponent(),
                            zoom: zoom,
                            reloadToken: reloadToken,
                            proxy: proxy)
            if showSource {
                SourceView(text: text)
            }
        }
        .frame(minWidth: 480, minHeight: 320)
        .safeAreaInset(edge: .bottom, spacing: 0) { statusBar }
        .toolbar { toolbarContent }
        .focusedSceneValue(\.mdActions, actions)
        .onChange(of: document.text) { _ in overrideText = nil }
    }

    // MARK: - Barra strumenti e barra di stato

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItemGroup {
            Picker("Vista", selection: $showSource) {
                Text("Anteprima").tag(false)
                Text("Sorgente").tag(true)
            }
            .pickerStyle(.segmented)
            .help("Passa tra anteprima e sorgente Markdown (⌥⌘U)")

            Button(action: zoomOut) {
                Image(systemName: "minus.magnifyingglass")
            }
            .help("Riduci (⌘−)")

            Button(action: zoomIn) {
                Image(systemName: "plus.magnifyingglass")
            }
            .help("Ingrandisci (⌘+)")

            Button(action: reloadFromDisk) {
                Image(systemName: "arrow.clockwise")
            }
            .help("Ricarica dal disco (⌘R)")

            Button(action: printDocument) {
                Image(systemName: "printer")
            }
            .help("Stampa (⌘P)")

            Button(action: exportPDF) {
                Image(systemName: "square.and.arrow.down")
            }
            .help("Esporta come PDF (⇧⌘E)")
        }
    }

    private var statusBar: some View {
        HStack(spacing: 12) {
            Text(statistics)
            Spacer()
            Text("Zoom \(Int((zoom * 100).rounded())) %")
        }
        .font(.caption)
        .foregroundColor(.secondary)
        .padding(.horizontal, 12)
        .padding(.vertical, 5)
        .background(.bar)
    }

    private var statistics: String {
        let words = text.split(whereSeparator: \.isWhitespace).count
        guard words > 0 else { return "Documento vuoto" }
        let characters = text.count
        let minutes = max(1, Int((Double(words) / 200.0).rounded(.up)))
        return "\(words.formatted()) parole · \(characters.formatted()) caratteri · ~\(minutes) min di lettura"
    }

    private var actions: MdActions {
        MdActions(showingSource: showSource,
                  toggleSource: { showSource.toggle() },
                  printDocument: printDocument,
                  exportPDF: exportPDF,
                  zoomIn: zoomIn,
                  zoomOut: zoomOut,
                  zoomReset: zoomReset,
                  reload: reloadFromDisk)
    }

    // MARK: - Azioni

    private func zoomIn() {
        zoom = min(3.0, ((zoom + 0.1) * 10).rounded() / 10)
    }

    private func zoomOut() {
        zoom = max(0.5, ((zoom - 0.1) * 10).rounded() / 10)
    }

    private func zoomReset() {
        zoom = 1.0
    }

    /// Rilegge il file dal disco e forza il ricaricamento dell'anteprima
    /// (utile se il file o le sue immagini sono cambiati in un altro editor).
    private func reloadFromDisk() {
        if let url = fileURL, let data = try? Data(contentsOf: url) {
            overrideText = MarkdownDocument.decodeText(from: data)
        }
        reloadToken += 1
    }

    // MARK: - Stampa ed esportazione

    private func makePrintInfo() -> NSPrintInfo {
        let info = NSPrintInfo(dictionary: [:])
        info.horizontalPagination = .fit
        info.verticalPagination = .automatic
        info.isHorizontallyCentered = true
        info.isVerticallyCentered = false
        info.topMargin = 36
        info.bottomMargin = 36
        info.leftMargin = 36
        info.rightMargin = 36
        return info
    }

    private func configure(_ operation: NSPrintOperation, webView: WKWebView) {
        operation.jobTitle = fileURL?.lastPathComponent ?? "Documento Markdown"
        // Workaround per un difetto noto di WKWebView: la vista di stampa nasce con frame nullo.
        operation.view?.frame = NSRect(origin: .zero, size: webView.bounds.size)
    }

    private func printDocument() {
        guard let webView = proxy.webView, let window = webView.window else { return }
        let operation = webView.printOperation(with: makePrintInfo())
        operation.showsPrintPanel = true
        operation.showsProgressPanel = true
        operation.printPanel.options.insert([.showsPaperSize, .showsOrientation, .showsScaling])
        configure(operation, webView: webView)
        operation.runModal(for: window, delegate: nil, didRun: nil, contextInfo: nil)
    }

    private func exportPDF() {
        guard let webView = proxy.webView, let window = webView.window else { return }
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.pdf]
        let baseName = fileURL?.deletingPathExtension().lastPathComponent ?? "Documento"
        panel.nameFieldStringValue = baseName + ".pdf"
        panel.beginSheetModal(for: window) { response in
            guard response == .OK, let url = panel.url else { return }
            let info = makePrintInfo()
            info.jobDisposition = .save
            info.dictionary().setObject(url as NSURL,
                                        forKey: NSPrintInfo.AttributeKey.jobSavingURL.rawValue as NSString)
            let operation = webView.printOperation(with: info)
            operation.showsPrintPanel = false
            operation.showsProgressPanel = true
            configure(operation, webView: webView)
            operation.runModal(for: window, delegate: nil, didRun: nil, contextInfo: nil)
        }
    }
}

/// Vista del testo sorgente, in sola lettura ma selezionabile.
private struct SourceView: View {
    let text: String

    var body: some View {
        ScrollView {
            Text(text)
                .font(.system(size: 13, design: .monospaced))
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(16)
        }
        .background(Color(nsColor: .textBackgroundColor))
    }
}
