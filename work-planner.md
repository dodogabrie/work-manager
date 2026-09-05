# Work Planner — Specifica di progetto

## 1. Visione

Work Planner è un'applicazione personale per pianificare, simulare, versionare e comunicare il carico di lavoro.

L'obiettivo non è misurare il tempo effettivamente impiegato davanti al computer, ma rappresentare in modo coerente:

- il lavoro richiesto;
- l'effort pianificato;
- la capacità lavorativa disponibile;
- l'ordine manuale della coda di lavoro;
- le date previste di consegna;
- l'impatto di nuove richieste, riunioni, ferie e permessi;
- la differenza tra un'attività tecnicamente pronta e la sua consegna;
- la storia completa delle decisioni di pianificazione.

Il sistema deve essere utile sia come strumento personale sia come mezzo per comunicare al manager su cosa è allocata la capacità e quali conseguenze produce una nuova richiesta.

**Principio fondamentale:**

> La timeline rappresenta l'allocazione prevista e concordata, non un cronometro del tempo effettivamente impiegato.

## 2. Obiettivi

Il sistema deve permettere di:

1. raccogliere rapidamente nuove richieste in una Inbox;
2. assegnare a ogni task un effort pianificato;
3. ottenere proposte di effort da Claude/LLM;
4. pianificare automaticamente i task sulla capacità disponibile;
5. simulare qualsiasi modifica prima di applicarla;
6. mostrare chiaramente l'impatto di una nuova richiesta sul piano esistente;
7. approvare o rifiutare le modifiche sia dalla UI sia tramite Claude/API;
8. mantenere una timeline personale dettagliata;
9. pubblicare una vista manager in sola lettura tramite link revocabile;
10. produrre report grafici PDF/PNG allegabili a email;
11. sincronizzare il calendario con Outlook, con particolare attenzione alle riunioni aziendali;
12. supportare Google Calendar e iCalendar;
13. conservare la storia delle modifiche;
14. rendere annullabili, dove semanticamente possibile, tutte le azioni;
15. permettere a Claude di operare sull'applicazione tramite API REST senza duplicare la business logic.

## 3. Principi funzionali

### 3.1 Effort pianificato e tempo effettivo sono concetti diversi

Ogni task possiede un **planning effort**: quanto lavoro viene allocato nella pianificazione. Non deve essere automaticamente ridotto perché strumenti AI consentono di completare tecnicamente il task più rapidamente.

Il tempo effettivo impiegato:

- non determina automaticamente la timeline;
- non libera automaticamente capacità;
- può non essere necessario nella vista manager;
- non deve essere confuso con l'effort usato dallo scheduler.

L'applicazione non è pensata come time tracker.

### 3.2 Completamento interno e consegna esterna

Un task può essere tecnicamente completato prima della data pianificata. Occorre distinguere almeno: in lavorazione; pronto internamente / READY; consegnato.

Quando un task diventa READY:

- il proprietario sa che il lavoro tecnico è pronto;
- **la capacità pianificata non viene liberata automaticamente**;
- **la data di delivery pianificata rimane invariata**;
- la comunicazione/consegna avviene quando viene esplicitamente decisa.

### 3.3 Nessuna modifica automatica al piano confermato

Il piano corrente è uno stato confermato. Qualunque evento che potrebbe modificarlo genera prima una Planning Proposal.

```
evento/intenzione -> proposta -> simulazione -> anteprima impatto -> approvazione/rifiuto -> applicazione -> snapshot
```

Vale per: nuovi task; modifica effort; modifica dell'ordine della coda; drag & drop; modifica date; riordino esplicito; ferie; permessi; riunioni; cancellazione/spostamento di riunioni; undo che modifica la pianificazione; altre variazioni di capacità.

## 4. Stack tecnologico

Docker + Docker Compose. Backend Python/FastAPI. Frontend Vue 3 + Vite. PostgreSQL.

La business logic non deve vivere nei controller/API endpoint. UI, integrazioni e Claude devono richiamare gli stessi servizi applicativi.

## 5. Accessi e superfici applicative

### 5.1 Owner application (`/app`)
Area privata completa, autenticata. Vede informazioni interne, modifica task, approva proposal, gestisce timeline, vede READY, gestisce integrazioni, history, undo/redo, link manager, report.

### 5.2 Manager View (`/share/<token>`)
Link revocabile, senza account. Token ad alta entropia, revocabile, eventualmente con scadenza, **read-only**.

Mostra: progetto; task; effort pianificato; periodo di allocazione; data prevista di delivery; timeline; eventuali impatti.

**Non** mostra: tempo effettivo; stato READY interno; note private; informazioni tecniche; token o integrazioni.

