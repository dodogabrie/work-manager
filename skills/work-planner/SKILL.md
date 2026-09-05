---
name: work-planner
description: Registra il lavoro in Work Planner (work-planner.edoardogabrielli.com) prima di progettare o scrivere codice, e ne mostra l'impatto sulla pianificazione. Usa questa skill quando l'utente chiede di agganciare il repository a Work Planner o al planner, di pianificare un'attività, di stimare o cambiare l'effort di un task, di sapere cosa c'è in coda o quando è prevista una consegna, di simulare l'impatto di una nuova richiesta, di marcare un lavoro come completato, di registrare ferie o permessi, o di generare un report per il manager. Usala anche di tua iniziativa, senza che l'utente nomini il planner, quando stai per iniziare un'attività di sviluppo non banale in un progetto di lavoro il cui CLAUDE.md dichiara l'aggancio a Work Planner.
---

# Work Planner

Work Planner tiene la coda di lavoro, la capacità disponibile e le date di
consegna. Serve a sapere su cosa è allocato il tempo e cosa succede quando
arriva una richiesta nuova.

**Non è un task manager e non è un time tracker.** Se lo tratti come tale
sbaglierai, in modi che l'API non segnala.

## Le tre regole che fanno sbagliare

1. **La posizione in coda è l'unica priorità.** Non esiste un campo `priority`.
   Un task diventa urgente perché lo si sposta in coda, non perché gli si alza
   un numero.
2. **L'effort è sempre in minuti.**
3. **Una risposta `200` che contiene una `proposal` non ha cambiato niente.**
   Ogni operazione che tocca la pianificazione restituisce una proposta da
   approvare. Il piano confermato cambia solo dopo `/approve`.

E una regola di condotta: **non approvare mai una proposal di tua iniziativa.**
Mostra l'impatto e fermati. L'applicazione esiste perché il piano cambi per
decisione consapevole; un agente che approva da solo la svuota di senso.

## Configurazione

- **API**: `https://work-planner.edoardogabrielli.com`
- **Token**: `~/.config/work-planner/token`, come `Authorization: Bearer <token>`

Se il token non c'è, dillo all'utente: si crea da Impostazioni → Token API.
Non inventare un percorso alternativo e non scrivere il token in un file del
repository.

Lo script `scripts/wp` di questa skill incapsula base URL, token e JSON:

```bash
SKILL_DIR/scripts/wp context                    # il piano corrente, in una chiamata
SKILL_DIR/scripts/wp get /api/proposals
SKILL_DIR/scripts/wp post /api/inbox/quick-add '{"title":"..."}'
```

Funziona anche a mano con `curl`, se preferisci vedere cosa passa.

## Procedura: agganciare un repository

Quando l'utente incolla un prompt di aggancio, o chiede di collegare il
progetto:

1. `wp context` — restituisce data odierna, progetti, inbox, coda, segmenti,
   capacità dei prossimi giorni, proposal pendenti e le regole in `constraints`.
   **È la prima chiamata da fare**: una sola richiesta invece di sei.
2. Individua il `project_id` in `context.projects` che corrisponde a questo
   repository. **Non crearne uno nuovo** se ne esiste già uno pertinente.
3. Conferma all'utente a quale progetto ti sei agganciato e quanti task ci sono
   già in coda.

## Procedura: prima di sviluppare

All'inizio di un'attività non banale, **prima** di progettare o scrivere codice:

1. `wp context` e guarda se il lavoro è già un task in coda.
2. Se non c'è, crealo:

```bash
wp post /api/inbox/quick-add \
  '{"title":"Bug import TIFF su fascicoli multipagina",
    "project_id":"<id>","planning_effort_minutes":240}'
```

Il task entra in **Inbox** e **non tocca il piano**. È il modo giusto di
catturare qualcosa senza decidere subito quando farlo.

**Titolo e descrizione stanno stretti.** Il titolo è una riga che dice cosa si
fa; la `description` è **sempre breve e concisa** — due o tre righe al massimo,
quel tanto che serve a riconoscere l'attività fra sei mesi. Niente riassunti del
contratto, niente elenchi di sottopassi, niente stato dell'arte: il planner
mostra i task in lista, e una descrizione lunga la legge nessuno. Il dettaglio
vive nel repository, non qui.

3. Chiedi all'utente se va pianificato ora. Se sì:

```bash
wp post /api/tasks/<id>/status '{"status":"PLANNED"}'      # -> proposal
wp get  /api/proposals/<proposal_id>                        # -> impatto
```

4. **Mostra l'impatto e fermati**: quali task si spostano, quali consegne
   slittano, quali warning. Poi aspetta.

5. Solo se l'utente lo chiede esplicitamente:

```bash
wp post /api/proposals/<proposal_id>/approve
```

### Stimare l'effort

Stima l'effort **convenzionale** del lavoro, non il tempo compresso dall'uso
dell'AI. Se un task che chiunque farebbe in due giorni tu lo chiudi in un'ora,
l'effort resta di due giorni: il planner rappresenta l'allocazione concordata
con chi aspetta la consegna, non le ore passate davanti allo schermo.

## Le altre operazioni

| Cosa | Chiamata |
|---|---|
| Simulare senza lasciare traccia | `POST /api/planning/simulate` — stesso impatto, non crea nulla |
| Cambiare l'effort | `POST /api/tasks/{id}/effort/change` → proposal |
| Marcare completato | `POST /api/tasks/{id}/complete` → proposal (compatta in avanti) |
| Spostare in coda | `POST /api/tasks/{id}/move` → proposal |
| Ferie o permesso | `POST /api/capacity/exceptions` → proposal |
| Report per il manager | `POST /api/reports/planning` (`format`: `pdf` o `png`) |
| Storia e undo | `GET /api/actions`, `POST /api/actions/{id}/undo` |

Per rispondere a «cosa succede se…» usa **`/simulate`**, non creare una
proposal: la history è un registro di decisioni, non di ipotesi.

## Errori che vogliono dire qualcosa

| Codice | Significato | Cosa fare |
|---|---|---|
| `409` | La proposal è **stale**: il piano è cambiato da quando è stata calcolata | `POST /api/proposals/{id}/recalculate`, poi rimostra l'impatto |
| `422` | **Conflitto hard**, tipicamente una fixed date impossibile | Non insistere: il messaggio dice quanta capacità manca. Riferisci il conflitto all'utente |
| `401` | Token assente, sbagliato o revocato | Non ritentare in loop |

Una `fixed_delivery_date` è un vincolo che blocca l'approvazione; una
`target_delivery_date` produce solo un warning. Lo scheduler **non riordina mai
la coda da solo** per far entrare un task entro la sua data: se non ci sta,
segnala il conflitto e sta all'utente decidere se spostarlo.

## Riferimenti

- OpenAPI: `https://work-planner.edoardogabrielli.com/openapi.json` — la fonte
  di verità sulle forme esatte, da consultare invece di indovinare i campi
- Documentazione: [`docs/API-CLIENT.md`](../../docs/API-CLIENT.md) nel repository
  `dodogabrie/work-manager`, dove vive anche questa skill
