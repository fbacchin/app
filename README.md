# bacchin.app: come si aggiorna il sito

Guida per le sessioni che lavorano sul sito, in particolare quando si aggiornano
le pagine di **assistenza** e di **privacy** delle app.

Stato verificato sui repository il 3 ottobre 2026.

## La regola in una riga

Le pagine si modificano **solo** nel repo `fbacchin/fbacchin.github.io`.
Il repo `fbacchin/app` contiene i dati che le app scaricano e dei semplici
rimandi: lì le pagine di assistenza e privacy **non si toccano**.

## Dove sta cosa

| Cosa | Repository | Si vede su | Si modifica? |
|---|---|---|---|
| Il sito: home, pagine delle app, assistenza, privacy | `fbacchin/fbacchin.github.io` | `https://bacchin.app` | **Sì, qui** |
| I dati letti dalle app (CSV dei tassi, Gottardo, codici di gara, valichi, volcano) | `fbacchin/app` | `https://fbacchin.github.io/app/...` | Solo dagli automatismi |
| I vecchi indirizzi di assistenza e privacy | `fbacchin/app` | `https://fbacchin.github.io/app/<Cartella>/...` | No: sono rimandi |
| I giochi | `fbacchin/Giochi` | `https://giochi.bacchin.app` | Sì, nel loro repo |
| ONON Tracker e Dashboard BCE | `fbacchin/finance` | `https://fbacchin.github.io/finance/...` | Sì, nel loro repo |
| Vecchie pagine delle app geografiche | `fbacchin/privacy-and-support` | GitHub Pages | Non toccare (vedi sotto) |

### Come viene pubblicato il sito

`bacchin.app` è servito da **Cloudflare Pages**, che pubblica da solo il ramo
`main` di `fbacchin/fbacchin.github.io`. Ogni commit su `main` va online in
meno di un minuto: non c'è una fase di prova.

Cloudflare toglie `.html` dagli indirizzi con un reindirizzamento:
`/Leasing.html` diventa `/Leasing`, `/app/Leasing/support.html` diventa
`/app/Leasing/support`. Nei link interni e su App Store Connect usare la forma
**senza** `.html`.

## I file del sito (`fbacchin/fbacchin.github.io`)

```
index.html              home
stile.css               foglio di stile comune (richiamato come stile.css?v=...)
fonts/                  caratteri ospitati sul sito (niente Google Fonts)
privacy.html            privacy del sito + indice di assistenza e privacy delle app
EuriborX.html           pagine di presentazione, una per app
LiborX.html
Mortgage.html
Leasing.html
gotthard.html
Burraco.html
codici.html
perspecta.html
Regione.html
USState.html
EuriborMac.html         solo un rimando a /EuriborX (app dismessa)
euribor-oggi.html       GENERATA: non modificare a mano (vedi sotto)
strumenti/euribor_oggi.py   lo script che genera euribor-oggi.html
.github/workflows/euribor-oggi.yml   lo fa girare 4 volte al giorno
tennis/                 simulatore ranking ATP
stampa/                 materiali stampa di Gottardo Live
sitemap.xml  robots.txt  404.html  og.png
app-ads.txt             serve a Google AdMob: NON cancellare
Help.html               vecchia pagina, NON cancellare per ora (vedi sotto)
app/                    assistenza e privacy di ogni app  <-- il lavoro si fa qui
```

### La cartella `app/`: assistenza e privacy

Una cartella per app. Attenzione: i nomi dei file non sono uniformi.