### 5.3 Accesso API per Claude
REST API con token personale revocabile, identificabile, con scope, memorizzato in forma sicura. Documentate via OpenAPI. Nessun MCP nell'MVP.

## 6. Task e Inbox

### 6.1 Inbox
Un task creato via Quick Add entra in `INBOX` e resta non pianificato finché non viene esplicitamente sottoposto allo scheduler.

### 6.2 Quick Add
Sempre facilmente accessibile. **Unico campo obbligatorio: il titolo.** Gli altri sono opzionali.

### 6.3 Campi concettuali del task
id; titolo; descrizione; progetto; stato; planning effort; effort proposto; confidence della stima; target delivery date; fixed delivery date; data creazione; data modifica; data READY; data consegna; note interne; posizione/ordinamento; soft-delete timestamp.

### 6.4 Task multi-giorno
Un task può essere distribuito su più giorni. Task e allocazione temporale sono **entità separate**: servono planning segments.

## 7. Stati dei task

`INBOX`, `PLANNED`, `IN_PROGRESS`, `READY`, `DELIVERED`, `BLOCKED`, `ARCHIVED/CANCELLED`.

READY è uno stato interno. Il passaggio a READY non modifica automaticamente la pianificazione.

## 8. Ordine manuale della coda

Non esiste priorità calcolata automaticamente. **La posizione del task nella coda è la sua priorità effettiva.** L'utente decide l'ordine tramite drag & drop.

Un task normale pianificato entra in fondo alla coda e viene collocato nel primo spazio disponibile in avanti. Per rendere urgente un task lo si trascina nella posizione desiderata.

Nessun campo `priority`, nessun algoritmo di preemption. Ogni riordino passa da Planning Proposal, preview e approvazione.

## 9. Dipendenze — escluse dall'MVP

Le dipendenze tra task non fanno parte dello scheduler, dell'interfaccia né del modello dati dell'MVP. L'ordine operativo è esclusivamente quello della coda.

## 10. Date target e fixed

- **Target date**: preferenza/obiettivo. Il mancato rispetto genera un **warning**, approvabile.
- **Fixed date**: vincolo **hard**. Una proposta che la viola genera un **conflitto che impedisce la conferma**.

## 11. Scheduler

### 11.1 Unità di capacità
Internamente **minuti**. UI mostra ore/minuti. Capacità standard iniziale 8 ore/giorno, configurazione settimanale modificabile.

### 11.2 Capacità base
Calendario di capacità standard settimanale, es. Lun-Ven 480 min, Sab-Dom 0.

### 11.3 Eccezioni alla capacità
Ferie, permessi e giornate ridotte **non sono task**: sono capacity exceptions (es. `FERIE -> 0 min`, `PERMESSO -> 240 min`).

Inserire un'eccezione su un piano esistente: ricalcolo impatto -> Planning Proposal -> before/after -> approvazione -> nuovo snapshot.

### 11.4 Riunioni
Le riunioni riducono la capacità disponibile; non sono task.

```
capacità base:         480 min
riunioni:              120 min
capacità schedulabile: 360 min
```

**Gli intervalli sovrapposti devono essere uniti prima del calcolo**, evitando doppie sottrazioni.

### 11.5 READY non libera capacità
Un task pianificato per 8h completato tecnicamente in anticipo e passato a READY resta allocato secondo il piano. Lo scheduler non recupera automaticamente le ore.

### 11.6 Ordinamento
Lo scheduler **non decide l'ordine**. Usa la coda definita dall'utente come fonte di verità e riempie la capacità disponibile procedendo in avanti nel tempo. Considera capacità reale, date fixed e segmenti bloccati. I target generano warning ma non riordinano. Comportamento deterministico e prevedibile.

## 12. Planning Proposal

Rappresenta una modifica non ancora applicata. Può nascere da UI, Claude/API, calendario, drag & drop, modifica effort, nuova richiesta, nuova assenza, riordino, undo.

Contiene almeno: id; tipo; origine; autore/originator; **base plan version**; cambiamento richiesto; simulazione risultante; warnings; conflicts; stato; timestamp.

Stati: `pending`, `approved`, `rejected`, `stale`, `applied`.

### 12.1 Base plan version
Ogni proposal sa da quale versione del piano è stata calcolata. Se il piano cambia nel frattempo la proposal diventa `STALE` e deve essere ricalcolata prima dell'approvazione.

## 13. Preview e Impact Simulation

Prima di applicare: piano attuale; piano proposto; task spostati; vecchie date; nuove date; target violati; conflitti hard; variazione della capacità. La stessa semantica deve essere disponibile via API.

