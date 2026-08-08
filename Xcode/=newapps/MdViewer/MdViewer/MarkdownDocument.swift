import SwiftUI
import UniformTypeIdentifiers

extension UTType {
    /// Tipo Markdown dichiarato (importato) in Info.plist.
    static let markdown = UTType(importedAs: "net.daringfireball.markdown")
}

/// Documento di sola lettura: il testo Markdown così com'è sul disco.
struct MarkdownDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.markdown, .plainText] }

    var text: String

    init(text: String = "") {
        self.text = text
    }

    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents else {
            throw CocoaError(.fileReadCorruptFile)
        }
        self.text = Self.decodeText(from: data)
    }

    /// Decodifica con fallback: UTF-8, poi UTF-16 (con BOM), poi Latin-1.
    static func decodeText(from data: Data) -> String {
        if let text = String(data: data, encoding: .utf8) { return text }
        if let text = String(data: data, encoding: .utf16) { return text }
        return String(data: data, encoding: .isoLatin1) ?? ""
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        // L'app è un visualizzatore: non salva mai, ma il protocollo lo richiede.
        FileWrapper(regularFileWithContents: Data(text.utf8))
    }
}
