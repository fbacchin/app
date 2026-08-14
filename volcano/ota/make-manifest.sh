#!/usr/bin/env bash
#
# Genera manifest.plist a partire da un .ipa.
#
# Il manifest che Xcode produce con "Include manifest for over-the-air
# installation" va bene, ma richiede di digitare tre URL a mano nella finestra
# di export — e quei tre URL sono il punto in cui l'installazione fallisce più
# spesso, perché un refuso non dà nessun errore visibile: iOS mostra solo
# "Impossibile installare".
#
# Questo script legge bundle identifier, versione e nome direttamente
# dall'Info.plist dentro l'.ipa, così i valori non possono divergere dal
# binario, e costruisce gli URL da un'unica base.
#
# Uso:
#   ./make-manifest.sh Volcano.ipa
#   ./make-manifest.sh Volcano.ipa https://fbacchin.github.io/app/volcano/ota
#
# Richiede: unzip, plutil (macOS). Da eseguire sul Mac.

set -euo pipefail

IPA="${1:-}"
BASE_URL="${2:-https://fbacchin.github.io/app/volcano/ota}"

if [[ -z "$IPA" ]]; then
    echo "Uso: $0 <file.ipa> [base-url]" >&2
    exit 1
fi

if [[ ! -f "$IPA" ]]; then
    echo "File non trovato: $IPA" >&2
    exit 1
fi

# HTTPS è obbligatorio: iOS rifiuta itms-services su HTTP senza nemmeno
# spiegare perché.
if [[ "$BASE_URL" != https://* ]]; then
    echo "La base URL deve essere HTTPS: $BASE_URL" >&2
    exit 1
fi

BASE_URL="${BASE_URL%/}"
IPA_NAME="$(basename "$IPA")"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# L'Info.plist sta in Payload/<Nome>.app/Info.plist, e il nome della cartella
# .app non è prevedibile: si cerca.
unzip -q -o "$IPA" 'Payload/*/Info.plist' -d "$WORKDIR" 2>/dev/null || {
    echo "Impossibile estrarre Info.plist da $IPA" >&2
    exit 1
}

INFO_PLIST="$(find "$WORKDIR/Payload" -maxdepth 2 -name 'Info.plist' | head -1)"
if [[ -z "$INFO_PLIST" ]]; then
    echo "Info.plist non trovato dentro l'.ipa" >&2
    exit 1
fi

read_key() {
    plutil -extract "$1" raw -o - "$INFO_PLIST" 2>/dev/null || echo ""
}

BUNDLE_ID="$(read_key CFBundleIdentifier)"
VERSION="$(read_key CFBundleShortVersionString)"
BUILD="$(read_key CFBundleVersion)"
TITLE="$(read_key CFBundleDisplayName)"
[[ -z "$TITLE" ]] && TITLE="$(read_key CFBundleName)"

if [[ -z "$BUNDLE_ID" ]]; then
    echo "CFBundleIdentifier non leggibile: l'.ipa sembra malformato" >&2
    exit 1
fi

cat > manifest.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>items</key>
	<array>
		<dict>
			<key>assets</key>
			<array>
				<dict>
					<key>kind</key>
					<string>software-package</string>
					<key>url</key>
					<string>${BASE_URL}/${IPA_NAME}</string>
				</dict>
				<dict>
					<key>kind</key>
					<string>display-image</string>
					<key>url</key>
					<string>${BASE_URL}/icon-57.png</string>
				</dict>
				<dict>
					<key>kind</key>
					<string>full-size-image</string>
					<key>url</key>
					<string>${BASE_URL}/icon-512.png</string>
				</dict>
			</array>
			<key>metadata</key>
			<dict>
				<key>bundle-identifier</key>
				<string>${BUNDLE_ID}</string>
				<key>bundle-version</key>
				<string>${VERSION}</string>
				<key>kind</key>
				<string>software</string>
				<key>title</key>
				<string>${TITLE}</string>
			</dict>
		</dict>
	</array>
</dict>
</plist>
PLIST

# Se il plist è malformato iOS non lo dice: fallisce e basta.
plutil -lint manifest.plist > /dev/null

SIZE_MB=$(( $(stat -f%z "$IPA" 2>/dev/null || stat -c%s "$IPA") / 1024 / 1024 ))

echo "manifest.plist creato"
echo "  app        : ${TITLE} ${VERSION} (${BUILD})"
echo "  bundle id  : ${BUNDLE_ID}"
echo "  ipa        : ${IPA_NAME} — ${SIZE_MB} MB"
echo "  base url   : ${BASE_URL}"
echo

if (( SIZE_MB > 95 )); then
    echo "⚠️  L'.ipa supera i 95 MB: git rifiuta i file oltre i 100 MB."
    echo "   Vedi README.md, sezione sui file grandi."
    echo
fi

echo "Prossimi passi:"
echo "  1. copia ${IPA_NAME} e manifest.plist in volcano/ota/"
echo "  2. commit e push sul branch servito da GitHub Pages"
echo "  3. apri ${BASE_URL}/ dall'iPhone e tocca Installa"