## 14. Drag & Drop

Non modifica direttamente il piano: UI invia l'intenzione -> scheduler simula -> risultato mostrato -> utente approva o rifiuta. Se approvato, il risultato diventa il nuovo piano corrente.

- **14.1 Hard conflict**: fixed date impossibile, capacità insufficiente rispetto a vincolo hard. Non confermabile.
- **14.2 Soft conflict**: target date superata. Warning, confermabile.
- **14.3 Resize**: ridimensionare graficamente un task **non** deve alterare silenziosamente l'effort. È una modifica dell'effort e segue il flusso di proposal.

## 15. Effort estimation

- **15.1 Effort proposto**: Claude/LLM propone range, valore suggerito, confidence, breve motivazione.
- **15.2 Effort confermato**: l'utente conferma o modifica.
- **15.3 Planning effort**: valore usato dallo scheduler.

Claude deve stimare l'effort **convenzionale** del lavoro, non il tempo compresso dall'uso di strumenti AI.

Modificare l'effort di un task pianificato: proposal -> preview -> approvazione -> nuovo snapshot. Uguale da UI e da API.

## 16. Claude / API REST

Claude può: creare/modificare task; proporre e cambiare effort; cambiare posizione in coda; richiedere simulazione; mostrare impatto; approvare/rifiutare proposal su esplicita richiesta dell'utente; interrogare piano e capacità; leggere proposal pendenti; richiedere undo/redo.

> Claude e Vue sono client differenti della stessa application layer. Non deve esistere business logic parallela.

### 16.1 Context endpoint
Endpoint compatto che restituisce: data corrente; progetti attivi; task Inbox; piano corrente; capacità prossimi giorni; proposal pendenti; principali vincoli.

## 17. Calendario — riunioni

### 17.1 Principio
Il calendario esterno è una **fonte di occupazione esterna della capacità**. Una riunione **non** diventa un task.

### 17.2 Nuova riunione
Rilevata -> memorizzata -> calcolo riduzione capacità -> Planning Proposal se il piano è impattato -> shift mostrato -> approvazione -> snapshot. L'evento esiste indipendentemente dall'approvazione della ripianificazione.

### 17.3 Riunione spostata
Trattata come **una singola variazione**, non cancellazione + nuova. Si ricalcola la capacità del vecchio e del nuovo intervallo.

### 17.4 Riunione cancellata
Recupera capacità. Il sistema **non compatta automaticamente** il piano: propone, l'utente decide.

### 17.5 Stato riunione
Accettata -> occupa capacità. Tentative/provvisoria -> occupa capacità. Rifiutata -> non occupa capacità.

### 17.6 Eventi sovrapposti
La capacità occupata si calcola sull'**unione degli intervalli**. Due meeting sovrapposti non possono sottrarre due volte lo stesso minuto.

### 17.7 Bidirezionalità
- Calendario -> Work Planner: gli eventi modificano la capacità.
- Work Planner -> calendario: il piano viene pubblicato/sincronizzato.

Le modifiche provenienti dal calendario **non possono bypassare l'approvazione** del nuovo piano dei task.

## 18. Google Calendar e iCalendar

Almeno sincronizzazione in uscita del piano, più un feed **iCalendar (ICS) sottoscrivibile**.

- Non deve essere necessario esportare manualmente un file a ogni modifica.
- Il calendario deve aggiornarsi automaticamente.
- L'export `.ics` statico può esistere come funzione aggiuntiva, non come meccanismo principale.

## 19. Vista calendario

Vista settimanale. Ogni giorno rende leggibili: capacità base; capacità occupata da riunioni; ferie/permessi; task pianificati; capacità residua.

Task col colore del progetto. Riunioni con stile distinto e neutro. Assenze chiaramente distinguibili.

### 19.1 Proposal panel
Area facilmente raggiungibile con le proposal pendenti: motivo; before; after; warning; conflitti; approve; reject.

### 19.2 Timeline multi-settimana
Vista compatta per capire allocazione e slittamenti su più settimane.

## 20. Planning Report

Report graficamente curato, non uno screenshot della UI. Leggibile, professionale, allegabile a email, condivisibile. Formati PDF e PNG.

Contenuti: intervallo temporale; progetti; task; effort; timeline; delivery previste; capacità; note pubbliche.

## 21. Impact Report

Mostra visivamente come una richiesta modifica la pianificazione: prima; nuova richiesta; dopo; effetti (`Task A: +1 giorno`). Esportabile in PDF/PNG.

## 22. Snapshot del piano

