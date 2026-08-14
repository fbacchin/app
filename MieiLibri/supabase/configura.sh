#!/bin/bash
# Scrive le coordinate del progetto Supabase dentro SupabaseConfig.swift.
#
#   ./configura.sh https://abcdefgh.supabase.co sb_publishable_xxxxxxxx
#
# I due valori si trovano nella dashboard di Supabase, in
# Project Settings → API ("Project URL" e "publishable key" / "anon key").

set -euo pipefail

URL="${1:-}"
KEY="${2:-}"

if [ -z "$URL" ] || [ -z "$KEY" ]; then
  echo "Uso: $0 <project-url> <publishable-key>" >&2
  echo "Esempio: $0 https://abcdefgh.supabase.co sb_publishable_xxxxxxxx" >&2
  exit 1
fi

if [[ "$URL" != https://*.supabase.co ]]; then
  echo "Attenzione: l'indirizzo dovrebbe avere la forma https://<progetto>.supabase.co" >&2
fi

CONFIG="$(cd "$(dirname "$0")/.." && pwd)/MieiLibri/Services/SupabaseConfig.swift"

if [ ! -f "$CONFIG" ]; then
  echo "File non trovato: $CONFIG" >&2
  exit 1
fi

cat > "$CONFIG" <<SWIFT
import Foundation

/// Coordinate del progetto Supabase che ospita la sincronizzazione.
///
/// La chiave "publishable" è pensata per essere distribuita con le app:
/// i dati sono protetti dalle policy di Row Level Security sul server,
/// quindi ogni utente vede soltanto i propri libri.
enum SupabaseConfig {
    static let url = URL(string: "${URL}")!
    static let anonKey = "${KEY}"

    /// True quando il file è ancora da compilare con i dati del progetto.
    static var isPlaceholder: Bool {
        anonKey.hasPrefix("CONFIGURA")
    }
}
SWIFT

echo "Configurato: $CONFIG"
echo "Ora ricompila l'app in Xcode (⌘R)."
