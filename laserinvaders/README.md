# Laser Invaders 👾

Sparatutto arcade stile anni '80 (ondate di alieni, laser, bunker, UFO misterioso),
scritto come **webapp in un singolo file** — niente dipendenze, niente build, funziona anche offline.

## Come si gioca

- **Desktop**: frecce ← → (o A/D) per muovere, **SPAZIO** per sparare, **P** pausa, **M** audio.
- **iPhone / iPad**: trascina il dito sullo schermo per muovere la navicella, oppure usa i
  pulsanti ◀ ▶ e **FUOCO** (tieni premuto per il fuoco automatico).
- Vita extra a 1.500 punti. L'UFO rosso vale da 50 a 300 punti… mistero!
- Il record resta salvato sul dispositivo.

## Caratteristiche

- Estetica CRT autentica: scanline, maschera RGB, vignettatura, accensione del tubo catodico.
- Colori "a bande" come i cabinet del 1978-82: il monitor era monocromatico con strisce di
  gelatina colorata, quindi gli alieni **cambiano colore mentre scendono**.
- Audio 100% sintetizzato con Web Audio API: il "pew" laser (doppio oscillatore in caduta
  esponenziale, stile disco anni '80), esplosioni, la marcia a 4 note che accelera, sirena UFO.
- Font pixel (Press Start 2P) incorporato in base64: nessuna richiesta esterna.
- PWA completa: manifest, service worker, icone — installabile e giocabile offline.

## Provarlo

- **Online** (quando il branch è su `main`): `https://fbacchin.github.io/app/laserinvaders/`
- **In locale**: `python3 -m http.server` dentro questa cartella, poi apri `http://localhost:8000`.
  (Aprire `index.html` direttamente funziona lo stesso; solo il service worker resta disattivo.)

## Passaggio ad app iPhone/iPad (fase 2)

Due strade, in ordine di sforzo:

1. **Subito, senza App Store** — apri l'URL in Safari su iPhone/iPad →
   Condividi → *Aggiungi alla schermata Home*. Grazie al manifest si apre a tutto schermo,
   con la sua icona, e funziona offline: di fatto è già un'app.
2. **App Store** — impacchettare questa stessa webapp con
   [Capacitor](https://capacitorjs.com) (`npx cap add ios`) in un progetto Xcode:
   il gioco gira in una WKWebView senza modifiche al codice. Servono un Mac con Xcode
   e l'account Apple Developer. Il codice è già pronto per questo passaggio
   (viewport con safe-area, audio sbloccato al primo tocco, controlli touch, niente risorse esterne).

## File

| File | Ruolo |
| --- | --- |
| `index.html` | Tutto il gioco: markup, CSS CRT, motore, sprite, audio |
| `manifest.webmanifest` | Metadati PWA (nome, icone, fullscreen, orientamento) |
| `sw.js` | Service worker cache-first per l'uso offline |
| `icon-180.png` / `icon-512.png` | Icone per home screen e install |