Ogni modifica approvata produce uno **snapshot immutabile**, copia **completa** dello stato rilevante della timeline, non un diff. Semplifica audit, confronto, rollback concettuale, report, ricostruzione della storia.

Ripristinare uno snapshot non cancella la storia: genera una nuova azione/versione.

## 23. History, audit, undo e redo

> Tutte le azioni significative devono essere memorizzate e, dove semanticamente possibile, annullabili.

Modello a **command/action log + snapshot**, non event sourcing puro.

### 23.1 Action
Registra: id; action type; origine; autore; timestamp; entità coinvolte; before JSON; after JSON; planning snapshot; reversible; riferimento all'azione annullata/ripetuta.

Origini: UI; Claude/API; calendario; sistema.

### 23.2 Soft delete
Le cancellazioni di entità interne sono soft delete.

### 23.3 Undo
Non elimina l'azione originale: crea una nuova azione inversa. Se modifica il piano: contro-operazione sullo stato corrente -> proposal -> impatto -> conferma -> applicazione -> nuovo snapshot/action.

### 23.4 Undo non lineare
Dalla history si può tentare di annullare **qualsiasi** azione reversibile, non solo l'ultima. L'undo deve essere validato contro lo stato attuale. Può: riuscire; richiedere una proposal; produrre warning; produrre conflitti; essere impossibile.

### 23.5 Redo
Simmetrico all'undo. Non ripristina ciecamente vecchi dati: tenta di riapplicare **semanticamente** l'azione originale sullo stato corrente.

### 23.6 Calendario e undo
Non si può usare Work Planner per annullare arbitrariamente un evento esterno. Si può annullare **l'effetto** che una precedente decisione ha avuto sul nostro piano.

## 24. Modello dati preliminare

Entità principali: `User`, `Project`, `Task`, `PlanningSegment`, `WeeklyCapacity`, `CapacityException`, `ExternalCalendarConnection`, `ExternalCalendarEvent`, `PlanningProposal`, `PlanningSnapshot`, `Action`, `ManagerShareLink`, `ApiToken`, `Report`.

`PlanningProposal` deve contenere o rendere disponibili anche gli effetti della simulazione: cambiamenti, warning, conflitti e motivazioni leggibili.

`PlanningReason` — oggetto di dominio, non necessariamente tabella persistente, che spiega perché lo scheduler ha effettuato una scelta o prodotto un conflitto.

Campi: `type`; `task_id`; `related_task_id`; `date`; `hours`; `severity`; `message`.

Tipi: `CAPACITY_REDUCED`; `TARGET_MISSED`; `FIXED_DATE_CONFLICT`; `USER_REORDER`; `CALENDAR_EVENT`; `EFFORT_INCREASE`; `TASK_COMPLETED`; `QUEUE_COMPACTION`.

PlanningReason alimenta proposal UI, Impact Report, Claude, history e diagnostica dello scheduler.

## 25. Schema API preliminare

```
GET/POST          /api/tasks
GET/PATCH/DELETE  /api/tasks/{id}
GET               /api/inbox
POST              /api/inbox/quick-add
POST              /api/tasks/{id}/effort/propose
POST              /api/tasks/{id}/effort/change
GET               /api/planning
GET               /api/planning/context
POST              /api/planning/simulate
GET               /api/proposals
GET               /api/proposals/{id}
POST              /api/proposals/{id}/approve
POST              /api/proposals/{id}/reject
POST              /api/proposals/{id}/recalculate
GET               /api/capacity
POST              /api/capacity/exceptions
PATCH/DELETE      /api/capacity/exceptions/{id}
GET               /api/snapshots
GET               /api/snapshots/{id}
GET               /api/actions
GET               /api/actions/{id}
POST              /api/actions/{id}/undo
POST              /api/actions/{id}/redo
POST              /api/reports/planning
POST              /api/reports/impact
POST/GET          /api/share-links
DELETE            /api/share-links/{id}
GET               /api/integrations
```

Le modifiche che impattano il piano devono generare proposal, non applicazioni dirette.

## 26. Transazionalità e concorrenza

L'approvazione di una proposal deve essere **transazionale**. Non deve essere possibile applicare una proposal calcolata su un piano non più corrente senza rilevare il conflitto.

```
proposal.base_plan_version == current_plan_version
```

Se falso -> `proposal -> STALE`, da ricalcolare.

Importante perché contemporaneamente agiscono UI, Claude, sync calendario e job asincroni.

## 27. Report e Manager View: privacy per campo

Distinguere dati owner-only; condivisibili; tecnici; pubblicabili nei report.

**Non** serializzare il modello Task completo nella Manager View. Usare DTO/schema di output specifici: `TaskInternalView`, `TaskManagerView`, `TaskClaudeView`, con autorizzazioni e campi espliciti.

