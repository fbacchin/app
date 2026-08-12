import Foundation

/// Personalizzazione del Maestro.
enum YodaConfig {
    /// Scrivi qui il nome della padawan (es. "Giulia"): Yoda la chiamerà per nome.
    /// Se resta vuoto, userà "giovane padawan".
    static let nomePadawan: String = ""

    static var appellativo: String {
        nomePadawan.isEmpty ? "giovane padawan" : nomePadawan
    }
}
