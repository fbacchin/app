# Volcano — installazione over-the-air

Distribuzione Ad Hoc senza TestFlight: l'`.ipa` e il manifest stanno su GitHub
Pages, e l'iPhone li installa con il protocollo `itms-services://`.

**Pagina di installazione:** <https://fbacchin.github.io/app/volcano/ota/>

Questa cartella contiene solo ciò che deve essere **pubblicato**. Il codice
sorgente dell'app vive altrove: se ti serve, cercalo nella copia di lavoro
locale del progetto.

---

## Prima di iniziare: due prerequisiti che bloccano tutto

### Serve un Apple Developer Program a pagamento

L'export Ad Hoc **non è possibile con un Apple ID gratuito**. Un account free
può solo installare via cavo da Xcode, con un profilo che scade dopo 7 giorni e
senza alcuna possibilità di installazione over-the-air.

### Il dispositivo va registrato prima dell'export

Ad Hoc e Development includono nel profilo l'elenco degli **UDID autorizzati**.
Un iPhone non registrato riceve il pop-up di installazione, accetta, e poi
fallisce senza dire perché — è il modo più frustrante in cui questa procedura
può rompersi.

1. Collega l'iPhone al Mac, apri Xcode → **Window → Devices and Simulators**
2. Copia l'**Identifier** (l'UDID)
3. Registralo su [developer.apple.com](https://developer.apple.com/account/resources/devices/list)
4. **Rigenera il provisioning profile** dopo aver aggiunto il dispositivo:
   un profilo generato prima non contiene il nuovo UDID

Il limite è di 100 dispositivi per tipo per anno di membership, e si azzera
solo al rinnovo.

---

## 1. Export da Xcode

1. **Product → Archive**
2. Nell'Organizer, **Distribute App**
3. Metodo: **Release Testing** (Ad Hoc) oppure **Debugging** (Development)
4. Esporta **senza** spuntare il manifest: lo genera lo script, meglio.

Poi, dalla cartella dove hai l'`.ipa`:

```bash
./make-manifest.sh Volcano.ipa
```

Lo script legge bundle identifier, versione e nome **dall'`.ipa` stesso** e
costruisce i tre URL da un'unica base, poi verifica il plist con
`plutil -lint`.

Se preferisci farlo da Xcode, spunta *Include manifest for over-the-air
installation* e usa questi valori:

| Campo | Valore |
|---|---|
| App URL | `https://fbacchin.github.io/app/volcano/ota/Volcano.ipa` |
| Display Image URL | `https://fbacchin.github.io/app/volcano/ota/icon-57.png` |
| Full Size Image URL | `https://fbacchin.github.io/app/volcano/ota/icon-512.png` |

Quei tre URL digitati a mano sono il punto in cui questa procedura fallisce più
spesso, e un refuso non produce nessun errore leggibile: iOS mostra soltanto
"Impossibile installare". È il motivo per cui lo script esiste.

---

## 2. Pubblicazione

Copia `Volcano.ipa` e `manifest.plist` in questa cartella, poi:

```bash
git add volcano/ota/
git commit -m "Volcano: build OTA <versione>"
git push
```

### Verifica prima di prendere in mano il telefono

```bash
curl -I https://fbacchin.github.io/app/volcano/ota/manifest.plist
curl -I https://fbacchin.github.io/app/volcano/ota/Volcano.ipa
```

Entrambe devono rispondere `200`. La pubblicazione di Pages richiede da pochi
secondi a un paio di minuti dopo il push.

Se rispondono `404`, controlla in **Settings → Pages** quale branch è
configurato: i file devono stare su quello.

---

## 3. Installazione sull'iPhone

Apri **con Safari**:

```
https://fbacchin.github.io/app/volcano/ota/
```

e tocca **Installa Volcano**.

### Perché una pagina e non il link diretto

Digitare `itms-services://?action=download-manifest&url=...` nella barra
indirizzi di Safari **non funziona in modo affidabile** su iOS recenti: Safari
spesso non riconosce lo schema quando viene scritto a mano, e non dà nessun
riscontro.

Il protocollo va invece attivato da un `<a href="itms-services://…">` toccato
dentro una pagina. È esattamente ciò che fa `index.html`, ed è il motivo per
cui quel file esiste invece di essere un dettaglio estetico.

### Alla prima apertura

L'app installata non parte subito: iOS chiede di autorizzare lo sviluppatore in
**Impostazioni → Generali → VPN e gestione dispositivo**. È normale per una
build che non viene dall'App Store.

---

## File grandi

`.ipa` è in `.gitignore` di proposito. Git rifiuta i file oltre i **100 MB**, e
ogni build committata resta **per sempre nella storia del repository** anche
dopo essere stata cancellata: dopo una decina di build il clone diventa pesante
per tutti.

**Alternativa consigliata: l'`.ipa` come asset di una GitHub Release**, e solo
il manifest qui. Gli asset di release arrivano a 2 GB, non entrano nella storia
di git, e hanno URL HTTPS stabili:

```
https://github.com/fbacchin/app/releases/download/volcano-v1.0/Volcano.ipa
```

Basta passare quell'URL allo script come base per l'`.ipa`, oppure modificare a
mano il campo `software-package` nel manifest. Funziona solo con repository
pubblico: gli asset di release di un repository privato richiedono
autenticazione, e l'iPhone non ce l'ha.

Se decidi di committare l'`.ipa` qui, togli la riga da `.gitignore`.

---

## Scadenze

- Un profilo **Ad Hoc** vale un anno. Alla scadenza l'app smette di aprirsi:
  serve una nuova build, non basta reinstallare la stessa.
- Il **certificato di distribuzione** scade indipendentemente dal profilo.
- Se l'app un giorno smette di partire senza motivo apparente, la prima cosa da
  controllare è la data di scadenza del profilo.
