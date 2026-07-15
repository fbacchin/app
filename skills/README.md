# Skills

> ⚠️ **Queste sono copie di riferimento, non le skill in esecuzione.**
> Modificare i file qui **non ha alcun effetto**. Vedi [Come modificarle](#come-modificarle).

Qui è versionato il sorgente delle skill di Claude che alimentano i dati di
questa repo. Servono a tre cose: avere la storia delle modifiche, tenere il
sorgente accanto agli script che le skill invocano, e poter rileggere cosa fa
una skill senza doverla esportare da Claude.

## Cosa c'è

| Cartella | Cos'è | Dove gira davvero |
|---|---|---|
| [`aggiorna-tassi/`](aggiorna-tassi/SKILL.md) | La skill vera e propria: scarica i tassi da global-rates.com, aggiorna i CSV nella cartella Libor su Google Drive e pubblica le date nuove in [`../Euribor/`](../Euribor/) | Installata su Claude come **Skill**, usata da **Cowork** |
| [`aggiorna-tassi-libor/`](aggiorna-tassi-libor/SKILL.md) | Il wrapper schedulato: invoca la skill qui sopra e scrive il riepilogo dell'esecuzione | Task schedulato, **da martedì a sabato alle 13:00** |

Il wrapper è schedulato dal martedì al sabato perché i fixing escono nei giorni
lavorativi: il lunedì non c'è nulla di nuovo da prendere (il dato del venerdì
arriva il sabato).

## Come modificarle

**Non modificare i file di questa cartella per cambiare il comportamento.** Le
copie in esecuzione stanno altrove:

- **`aggiorna-tassi`** è installata su **Claude come Skill**. Per cambiarla:
  aprire Claude, andare nelle competenze/skill e **sostituire la skill
  esistente** caricando il pacchetto aggiornato. Finché non la si sostituisce,
  Cowork e il task schedulato continuano a usare la versione precedente.
- **`aggiorna-tassi-libor`** è il task schedulato: il suo `SKILL.md` vive nella
  cartella locale di Claude, sotto `Scheduled/`.

Flusso consigliato quando si cambia qualcosa:

1. modificare il file qui e committarlo, così resta la storia;
2. ricaricare la skill su Claude (o aggiornare il file del task schedulato);
3. verificare alla prima esecuzione utile che il comportamento sia quello atteso.

Se le due copie divergono, **quella di Claude è quella che conta**: questa è solo
il riferimento.

## Dipendenze

`aggiorna-tassi` non lavora da sola. Dipende da:

- **[`../Euribor/sync-from-drive.py`](../Euribor/sync-from-drive.py)** — lo
  script che pubblica qui le date nuove prese dal Drive. La skill lo invoca, non
  riscrive i CSV a mano. Se cambia il formato dei dati, va toccato lo script, non
  la skill.
- **`CLAUDE.md` nella cartella Libor su Drive** — contiene le stesse istruzioni
  della skill, per le sessioni che lavorano direttamente in quella cartella. **Se
  si modifica la skill, va allineato anche quello**, altrimenti le due fonti si
  contraddicono.

## Perché non sono nella cartella dell'app

Le altre cartelle di questa repo (`Euribor/`, `gotthard/`, `Tarocchi/`) sono una
per app. Le skill non sono un'app e servono più app insieme — i CSV che
`aggiorna-tassi` pubblica alimentano sia Euribor X sia l'app Libor — quindi
stanno separate.
