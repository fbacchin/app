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

    /// Riga da mostrare: evita di ripetere il numero quando la versione lo
    /// contiene già, come accade nelle build prodotte da GitHub Actions.
    static var descrizione: String {
        versione.hasSuffix(".\(build)") ? "Versione \(versione)"
                                        : "Versione \(versione) (\(build))"
    }
}
