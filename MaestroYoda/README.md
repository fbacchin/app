# Maestro Yoda 🛸

Un'app iOS regalo: il saggio Yoda risponde alle tue domande parlando come nel
doppiaggio italiano di Guerre Stellari — *«La Forza tu hai, e vincere tu devi.»*

All'apertura il Maestro pone la domanda rituale — **«Su cosa avere risposta tu
vuoi?»** — e da lì parte una conversazione in chat su sfondo interstellare
(stelle che brillano, nebulose, stelle cadenti). Yoda è specializzato
soprattutto in consigli di **lavoro**: capo, colleghi, riunioni, colloqui,
promozioni, scadenze, stress… ma sa dire la sua anche su paure, decisioni,
amore e futuro.

## Come funziona

- **Apple Intelligence (se disponibile)**: su iPhone con iOS 26+ e Apple
  Intelligence attiva, le risposte di Yoda sono generate dal modello
  linguistico on-device di Apple (framework Foundation Models), istruito a
  parlare come Yoda del doppiaggio italiano. La conversazione ha memoria del
  contesto, tutto resta sul telefono e non serve internet. Nell'intestazione
  della chat appare "in ascolto, con Apple Intelligence".
- **Motore offline**: se Apple Intelligence non è disponibile (iPhone o iOS
  più vecchi, funzione disattivata) — o se il modello dovesse fallire — l'app
  passa automaticamente a `YodaBrain`, che analizza la domanda (parole chiave,
  domande sì/no, risposte brevi, saluti) e compone la risposta pescando da
  oltre 120 frasi originali in stile Yoda, senza mai ripetersi finché un
  argomento non si esaurisce.
- **Domande sì/no** («Devo…?», «Ce la farò…?»): risponde da oracolo, con
  leggera preferenza per l'incoraggiamento.
- **Chicche nascoste**: prova a scrivere «lato oscuro», «quanti anni hai»,
  «caffè», «ti amo», «grazie»…

## Installazione su iPhone

1. Apri `MaestroYoda.xcodeproj` con **Xcode 16 o successivo** sul Mac
   (per includere Apple Intelligence serve **Xcode 26+**; con Xcode più
   vecchi l'app si compila comunque e usa solo il motore offline).
2. Seleziona il target *MaestroYoda* → scheda **Signing & Capabilities** →
   scegli il tuo **Team** (basta un Apple ID gratuito).
3. Se Xcode lo chiede, cambia il *Bundle Identifier* in uno tuo
   (es. `com.tuonome.MaestroYoda`).
4. Collega l'iPhone, selezionalo come destinazione e premi **Run** (⌘R).
5. Sull'iPhone: *Impostazioni → Generali → VPN e gestione dispositivi* →
   autorizza il tuo profilo sviluppatore.

Nota: con un Apple ID gratuito l'app scade dopo 7 giorni (basta rifare Run);
con un account sviluppatore a pagamento dura un anno.

## Personalizzazione

- In `MaestroYoda/Engine/YodaConfig.swift` imposta `nomePadawan` con il nome
  della tua padawan: Yoda la saluterà per nome.
- Le frasi vivono in `MaestroYoda/Engine/YodaPhrases.swift`: aggiungine quante
  vuoi, il motore le userà subito.
- Il Maestro parla al femminile ("Benvenuta", "stanca", "preparata"): per un
  padawan maschile basta ritoccare le frasi negli stessi file.

## Nota

Progetto amatoriale a scopo personale, per uso privato: Yoda e Guerre Stellari
sono proprietà di Lucasfilm/Disney, quindi l'app non va distribuita su App
Store. L'icona e l'avatar in-app usano un'illustrazione cartoon di Yoda
fornita dall'autore dell'app (`AppIcon` e `YodaPortrait` in Assets.xcassets).
