# Laser Invaders 🚀

Sparatutto arcade stile anni '80: squadriglie di astronavi nemiche arrivano in picchiata
**1, 2 o 3 alla volta** — abbattile col laser e raccogli le capsule **[P]** per potenziarlo:
singolo → **doppio** → **triplo**. Scritto come **webapp in un singolo file** — niente
dipendenze, niente build, funziona anche offline.

## Come si gioca

- **Desktop**: frecce ← → ↑ ↓ (o WASD) per muovere in ogni direzione — anche in
  diagonale — **SPAZIO** per sparare (tieni premuto: fuoco automatico), **P** pausa,
  **M** audio.
- **iPhone / iPad**: trascina il dito in qualsiasi punto dello schermo per muovere la
  navicella in ogni direzione (movimento relativo: il dito non copre mai la nave);
  un unico pulsante, **FUOCO** — tienilo premuto per sparare a raffica.
- Ogni 7 astronavi abbattute cade una capsula **[P]**. La scala dei potenziamenti è
  infinita: laser singolo → doppio → triplo, poi si riparte da un **raggio più lungo**
  che **trapassa le navi** (un colpo può abbatterne più d'una), di nuovo singolo →
  doppio → triplo, poi ancora più lungo, e così via.
- Se vieni colpito perdi una vita e il laser scende di un gradino.
- Vita extra ogni 2.500 punti. Il record resta salvato sul dispositivo.

## Le astronavi

| Nave | Comportamento | Colpi | Punti |
| --- | --- | --- | --- |
| Caccia (ciano) | Picchiata a serpentina, veloce | 1 | 50 |
| Incrociatore (magenta) | Attraversa lo schermo planando | 2 | 100 |
| Nave pesante (ambra) | Scende lenta a zig-zag | 3 | 150 |

## Caratteristiche

- Estetica CRT autentica: scanline, maschera RGB, vignettatura, accensione del tubo catodico.
- Audio 100% sintetizzato con Web Audio API: il "fiu fiu" del laser (glissando sinusoidale
  discendente, come i laser disco di "I Don't Feel Like Dancin'" degli Scissor Sisters —
  il timbro sale col laser potenziato), esplosioni, battito di fondo che accelera col livello.
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