## 28. Principi di sicurezza

Password owner hashata; HTTPS in produzione; token API hashati; share token ad alta entropia; revoca dei link; token calendario cifrati/protetti; segreti esclusi dal repository; `.env.example` senza credenziali; rate limiting dove opportuno; audit delle operazioni da API/Claude; validazione server-side di ogni operazione.

> Claude non deve poter bypassare i vincoli dello scheduler chiamando endpoint diversi.

## 29. Regola architetturale fondamentale

```
Vue UI ──────────┐
                 │
Claude REST ─────┼──> Application Services ──> Domain/Scheduler ──> PostgreSQL
                 │
Calendar Sync ───┤
                 │
Report Engine ───┘
```

Non devono esistere implementazioni divergenti delle regole di planning.

## 30. Flusso completo di esempio

Situazione iniziale:

```
Lunedì    MAG bug 4h + RAW development 4h
Martedì   RAW development 8h
```

Arriva una riunione lunedì da 2 ore. Il sistema: importa la riunione; riduce la capacità schedulabile di lunedì da 8h a 6h; **non modifica il piano corrente**; genera una proposal; simula lo shift; mostra `MAG bug invariato`, `RAW development: 2h spostate da lunedì a martedì`, eventuale slittamento successivo; l'utente approva; il backend verifica `base_plan_version`; applica in transazione; crea snapshot; registra Action; aggiorna calendario/report; la Manager View riflette il nuovo piano.

Se la riunione viene poi cancellata: torna capacità disponibile; il sistema **propone** una possibile ottimizzazione; **non anticipa automaticamente** i task; l'utente decide.

## 31. MVP

Docker Compose; FastAPI; Vue 3; PostgreSQL; autenticazione owner; Project; Task; Inbox; Quick Add; effort manuale; effort proposto da Claude; planning segments; scheduler deterministico; capacità standard; ferie/permessi; target/fixed dates; coda manuale con drag & drop; Planning Proposal; preview before/after; approve/reject; snapshot; Action history; undo/redo; calendario settimanale; timeline multi-settimana; drag & drop tramite proposal; REST API per Claude; API token revocabili; Context endpoint; integrazione calendario; import automatico delle riunioni; ricalcolo capacità; Manager View via link revocabile; Planning Report PDF/PNG; Impact Report PDF/PNG; sincronizzazione calendario in uscita; feed iCalendar; Google Calendar almeno in uscita.

**Fuori dall'MVP:** server MCP dedicato; task ricorrenti; event sourcing puro; multi-tenancy complessa.

## 32. Decisioni prese in fase di planning

Queste decisioni **chiudono** i corrispondenti punti aperti della specifica originale.

- **Calendario: solo ICS, in entrata e in uscita.** Niente Microsoft Graph, niente OAuth, niente webhook/delta sync. In ingresso polling dell'URL ICS del calendario Outlook; in uscita Work Planner espone un feed ICS tokenizzato che Outlook e Google sottoscrivono. Realizza §17.7 e §18 con un solo formato standard in due direzioni.
- **Auth owner:** password singola hashata (argon2) + cookie di sessione HttpOnly.
- **Background jobs:** APScheduler in-process. Niente Celery/Redis.
- **Report:** Playwright headless su template HTML, un template per PDF e PNG.
- **UI/UX:** desktop e mobile entrambi curati; su mobile il layout è ripensato, non compresso.
- **Deploy:** sottodominio pubblico dietro reverse proxy + TLS.

### 32.2 Algoritmo dello scheduler

Lo scheduler è volutamente semplice e prevedibile. **Non** assegna punteggi, **non** calcola priorità implicite, **non** decide quale lavoro sia più importante.

> Il planning è una coda temporale ordinata manualmente dall'utente. Lo scheduler riempie la capacità disponibile procedendo in avanti nel tempo.

**32.2.1 Ordine dei task.** L'ordine della coda è la priorità effettiva, deciso dall'utente, mai ricalcolato. Un nuovo task entra nella posizione prevista e viene pianificato nel primo spazio disponibile coerente con tale ordine. Non sposta lavoro già pianificato solo perché è stato creato. Non esistono: priority score automatici; formule di rischio temporale; ordinamenti euristici; pesi relativi.

**32.2.2 Riempimento in avanti — modello "bicchiere".** Lo scheduler scorre il tempo in avanti e usa la prima capacità disponibile. Se oggi e domani sono pieni e arriva un task da 12h, non sposta il pianificato: parte dal primo spazio libero successivo, distribuendosi automaticamente (es. 8h mercoledì + 4h giovedì).