| App | Cartella | Assistenza | Privacy |
|---|---|---|---|
| Euribor X | `app/EuriborX/` | `support.html` | `privacy.html` |
| Libor X | `app/LiborX/` | `support.html` | `privacy.html` |
| Mortgage Calculators | `app/Mortgage/` | `support.html` | `privacy.html` |
| Leasing Calculators | `app/Leasing/` | `support.html` | `privacy.html` |
| Gottardo Live | `app/gotthard/` | `support-gotthard.html` | `privacy-gotthard.html` |
| Burraco Score | `app/Burraco/` | `support-burraco.html` | `privacy-burraco.html` |
| Codice di Gara Burraco | `app/codici/` | `support-codicedigara.html` | `privacy-codicedigara.html` |
| Perspecta | `app/perspecta/` | `support-perspecta.html` | `privacy-perspecta.html` |
| Indovina la Regione | `app/Regione/` | `support-regione.html` | `privacy-regione.html` |
| Guess the Swiss Canton | `app/SwissCanton/` | `support-swisscanton.html` | `privacy-swisscanton.html` |
| Guess the US State | `app/USState/` | `support-usstate.html` | `privacy-usstate.html` |
| Euribor per Mac (dismessa) | `app/EuriborMac/` | `support.html` | `privacy.html` |
| Health Companion (non pubblicata) | `app/healthcompanion/` | `support-healthcompanion.html` | `privacy-healthcompanion.html` |
| Valichi (non pubblicata) | `app/valichi/` | `support-valichi.html` | `privacy-valichi.html` |
| Volcano (non pubblicata) | `app/volcano/` | `support-volcano.html` | `privacy-volcano.html` |

L'indirizzo pubblico di ogni pagina è
`https://bacchin.app/app/<Cartella>/<file senza .html>`, per esempio
`https://bacchin.app/app/Leasing/support`.

## Cosa c'è invece in `fbacchin/app`

Si vede su `https://fbacchin.github.io/app/`. Contiene due cose diverse.

**1. I dati che le app scaricano.** Gli indirizzi sono scritti dentro le app
già distribuite: non vanno mai spostati né rinominati.

- `Euribor/*.csv`: i tassi. Li aggiorna la skill `aggiorna-tassi`.
- `gotthard/data/`: lo stato del tunnel. Lo aggiorna una GitHub Action.
- `codici/manifest.json` e le cartelle `fibur/`, `fitab/`: i regolamenti.
- `valichi/` e i dati di volcano: aggiornati da GitHub Action.

**2. I rimandi.** I file `support*.html` e `privacy*.html` in questo repo sono
pagine vuote che portano subito alla pagina vera su `bacchin.app`. Esistono
perché le versioni vecchie delle app e l'App Store puntano ancora lì.
**Non vanno modificati**: se una sessione ci scrive del contenuto, quel testo
non lo vedrà nessuno.

## Procedura: aggiornare assistenza o privacy di un'app

1. **Parti dall'ultima versione.** Clona di nuovo
   `fbacchin/fbacchin.github.io`, oppure fai `git pull`. Più sessioni lavorano
   sullo stesso repo e `euribor-oggi.html` cambia da sola più volte al giorno:
   una copia vecchia sovrascrive il lavoro degli altri.
2. **Modifica solo i file dell'app** in `app/<Cartella>/`. Modifiche mirate:
   non riscrivere la pagina se cambia un paragrafo.
3. **Aggiorna la data** in cima alla pagina («Aggiornato al …»).
4. **Tutte le lingue.** Le pagine sono multilingua nello stesso file: la
   modifica va fatta in ogni lingua presente.
5. **Controlla le pagine collegate**, e aggiornale solo se cambia qualcosa che
   dicono:
   - la pagina di presentazione dell'app nella radice (per esempio
     `Leasing.html`): sezione sul prezzo e sulla pubblicità, riga
     «Piattaforma», riga «Prezzo»;
   - la riga dell'app in `index.html`;
   - l'indice delle app in `privacy.html`, se cambia il nome dell'app o se
     l'app viene pubblicata o ritirata;
   - `sitemap.xml`: la data `lastmod` della pagina di presentazione toccata.
6. **Prima di pubblicare** fai `git fetch` e controlla che `main` non sia
   cambiato nel frattempo. Se è cambiato, riporta le tue modifiche sulla
   versione nuova.
7. **Pubblica** con un commit su `main`, con un messaggio che dica app e
   versione (esempio: `Leasing 3.1: supporto con Leasing Legacy`). Se la
   sessione non può scrivere sul repo, prepara uno zip con i soli file
   cambiati, con le cartelle al loro posto, da caricare a mano con
   «Add file → Upload files».
