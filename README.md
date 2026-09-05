# Work Planner

Applicazione personale per pianificare, simulare, versionare e comunicare il
carico di lavoro.

> La timeline rappresenta l'allocazione **prevista e concordata**, non un
> cronometro del tempo effettivamente impiegato.

Non è un task manager e non è un time tracker. Serve a rispondere a due
domande: *su cosa è allocata la mia capacità* e *cosa succede al piano se
arriva questa richiesta*.

## Come funziona

L'ordine della coda **è** la priorità: non esistono punteggi né algoritmi che
decidono cosa conta di più. Lo scheduler prende quella coda e la versa in
avanti nella capacità disponibile — il modello del bicchiere — spezzando
l'effort su più giorni quando serve.

Il piano approvato non si muove da solo. Ogni cambiamento — un riordino, una
riunione che riduce la capacità, una modifica dell'effort, delle ferie —
produce prima una **proposta**: si vede l'impatto, si approva, e solo allora il
piano cambia. Le regole complete stanno in [`work-planner.md`](work-planner.md).

Tre conseguenze che sorprendono chi arriva da un task manager normale:

- **Un task pronto in anticipo non libera capacità.** Il completamento tecnico
  interno e la consegna sono due cose diverse.
- **Capacità recuperata non compatta il piano.** Se una riunione salta, il
  sistema lo propone; non anticipa niente da solo.
- **Una data fissa non riordina la coda.** Se il piano non la rispetta, produce
  un conflitto e sta a te decidere cosa spostare.

## Avvio

```bash
cp .env.example .env
docker compose up -d
docker compose run --rm backend python -m app.cli hash-password
```

Poi `http://localhost:5173`. Per il deploy dietro un tunnel o un reverse proxy:
[`DEPLOY.md`](DEPLOY.md).

## Struttura

| | |
|---|---|
| `backend/app/domain/` | Lo scheduler: **funzioni pure**, nessun database, nessun framework, nessun orologio. È ciò che rende i golden test della specifica banali da scrivere |
| `backend/app/services/` | L'unica sede della business logic: UI, API e sync calendario chiamano queste funzioni |
| `backend/app/api/` | Router sottili: parse, service, DTO |
| `frontend/src/` | Vue 3, mobile-first |
| `skills/work-planner/` | Skill per Claude Code, versionata insieme all'API che descrive |
| `docs/API-CLIENT.md` | Come un altro progetto dialoga con l'API |

## Test

```bash
cd backend && python -m pytest tests -q      # 199
cd frontend && npm run build && npx vitest run
```

Lo scheduler è l'unico punto dove un bug è silenzioso e costoso: passa i test e
produce un piano semplicemente sbagliato. Riceve quindi copertura
sproporzionata — golden test su ogni scenario della specifica, property-based
test sugli invarianti (nessun minuto perso o inventato, nessun giorno oltre la
propria capacità) e un test di determinismo.

## Integrazione calendario

Solo **iCalendar**, in entrambe le direzioni: in ingresso si fa polling del feed
del calendario aziendale, in uscita si espone un feed sottoscrivibile da Outlook
e Google. Un formato standard invece di due integrazioni proprietarie.
