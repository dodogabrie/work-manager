# Parlare con Work Planner da un altro progetto

Documento **canonico**: i `CLAUDE.md` degli altri repo puntano qui e non
ripetono nulla. Se l'API cambia, si aggiorna questo file soltanto.

- **Base URL**: `https://work-planner.edoardogabrielli.com`
- **OpenAPI**: `/openapi.json` — la fonte di verità sulle forme esatte
- **Token**: `~/.config/work-planner/token` (permessi 600, fuori da ogni repo)

```bash
TOKEN=$(cat ~/.config/work-planner/token)
curl -sH "Authorization: Bearer $TOKEN" \
  https://work-planner.edoardogabrielli.com/api/planning/context
```

Il token **non va messo in un file del repository** né in un `.env` versionato:
è un segreto personale e vale per tutti i progetti.

## Le cinque regole da conoscere prima di scrivere

Work Planner non è un task manager qualunque. Se le ignori, le chiamate
falliscono o — peggio — fanno una cosa diversa da quella che sembra.

1. **La posizione in coda è l'unica priorità.** Non esiste un campo `priority`.
   Per rendere urgente un task lo si sposta, non gli si alza un numero.
2. **Niente modifica il piano direttamente.** Ogni cambiamento che tocca la
   pianificazione restituisce una **proposal** da approvare. Una `POST` che
   risponde `200` con una proposal **non ha applicato nulla**.
3. **L'effort è sempre in minuti**, mai in ore.
4. **Una fixed date è un vincolo hard**: se il piano la viola, la proposal
   contiene un conflitto e l'approvazione viene rifiutata con `422`.
5. **Non è un time tracker.** L'effort pianificato è quanto lavoro viene
   allocato, non quanto tempo hai passato davanti allo schermo. Non ridurlo
   perché un task è stato tecnicamente veloce.

`GET /api/planning/context` restituisce queste regole in `constraints`, insieme
a tutto il contesto: data odierna, progetti, inbox, coda, segmenti, capacità
dei prossimi giorni e proposal pendenti. **È la prima chiamata da fare**: una
sola richiesta invece di sei.

## Le operazioni che servono davvero

### Annotare una richiesta senza pianificarla

Il campo obbligatorio è solo il titolo. Il task entra in Inbox e **non tocca il
piano**: è il modo giusto di catturare qualcosa al volo.

```bash
curl -sX POST "$BASE/api/inbox/quick-add" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Bug import TIFF su fascicoli multipagina",
       "project_id":"<id>","planning_effort_minutes":240}'
```

### Metterlo in coda (genera una proposal)

```bash
# 1. chiedi: risponde con una proposal, il piano NON è ancora cambiato
PROPOSAL=$(curl -sX POST "$BASE/api/tasks/$TASK/status" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"PLANNED"}' | jq -r '.proposal.id')

# 2. guarda l'impatto prima di applicare
curl -sH "Authorization: Bearer $TOKEN" "$BASE/api/proposals/$PROPOSAL" \
  | jq '.simulation | {changes, warnings, conflicts}'

# 3. applica solo se l'utente è d'accordo
curl -sX POST -H "Authorization: Bearer $TOKEN" "$BASE/api/proposals/$PROPOSAL/approve"
```

### Simulare senza lasciare traccia

`POST /api/planning/simulate` risponde con lo stesso impatto ma **non crea
nulla**. Da usare per rispondere a "cosa succede se…" senza sporcare la history.

### Altre operazioni

| Cosa | Endpoint |
|---|---|
| Cambiare l'effort | `POST /api/tasks/{id}/effort/change` → proposal |
| Marcare completato | `POST /api/tasks/{id}/complete` → proposal (compatta in avanti) |
| Spostare in coda | `POST /api/tasks/{id}/move` → proposal |
| Ferie o permesso | `POST /api/capacity/exceptions` → proposal |
| Report per il manager | `POST /api/reports/planning` (`format`: `pdf`\|`png`) |
| Storia e undo | `GET /api/actions`, `POST /api/actions/{id}/undo` |

## Codici di errore che vogliono dire qualcosa

| Codice | Significato | Cosa fare |
|---|---|---|
| `409` | La proposal è **stale**: il piano è cambiato da quando è stata calcolata | `POST /api/proposals/{id}/recalculate`, poi rimostra l'impatto |
| `422` | **Conflitto hard**, tipicamente una fixed date impossibile | Non insistere: il messaggio dice quanta capacità manca |
| `401` | Token assente, sbagliato o revocato | — |

## Regola per Claude

**Non approvare mai una proposal senza che l'utente l'abbia chiesto
esplicitamente.** Mostra l'impatto — task spostati, consegne che slittano,
warning — e aspetta. Il senso dell'applicazione è che il piano cambi solo per
decisione consapevole, e un agente che approva da solo lo svuota di significato.

Se il task riguarda un progetto già presente nel planner, riusa il suo
`project_id` da `context.projects` invece di crearne uno nuovo.
