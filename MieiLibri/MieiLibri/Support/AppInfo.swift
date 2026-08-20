import Foundation

/// Identità della copia in esecuzione, mostrata nella schermata Account
/// così da sapere sempre quale build si ha installata.
enum AppInfo {
    /// Versione visibile, nella forma 1.0.<numero di build>.
    static var versione: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "—"
    }

    /// Numero di build. Coincide con l'ultima cifra della versione nelle
    /// build automatiche; nelle compilazioni locali può differire.
    static var build: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "—"
    }

    /// Riga da mostrare: la versione resta 1.0, fra parentesi il numero di
    /// build, che si incrementa a ogni compilazione automatica.
    static var descrizione: String {
        "Versione \(versione) (\(build))"
    }
}
