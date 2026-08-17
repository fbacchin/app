# Tetris per iOS

App nativa scritta in SwiftUI, senza dipendenze esterne. Regole moderne del gioco: rotazione SRS con wall kick, sacchetto da 7 pezzi, ghost piece, "tieni", anteprima dei 3 pezzi successivi, lock delay, curva di velocità guideline e punteggio 100/300/500/800 × livello. Il record resta salvato sul dispositivo e il gioco si mette in pausa da solo se l'app passa in secondo piano.

## Requisiti

- Xcode 16 o successivo
- iOS 17 o successivo (iPhone e iPad)

## Come eseguirla

1. Apri `Tetris.xcodeproj` in Xcode.
2. Solo per provarla su un iPhone vero: in **Signing & Capabilities** seleziona il tuo team (con il simulatore non serve).
3. Scegli un simulatore o il tuo dispositivo e premi **▶ Run**.

## Comandi

| Gesto / tasto | Azione |
| --- | --- |
| Trascina a destra/sinistra sul pozzo | Sposta il pezzo |
| Tocco sul pozzo | Ruota |
| Trascina verso il basso | Cala subito in fondo (hard drop) |
| Pulsanti ◀ ▼ ▶ | Movimento con auto-ripetizione (▼ discesa morbida) |
| ⟲ ⟳ | Rotazione |
| ⇄ | Tieni il pezzo |
| ⤓ | Cala subito |

Con una tastiera collegata (iPad): frecce per muovere, ↑ o X ruota, Z ruota al contrario, spazio cala, C tiene, P o Esc mette in pausa, Invio avvia.

## Versione web

La stessa partita si gioca dal browser: `giochi/tetris/index.html` in questo repository.
