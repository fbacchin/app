# MdViewer

Un clone di **MdPreview** per macOS: visualizza, legge e stampa i file Markdown (`.md`).
App nativa SwiftUI + WebKit, senza dipendenze esterne da scaricare: si apre in Xcode e si compila subito.
Anteprima in stile GitHub, con tema chiaro/scuro automatico.

## Funzionalità

- **Anteprima renderizzata** di file `.md`, `.markdown`, `.mdown`, `.mkd`, `.txt` (GitHub Flavored Markdown: tabelle, elenchi attività, codice, citazioni, immagini…)
- **Stampa** con impaginazione corretta (⌘P) — formato carta, orientamento e scala dal pannello di stampa
- **Esportazione PDF** impaginata (⇧⌘E)
- **Vista sorgente** per leggere il Markdown grezzo (⌥⌘U)
- **Zoom** ⌘+ / ⌘− / ⌘0 (ricordato tra le sessioni), più pinch sul trackpad
- **Ricarica dal disco** (⌘R) se il file è stato modificato in un altro editor
- Immagini locali relative al file e immagini remote; i link esterni si aprono nel browser
- Barra di stato con conteggio parole, caratteri e tempo di lettura
- Documenti recenti, drag & drop sull'icona, finestre multiple, tema scuro

## Requisiti

- macOS 12 (Monterey) o successivo
- Xcode 14 o successivo

## Installazione sull'iMac

Il progetto vive nel repository `fbacchin/app` sotto `Xcode/=newapps/MdViewer`.

**Se hai già un clone del repository sull'iMac:**

```bash
cd /percorso/del/repo/app
git fetch origin
git checkout claude/mdpreview-clone-markdown-viewer-uaboo6   # oppure main, dopo il merge
```

Poi copia la cartella del progetto nella tua cartella di lavoro (adatta il percorso di destinazione):

```bash
cp -R "Xcode/=newapps/MdViewer" "$HOME/Xcode/=newapps/"
```

**Senza git:** scarica lo ZIP del branch da GitHub (Code ▸ Download ZIP) e copia la cartella `Xcode/=newapps/MdViewer` dove preferisci.

## Compilazione

1. Apri `MdViewer.xcodeproj` in Xcode.
2. Premi **⌘R**. La firma è "Sign to Run Locally", quindi non serve alcun team di sviluppo.
3. Per installarla stabilmente: **Product ▸ Archive ▸ Distribute App ▸ Copy App**, poi trascina `MdViewer.app` in `/Applicazioni`. (In alternativa, trascina l'app dalla cartella Products di Xcode.)

## Impostarla come app predefinita per i .md

Clic destro su un file `.md` nel Finder ▸ **Ottieni informazioni** ▸ *Apri con* ▸ scegli **MdViewer** ▸ **Modifica tutti…**

## Struttura del progetto

```
MdViewer/
├── MdViewer.xcodeproj          Progetto Xcode
├── MdViewer/
│   ├── MdViewerApp.swift       Entry point (DocumentGroup in sola lettura)
│   ├── MarkdownDocument.swift  Lettura del file (UTF-8/UTF-16/Latin-1)
│   ├── MarkdownRenderer.swift  Markdown → pagina HTML autosufficiente
│   ├── WebView.swift           WKWebView (anteprima, link esterni nel browser)
│   ├── ContentView.swift       Finestra: toolbar, zoom, stampa, PDF, barra di stato
│   ├── Commands.swift          Menu e scorciatoie di tastiera
│   ├── Info.plist              Tipi di documento Markdown (ruolo Viewer)
│   ├── Assets.xcassets         Icona dell'app
│   └── Resources/
│       ├── marked.min.js       Parser Markdown (marked v15, licenza MIT)
│       ├── markdown.css        Stile anteprima + regole di stampa
│       └── LICENSE-marked.md   Licenza di marked
├── Esempio.md                  File di prova con tutte le funzionalità
└── README.md
```

## Note tecniche

- Il rendering usa [marked](https://github.com/markedjs/marked) (MIT) incorporato nel bundle: l'app funziona completamente offline.
- La stampa passa da `NSPrintOperation` sulla WKWebView con CSS `@media print` dedicato: sfondo bianco, codice a capo automatico, tabelle e immagini non spezzate tra le pagine.
- L'app è un *visualizzatore*: non modifica mai i file (ruolo `Viewer` nei tipi di documento).
- App Sandbox disattivata per consentire il caricamento delle immagini relative accanto al file: è pensata per uso personale, non per l'App Store.