**32.2.3 Spostamento esplicito e urgenza.** Il lavoro pianificato si sposta quando l'utente modifica esplicitamente l'ordine.

```
PRIMA                          L'UTENTE PORTA TASK X (12h) ALL'INIZIO
Lunedì      Task A 8h          Lunedì      Task X 8h
Martedì     Task B 8h          Martedì     Task X 4h + Task A 4h
Mercoledì   Task C 8h          Mercoledì   Task A 4h + Task B 4h
                               Giovedì     Task B 4h + Task C 4h
```

Il concetto di URGENT non introduce un secondo algoritmo: l'urgenza è l'azione dell'utente che sposta il task nella coda.

**32.2.4 Proposal.** Una modifica manuale dell'ordine non viene applicata direttamente: nuovo ordine -> ricalcolo del riempimento -> verifica vincoli -> Planning Proposal -> prima/dopo, delivery modificate, warning, conflitti -> applicazione solo dopo approvazione. Il drag & drop è **un'intenzione**, non una modifica diretta dei PlanningSegment.

**32.2.5 Vincoli.** Lo scheduler rispetta: capacità realmente disponibile; ferie e permessi; eventi calendario che riducono la capacità; fixed date; segmenti esplicitamente bloccati. Una target date non modifica l'ordine: se l'ordine scelto la supera, si segnala il ritardo invece di riordinare. Una fixed date è hard constraint: se non rispettabile, la proposal evidenzia il conflitto.

**32.2.6 Stabilità del piano.** In assenza di azione esplicita, il piano approvato resta stabile. Nuova capacità disponibile (es. riunione cancellata) **non** provoca l'anticipo automatico dei task. Il sistema può proporre un'ottimizzazione, non applicarla.

**32.2.7 Determinismo ed explainability.** A parità di base snapshot, ordine della coda, capacità, vincoli, input e scheduler version, lo scheduler produce lo stesso risultato. Ogni spostamento significativo è spiegato da un PlanningReason.

**32.2.8 Decisioni congelate in fase di planning:**

- **Granularità minima del PlanningSegment: 30 minuti.** Un buco residuo inferiore non viene riempito, per evitare schegge illeggibili. Costante configurabile in un unico punto.
- **Fixed date = solo validatore, mai riordino.** Lo scheduler non anticipa un task per rispettarne la fixed date. Se il riempimento in avanti lo colloca oltre, produce `FIXED_DATE_CONFLICT` che blocca l'approvazione; sta all'utente riordinare la coda.
- **Fixed date multiple incompatibili:** si emette un conflitto **per ciascuna**, non solo il primo.
- **IN_PROGRESS:** il task resta nella sua posizione di coda e viene ripianificato come gli altri, ma non può essere spostato indietro rispetto a oggi; i suoi segmenti passati sono immutabili.
- **Orizzonte:** lo scheduling parte da **oggi come giorno intero**, non da "adesso". Il minuto corrente non è un'unità di pianificazione utile e introdurrebbe non-determinismo nei test.
- **Segmenti bloccati (`locked`):** consumano capacità nel loro giorno e non vengono mossi da una ri-simulazione; il resto della coda scorre intorno.
- **Tie-breaking:** `(queue_position, task.created_at, task.id)` — ordine totale, quindi deterministico.

### 32.4 UX

Principio: **una schermata principale è sufficiente per circa il 90% del lavoro quotidiano.** L'app non deve sembrare un gestionale complesso.

**32.4.1 Planning come schermata principale.** Due aree collegate: **Coda** a sinistra (elenco ordinato manualmente) e **Planning** a destra (rappresentazione temporale del risultato dello scheduler). La coda è la fonte di verità dell'ordine. In alto pochi indicatori sintetici (`OGGI 6h/8h pianificate` · `PROSSIMA CONSEGNA MAG · domani` · `INBOX 3 elementi`). Nessuna Dashboard separata nell'MVP.

**32.4.2 Drag & drop e preview.** Rapido, senza modal invasive. Riordino -> il frontend rappresenta il nuovo ordine -> il backend simula -> il calendario mostra la preview -> **una barra compatta** riassume l'impatto -> `[Annulla] [Applica]`.

```
Piano modificato
3 task spostati · Export slitta a lunedì        [Annulla] [Applica]
```

È una PlanningProposal, ma l'UX non deve farla percepire come una procedura burocratica.

**32.4.3 Inbox.** Minimale. Per pianificare bastano titolo, progetto, effort. Target/fixed opzionali. `Pianifica` mette il task in fondo alla coda.

