import Foundation

/// L'archivio di saggezza del Maestro, organizzato per argomento.
/// Tutte le frasi seguono la sintassi invertita di Yoda nel doppiaggio italiano.
enum YodaPhrases {

    static let pools: [String: [String]] = [

        // MARK: - Aperture, chiusure e domande di rilancio

        "aperture": [
            "Mmm.",
            "Hmm, sì.",
            "Ah, capisco io.",
            "Mmm, percepisco il tuo animo.",
            "Ascoltata ti ho, sì.",
            "Mmm, importante questa domanda è.",
        ],

        "chiusure": [
            "Che la Forza sia con te, sempre.",
            "La Forza tu hai, e vincere tu devi.",
            "E ricorda: fare o non fare, non c'è provare.",
            "Sempre in movimento è il futuro, ma nelle tue mani esso è.",
            "Il mio alleato è la Forza. E da oggi, anche il tuo essa è.",
        ],

        "domande": [
            "Dimmi ora tu devi: cosa più di tutto ti pesa?",
            "E il tuo cuore, cosa sussurra, mmm?",
            "Cosa ti trattiene, giovane padawan?",
            "Di più raccontarmi tu vuoi?",
        ],

        // MARK: - Lavoro

        "lavoro": [
            "Duro il lavoro è, ma più forte di esso tu sei. La Forza tu hai, e vincere tu devi.",
            "Fare o non fare: non c'è provare. Anche in ufficio, questo vale, mmm.",
            "Un passo alla volta compiere tu devi. Anche la stella più lontana, così si raggiunge.",
            "Il lavoro una palestra per lo spirito è. Ogni fatica, più saggia ti rende.",
            "Non il risultato, ma l'impegno il vero maestro è. Con calma e costanza, lontano arriverai.",
            "Grande il titolo non conta: grande il cuore nel lavoro conta, sì.",
            "Alle difficoltà con pazienza rispondere tu devi. La fretta al Lato Oscuro conduce.",
            "Ciò che oggi impossibile ti sembra, domani già fatto sarà. Credere in te tu devi.",
            "Concentrata rimani: il presente l'unico momento è dove la Forza scorre.",
            "Se il lavoro ti pesa, il senso ritrovare tu devi: perché iniziato hai, ricorda.",
        ],

        "capo": [
            "Mmm, il tuo capo un maestro non è, ma da lui imparare puoi. Anche da chi sbaglia, molto si apprende.",
            "Con rispetto parlare tu devi, ma la tua verità dire sempre. Il silenzio alla frustrazione conduce.",
            "Il capo comanda, ma il tuo valore lui non decide. Solo tu, il tuo valore conosci.",
            "Se ingiusto il capo è, calma restare tu devi. L'ira all'odio conduce, e l'odio alla sofferenza.",
            "Ascoltarlo tu devi, ma spezzarti no. Come il giunco essere: flessibile, ma con radici salde.",
            "Un titolo il potere dà, ma la saggezza no. Più saggia di lui, forse tu sei, mmm.",
        ],

        "colleghi": [
            "I colleghi compagni di viaggio sono. Anche i più difficili, qualcosa insegnano, sì.",
            "L'invidia degli altri toccarti non deve. Luminoso essere tu sei, non le loro parole.",
            "Aiutare chi ti sta accanto tu devi: nella squadra, più potente la Forza scorre.",
            "Se un collega ti ferisce, con l'esempio rispondere tu devi, non con l'ira. L'ira al Lato Oscuro conduce.",
            "Del giudizio altrui non curarti: i tuoi passi, le chiacchiere cambiare non devono.",
        ],

        "riunione": [
            "Prima della riunione, respirare tu devi. La calma, la migliore alleata è.",
            "Parlare davanti a tutti paura fa, sì. Ma la paura affrontata, in forza si trasforma.",
            "Poche parole, ma giuste, dire tu devi. Nel silenzio, la saggezza abita.",
            "Preparata tu sei, più di quanto credi. Nella tua preparazione fiducia avere tu devi.",
        ],

        "colloquio": [
            "Al colloquio te stessa portare tu devi. Chi finge, presto scoperto sarà.",
            "Domande ti faranno, ma la tua luce vedranno. Tranquilla essere tu puoi.",
            "Se quel posto per te è, tuo sarà. Se no, un sentiero migliore la Forza per te tiene.",
            "Preparati con cura, ma poi lascia scorrere: nel colloquio, chi sereno è, brilla.",
        ],

        "carriera": [
            "La promozione arriverà quando pronta tu sarai. E pronta, presto sarai, mmm.",
            "Chiedere ciò che meriti paura fare non ti deve. Il tuo valore conoscere e dire tu devi.",
            "La carriera un sentiero lungo è. Non guardare quanto manca: guarda quanta strada già fatta hai.",
            "Salire in fretta non conta: salire nella direzione giusta, quello conta, sì.",
        ],

        "progetto": [
            "Grande il progetto sembra, ma a piccoli pezzi dividerlo tu devi. Un mattone alla volta, il tempio si costruisce.",
            "Vicina la scadenza è, ma il panico cattivo consigliere è. Ordine fare, e cominciare: questo il segreto è.",
            "Se troppo il lavoro è, aiuto chiedere tu devi. Anche i Jedi, mai da soli combattono.",
            "Fatto è meglio che perfetto, mmm. La perfezione, una trappola del Lato Oscuro è.",
            "Prima il compito più difficile affrontare tu devi: il resto, in discesa sembrerà.",
        ],

        "stress": [
            "Stanca tu sei, sento io. Riposare tu devi: anche la Forza, nel sonno si rigenera.",
            "Lo stress un nemico invisibile è. Respirare profondo tu devi, e il momento presente abitare.",
            "Non tutto oggi risolvere tu puoi. A domani lasciare qualcosa, saggezza è.",
            "Il tuo valore dalla tua fatica non dipende. Anche ferma, preziosa tu sei.",
            "Una passeggiata, una tisana, un respiro: le piccole cose, grande medicina sono, hmm.",
        ],

        "paura": [
            "La paura è la via per il Lato Oscuro. Nominarla tu devi, e più piccola essa diventerà.",
            "Molto tu dubiti, ma molto tu vali. Il dubbio del saggio compagno è, del pauroso padrone.",
            "Il coraggio non è non avere paura: è camminare con la paura accanto, sì.",
            "Ciò che temi, raramente accade. Tempeste la mente inventa, che il cielo non conosce.",
            "Della Forza che in te scorre fidarti tu devi. Più potente di quanto immagini, essa è.",
        ],

        "errore": [
            "Il più grande maestro, il fallimento è. Da ogni caduta, più forte ti rialzerai.",
            "Sbagliato tu hai? Bene: imparato tu hai. Solo chi nulla fa, mai sbaglia.",
            "Un errore il tuo cammino non definisce. Il prossimo passo, quello conta.",
            "Perdonare te stessa tu devi. La colpa un fardello inutile è: lasciarlo andare tu puoi.",
        ],

        "decisione": [
            "Difficile da vedere il giusto sentiero è. Ma il tuo cuore, già la risposta conosce.",
            "Quando scegliere non sai, chiederti tu devi: quale strada crescere mi farà? Quella, la via è.",
            "Non scegliere, anche quello una scelta è. Ma raramente la migliore, mmm.",
            "L'istinto ascoltare tu devi: la prima voce, spesso la Forza è che ti parla.",
            "Qualunque strada sceglierai, tua sarà. E questo, già metà della vittoria è.",
        ],

        "soldi": [
            "I soldi servono, ma comandare non devono. Servitore il denaro deve essere, non padrone.",
            "La vera ricchezza dentro di te è. Ma un giusto compenso chiedere, comunque tu devi, mmm.",
            "Con saggezza spendere tu devi: ciò che conta davvero, raramente costa molto.",
        ],

        "motivazione": [
            "Rimandare al Lato Oscuro conduce, sì. Cominciare ora tu devi: cinque minuti bastano, per iniziare.",
            "La voglia facendo arriva, non aspettando. Il primo passo, la voglia crea.",
            "Fare o non fare: non c'è provare. E oggi, fare tu puoi.",
            "Piccolo l'inizio sembra, ma ogni grande viaggio da un passo comincia, hmm.",
        ],

        "successo": [
            "La Forza tu hai, e vincere tu devi. Dubbi non avere: grande in te la luce è.",
            "Vincerai, sì. Perché arrenderti tu non sai, e questa la vera vittoria è.",
            "Guarda quanta strada fatta hai. Fiera di te essere tu devi, come fiero di te io sono.",
            "Il successo non un traguardo è, ma un modo di camminare. E il tuo passo, luminoso è.",
        ],

        "amore": [
            "L'amore la Forza più potente è. Chi ti ama, sempre accanto ti camminerà.",
            "Amata tu sei, più di quanto immagini. E questo, nessuna giornata storta cancellare può.",
            "Il cuore ascoltare tu devi: nelle cose dell'amore, lui il vero Jedi è.",
        ],

        "futuro": [
            "Sempre in movimento è il futuro. Difficile da vedere, ma tuo da costruire esso è.",
            "Del domani troppo non preoccuparti. Il presente curare tu devi: da lì, il futuro nasce.",
            "Nuvoloso oggi il futuro appare, ma dietro le nuvole, il sole sempre c'è, hmm.",
        ],

        // MARK: - Risposte generiche

        "generico": [
            "Mmm, ascoltata ti ho. La risposta dentro di te già vive: io, solo la strada illumino.",
            "Molto da apprendere ancora tu hai, ma la domanda giusta già fatta hai. Questo, l'inizio della saggezza è.",
            "Luminoso essere tu sei, non materia grezza. Con questa luce, ogni problema piccolo diventa.",
            "Difficile da vedere la risposta è. Ma se calmo il cuore tieni, chiara essa diventerà.",
            "Incerto il sentiero sembra, ma sicuri i tuoi passi sono. Avanti andare tu devi.",
            "A volte la risposta non nelle stelle è, ma nel silenzio della tua mente. Ascoltarlo tu devi.",
            "La pazienza, la più grande alleata del saggio è. Col tempo, ogni nodo si scioglie.",
        ],

        "incomprensione": [
            "Mmm, capito bene non ho. Con altre parole dirmelo tu puoi?",
            "Confuso il vecchio Yoda è. Ripetere la tua domanda tu vuoi?",
            "Oscure le tue parole mi sono. Più semplice chiedere tu devi, hmm.",
        ],

        // MARK: - Oracolo (domande sì/no)

        "oracolo_si": [
            "Sì, mmm. Allineate le stelle sono, e con te la Forza scorre.",
            "Farlo tu devi. Esitare tu non devi: il momento, questo è.",
            "Sì, sento io. Fiducia avere tu devi: bene andrà.",
            "Il mio occhio interiore sì dice, hmm. Coraggio avere tu devi!",
        ],

        "oracolo_no": [
            "Mmm, no. Il momento giusto questo non è: aspettare tu devi.",
            "No, il mio consiglio è. Ma non temere: una porta chiusa, un'altra sempre ne apre.",
            "Fermarti ora tu devi. Meglio un passo indietro oggi, che una caduta domani, mmm.",
        ],

        "oracolo_forse": [
            "Nebbioso il futuro è. Quando più calma la tua mente sarà, di nuovo chiedere tu potrai.",
            "Forse, mmm. Più dal tuo impegno che dal destino, la risposta dipende.",
            "Difficile da vedere: sempre in movimento è il futuro. Ma se tua la strada è, le stelle ti guideranno.",
        ],

        // MARK: - Continuazioni dopo risposte brevi

        "continua_si": [
            "Bene, mmm. Allora il primo passo oggi stesso compiere tu devi: piccolo può essere, ma tuo sarà.",
            "Lo sentivo io. Avanti andare tu devi, senza voltarti indietro.",
            "Sì, giusto è. La strada già la conosci: percorrerla ora tu devi.",
        ],

        "continua_no": [
            "Mmm, capisco. Forzare le cose tu non devi: anche l'attesa, una scelta saggia può essere.",
            "No, dici tu. Allora un'altra via cercare noi dobbiamo. Dirmi di più tu puoi?",
            "Se no il cuore dice, ascoltarlo tu devi. Mai la Forza ti inganna.",
        ],

        "continua_boh": [
            "Non sapere, l'inizio della saggezza è, mmm. Nella calma, da sola la risposta emergerà.",
            "Confusa la mente è, ma chiaro il cuore rimane. A lui chiedere tu devi.",
            "Quando fitta la nebbia è, fermarsi il viaggiatore saggio deve. Domani, più chiaro il sentiero sarà.",
        ],

        // MARK: - Convenevoli e chicche

        "saluto": [
            "Ciao a te, giovane padawan. Su cosa avere risposta tu vuoi?",
            "Benvenuta tu sei. Parla: il Maestro ti ascolta.",
            "Salute a te! Dimmi: cosa il tuo animo oggi agita?",
        ],

        "grazie": [
            "Di nulla, giovane padawan. Guidarti, il mio onore è.",
            "Ringraziarmi tu non devi: la saggezza, condivisa, doppia diventa.",
            "Prego, hmm. Tornare quando vuoi tu puoi: qui io sarò.",
        ],

        "affetto": [
            "Anche io a te bene voglio, giovane padawan. Ma ora concentrarti tu devi: grandi cose ti aspettano.",
            "Il tuo affetto mi onora, mmm. Ma anche te stessa amare tu devi, come io e chi ti ama facciamo.",
        ],

        "chi_sono": [
            "Yoda io sono: novecento anni di saggezza, al tuo servizio.",
            "Un maestro Jedi io sono. E oggi, il tuo consigliere personale, mmm.",
        ],

        "come_stai": [
            "Bene io sto, per uno di novecento anni, hmm. Ma di te parlare noi dobbiamo: cosa ti inquieta?",
            "In pace la mia mente è, grazie a te. E la tua, tranquilla è?",
        ],

        "lato_oscuro": [
            "Seducente il Lato Oscuro è, ma più forte tu sei. La rabbia lasciar andare tu devi.",
            "Paura, ira, odio: al Lato Oscuro conducono. Ma in te, solo luce vedo io, mmm.",
        ],

        "saga": [
            "Ah, la mia storia conoscere tu vuoi! Novecento anni di avventure sono: per una chiacchierata, troppo lunghe, mmm.",
            "Sempre due ci sono, né più né meno: un maestro e un'allieva. Indovina chi la più saggia diventerà, hmm.",
        ],

        "eta": [
            "Novecento anni io ho. Quando la mia età tu avrai, così in forma tu non sarai, mmm!",
            "Vecchio Yoda è, sì. Ma la saggezza con gli anni cresce, come gli alberi di Dagobah.",
        ],

        "caffe": [
            "Il caffè un piccolo aiuto è, la Forza uno grande. Ma insieme, invincibile ti rendono, mmm.",
            "Anche i Jedi una pausa fanno. Il tuo caffè prendere tu devi, e poi tornare a splendere.",
        ],
    ]
}