8. **Verifica online** dopo un minuto: apri l'indirizzo su `bacchin.app` e
   controlla che il testo nuovo ci sia.

## Aggiungere un'app nuova

1. Crea `app/<Cartella>/` con assistenza, privacy e icona.
2. Crea la pagina di presentazione nella radice, copiando la struttura di una
   esistente (per esempio `Leasing.html`).
3. Aggiungi la riga in `index.html`.
4. Aggiungi la riga nell'indice di `privacy.html`, **solo se l'app è
   pubblicata** sull'App Store.
5. Aggiungi la pagina di presentazione a `sitemap.xml`.
6. Sistema i link «precedente / successiva» in fondo alle pagine delle app
   vicine.
7. Su App Store Connect usa gli indirizzi `https://bacchin.app/app/...`.
   Per un'app nuova non serve creare rimandi in `fbacchin/app`.

## Ritirare un'app

Togli la riga da `index.html`, da `privacy.html` e da `sitemap.xml`, e sistema
i link delle app vicine. La pagina di presentazione diventa un rimando (come
`EuriborMac.html`). Assistenza e privacy in `app/<Cartella>/` **restano**:
servono a chi ha ancora l'app installata.

## Convenzioni da rispettare

- **Caratteri:** si usa `/fonts/fonts.css`. Nessun link a Google Fonts.
- **Piede delle pagine del sito:** indirizzo email e link «Privacy e
  assistenza» verso `/privacy`.
- **Email:** le pagine del sito usano `info@bacchin.app`. Le pagine di
  assistenza e privacy delle app usano `bacchin@tiscali.it`: è voluto, non
  uniformare.
- **Link ad assistenza e privacy** dalle pagine del sito: forma breve, per
  esempio `/app/Leasing/support`.
- **Link all'App Store:** ogni pagina di presentazione ha il pulsante
  «Scarica su App Store» sotto il titolo e la riga «App Store» nella scheda
  in fondo, con indirizzo `https://apps.apple.com/app/id<numero>`. Perspecta
  non ce l'ha finché non è sull'App Store.
- **Dati in diretta:** le pagine del sito leggono i dati con l'indirizzo
  completo `https://fbacchin.github.io/app/...`. Non renderli relativi.
- **Modello di vendita attuale** di Euribor X, Libor X, Mortgage e Leasing:
  una sola app gratuita con pubblicità, che si toglie con abbonamento annuale
  o acquisto una tantum. La vecchia versione a pagamento si chiama «Legacy» e
  non riceve aggiornamenti. Non esistono più versioni «Light» di queste app.
- **Euribor per Mac** è dismessa.

## Cose da non fare

- Non modificare assistenza e privacy in `fbacchin/app`.
- Non spostare né rinominare i file di dati in `fbacchin/app`.
- Non modificare `euribor-oggi.html` a mano: la modifica dura poche ore. Si
  cambia `strumenti/euribor_oggi.py`, e poi anche la pagina.
- Non cancellare `app-ads.txt`.
- Non cancellare `Help.html` né il repo `privacy-and-support`: alcune app
  geografiche puntano ancora lì. Si tolgono solo quando tutte sono aggiornate.
- Non aggiungere a `privacy.html` le app non pubblicate (Health Companion,
  Valichi, Volcano).
- Non ricostruire un file partendo da una copia vecchia.

## Ancora da fare

- Inserire nelle pagine delle app delle immagini con le funzionalità
  descritte nel testo.
- Cancellare `Help.html` quando tutte le app geografiche sono aggiornate.
- Cancellare il repo `privacy-and-support` quando la privacy di tutte le app
  è stata scritta qui.

## Controllo finale

- [ ] Ho lavorato sull'ultima versione di `main`.
- [ ] Ho modificato solo `fbacchin/fbacchin.github.io`.
- [ ] La data «Aggiornato al» è quella di oggi.
- [ ] Tutte le lingue della pagina sono allineate.
- [ ] Pagina di presentazione, home, indice privacy e sitemap dicono la stessa
      cosa.
- [ ] La pagina si apre su `https://bacchin.app/app/<Cartella>/<file>`.