**32.4.4 Task detail.** Visibili: Titolo, Progetto, Effort stimato, Stato, Target, Note. I campi rari sotto `Avanzate`. **Nessun campo di priorità**: la priorità è la posizione in coda.

**32.4.5 Calendario.** Non è un secondo sistema di pianificazione: visualizza il risultato dello scheduler (blocchi task, meeting, ferie, capacità disponibile, warning). Un drag & drop sul calendario esprime solo un'intenzione e produce una simulazione/proposal.

**32.4.6 Navigazione.** `Planning · Inbox · Projects · History · Reports · Settings`. Il cuore resta Planning.

**32.4.7 Completamento e variazione dell'effort.** Definito in §46.

### 32.19 Test strategy

Attenzione particolare allo scheduler: unit test; property-based test; integration test; test API; test transazioni; test concorrenza; test calendario mock; **golden test** per il planning; test di regressione delle simulazioni. Lo scheduler deve essere estremamente deterministico e ben coperto.

## 33. Simulazione — scenario base

Capacità Lun-Ven 8h. Coda manuale iniziale:

```
1. T1 — Fix MAG import       5h
2. T2 — RAW processing API  12h
3. T3 — QC integration       8h
4. T4 — Manager export       6h
5. T5 — Release cliente      3h — fixed giovedì
```

Materializzazione temporale:

```
LUNEDÌ      T1 5h + T2 3h
MARTEDÌ     T2 8h
MERCOLEDÌ   T2 1h + T3 7h
GIOVEDÌ     T3 1h + T4 4h + T5 3h
VENERDÌ     T4 2h
```

L'ordine è già stato deciso dall'utente; lo scheduler lo trasforma in segmenti.

## 34. Evento: nuova riunione

Riunione lunedì di 2h: la capacità di lunedì passa da 8h a 6h. Il piano approvato non cambia silenziosamente: si genera una preview/proposal che conserva l'ordine e fa scorrere in avanti l'eccedenza.

```
LUNEDÌ      T1 5h + T2 1h
MARTEDÌ     T2 8h
MERCOLEDÌ   T2 3h + T3 5h
...
```

Reason: `CAPACITY_REDUCED` / `CALENDAR_EVENT`.

## 35. Evento: richiesta urgente

Un nuovo task da 6h entra **in fondo** alla coda e non sposta il pianificato. Per renderlo urgente l'utente lo trascina:

```
PRIMA                A → B → C → X
DOPO IL DRAG         X → A → B → C
```

Il backend simula il nuovo riempimento e mostra la preview. Solo dopo conferma diventa il piano corrente. Nessun URGENT, preemption automatica o priority score.

## 36. Evento: permesso o ferie

Un permesso di 4h riduce la capacità di un giorno. Se il piano non è più materializzabile, si genera una proposal che fa scorrere in avanti l'eccedenza mantenendo l'ordine.

Se una fixed date diventa impossibile:

```
HARD CONSTRAINT VIOLATION
Task: Release cliente
Fixed date: giovedì
Missing capacity: 3h
```

Il sistema **non** riordina altri task per risolvere autonomamente il problema.

## 37. Evento: modifica effort

La variazione deve essere **esplicita** (utente o Claude/API autorizzato).

```
change effort -> simulate forward fill -> show preview/proposal -> approve/reject
```

Un aumento allunga il bicchiere e fa slittare il lavoro successivo. Una riduzione non viene dedotta automaticamente: va dichiarata, o derivare dal comando esplicito `COMPLETED`.

## 38. Evento: drag & drop

Modifica l'ordine desiderato della coda, non i singoli PlanningSegment.

> **Drag & drop = modifica esplicita dell'ordine + simulazione + conferma.**

## 39. Evento: riunione spostata

Riunione da lunedì a giovedì: `Lunedì +2h capacità`, `Giovedì -2h capacità`.

La capacità recuperata lunedì **non** provoca l'anticipo automatico dei task. La riduzione di giovedì, se rende il piano non fattibile, genera una proposal di shift in avanti mantenendo la coda invariata. **L'asimmetria è intenzionale**: il bicchiere non si compatta da solo, ma reagisce quando una perdita di capacità rende impossibile il piano.

## 40. Evento: riunione cancellata

```
capacity recovered: sì
auto compaction:    no
auto reorder:       no
```

La capacità libera resta visibile finché l'utente o Claude/API non esegue un'azione esplicita.

## 41. Evento: undo non lineare

L'undo non carica ciecamente un vecchio snapshot: applica semanticamente l'operazione inversa allo stato corrente. Se tocca coda, effort o capacità pianificata, si ricalcola il bicchiere e si mostra una proposal quando necessario. La history conserva sia l'azione originale sia l'undo.

