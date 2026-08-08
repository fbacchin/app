# Documento di esempio

Questo file mostra tutto ciò che **MdViewer** sa visualizzare e stampare.
Aprilo con l'app e prova ⌘P per la stampa o ⇧⌘E per il PDF.

## Sommario

- [Formattazione](#formattazione)
- [Elenchi](#elenchi)
- [Codice](#codice)
- [Tabelle](#tabelle)
- [Citazioni e altro](#citazioni-e-altro)

## Formattazione

Testo in **grassetto**, in *corsivo*, in ***grassetto corsivo***, ~~barrato~~ e `codice inline`.
I link esterni si aprono nel browser: [sito di Markdown](https://daringfireball.net/projects/markdown/).

## Elenchi

1. Primo passo
2. Secondo passo
   1. Sotto-passo annidato
   2. Un altro sotto-passo
3. Terzo passo

- Punto elenco
- Un altro punto
  - Annidato

Elenco attività:

- [x] Creare il clone di MdPreview
- [x] Stampare un file Markdown
- [ ] Impostarlo come app predefinita per i `.md`

## Codice

```swift
struct Saluto {
    let nome: String
    var messaggio: String { "Ciao, \(nome)!" }
}

print(Saluto(nome: "iMac").messaggio)
```

## Tabelle

| Funzione            | Scorciatoia | Note                          |
|---------------------|:-----------:|-------------------------------|
| Stampa              |     ⌘P      | Pannello di stampa completo   |
| Esporta PDF         |    ⇧⌘E      | PDF impaginato                |
| Sorgente / Anteprima|    ⌥⌘U      | Vista del Markdown grezzo     |
| Zoom                | ⌘+ ⌘− ⌘0    | Ricordato tra le sessioni     |
| Ricarica            |     ⌘R      | Rilegge il file dal disco     |

## Citazioni e altro

> La semplicità è la sofisticazione suprema.
> — attribuita a Leonardo da Vinci

Una riga orizzontale:

---

E un'immagine remota (serve la connessione):

![Logo Markdown](https://upload.wikimedia.org/wikipedia/commons/thumb/4/48/Markdown-mark.svg/320px-Markdown-mark.svg.png)

*Fine dell'esempio — buona lettura!*
