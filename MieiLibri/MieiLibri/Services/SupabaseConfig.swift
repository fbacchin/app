import Foundation

/// Coordinate del progetto Supabase che ospita la sincronizzazione.
///
/// La chiave "publishable" è pensata per essere distribuita con le app:
/// i dati sono protetti dalle policy di Row Level Security sul server,
/// quindi ogni utente vede soltanto i propri libri.
enum SupabaseConfig {
    static let url = URL(string: "https://CONFIGURA-IL-PROGETTO.supabase.co")!
    static let anonKey = "CONFIGURA-LA-CHIAVE-PUBLISHABLE"

    /// True quando il file è ancora da compilare con i dati del progetto.
    static var isPlaceholder: Bool {
        anonKey.hasPrefix("CONFIGURA")
    }
}