## 42. Evento: nuova richiesta manager

Catturata nell'Inbox; dopo progetto ed effort, `Pianifica` la aggiunge **in fondo** alla coda.

```
T7 — Work Planner demo
Effort: 8h
Target: venerdì
```

Se l'utente vuole anticiparla, la sposta manualmente. L'Impact Report mostra gli effetti della **posizione scelta**, non di una priorità calcolata.

## 43. Regole definitive dello scheduler

- **R1 — La coda è la priorità.** L'ordine è deciso dall'utente; lo scheduler non calcola priorità proprie.
- **R2 — Riempimento in avanti.** La coda diventa segmenti usando la prima capacità disponibile nel tempo.
- **R3 — Nuovi task in fondo.** Un nuovo task non sposta il lavoro già approvato.
- **R4 — Nessun movimento implicito.** Il piano resta congelato finché non arriva un'azione esplicita o una riduzione di capacità lo rende non fattibile.
- **R5 — Urgenza = riordino manuale.** Nessuna preemption automatica.
- **R6 — Capacità recuperata non compatta.** Un aumento di capacità non tira il lavoro indietro nel tempo.
- **R7 — COMPLETED compatta.** Il comando esplicito elimina l'effort residuo e compatta in avanti il lavoro successivo mantenendo l'ordine.
- **R8 — Fixed date hard, target informativa.**
- **R9 — Drag & drop è intent.** Passa sempre dalla simulazione prima dell'applicazione.
- **R10 — Determinismo ed explainability.** Stesso stato e input -> risultato identico; ogni shift ha una reason leggibile.

## 44. Planning Reason e struttura delle proposal

Una proposal espone:

```
changes[]  warnings[]  conflicts[]  reasons[]
```

Reason: `USER_REORDER`, `CAPACITY_REDUCED`, `CALENDAR_EVENT`, `EFFORT_INCREASE`, `TASK_COMPLETED`, `QUEUE_COMPACTION`, `TARGET_MISSED`, `FIXED_DATE_CONFLICT`.

Esempi leggibili:

```
Moved because the user moved T6 before T2 in the queue.
Moved forward because Tuesday capacity was reduced by 2h.
Moved earlier because T1 was explicitly marked completed with 3h remaining.
Target missed because the current queue reaches this task after Friday.
```

## 45. Modello congelato

1. l'utente decide l'ordine;
2. lo scheduler riempie in avanti;
3. il planning approvato non si ottimizza autonomamente;
4. gli shift derivano da azioni esplicite o da perdita di capacità;
5. il completamento esplicito può compattare il bicchiere;
6. target e metadati informativi non riordinano nulla;
7. fixed date e capacità restano vincoli reali;
8. ogni cambiamento rilevante passa da preview/proposal.

**Non** fanno parte del modello: priority score, preemption automatica, ordinamento per urgenza, dipendenze tra task, funzioni di costo, euristiche di scheduling.

Le sezioni 33-45 sono la base per i **golden test** e i test di regressione.

## 46. Planning congelato e completamento esplicito

### 46.1 Nessuna compattazione automatica
Se un task stimato 8h finisce di fatto dopo 5h, le 3h residue **non** vengono recuperate automaticamente mentre l'utente lavora. Finché il task non è marcato `COMPLETED`, il calendario resta invariato. Il sistema non deduce avanzamento, completamento o tempo residuo dal trascorrere del tempo.

### 46.2 Completamento del task
`COMPLETED` è un evento esplicito che può modificare il planning. Lo scheduler: considera concluso il task; elimina dal futuro l'effort residuo pianificato; recupera la capacità liberata; prende i task successivi **nell'ordine corrente**; li fa scorrere in avanti nel primo spazio disponibile; **non cambia priorità**; produce la simulazione/proposal prevista dal flusso di approvazione.

```
PRIMA                          Task A completato dopo 5h
Lunedì      Task A 8h          Lunedì      Task A 5h + Task B 3h
Martedì     Task B 8h    ->    Martedì     Task B 5h + Task C 3h
Mercoledì   Task C 8h          Mercoledì   Task C 5h
```

Semplice shift/compattamento del bicchiere, non una nuova ottimizzazione.

### 46.3 Task che richiede più tempo
L'extra effort non viene dedotto automaticamente: va dichiarato esplicitamente. Il bicchiere si allunga e il lavoro successivo slitta in avanti mantenendo l'ordine.

### 46.4 Regola generale

> **Nessun movimento implicito del planning. Il calendario cambia soltanto in risposta a un evento esplicito; quando cambia, lo scheduler applica il minimo shift sequenziale necessario mantenendo l'ordine deciso dall'utente.**
