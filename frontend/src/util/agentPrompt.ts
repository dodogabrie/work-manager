/* Prompt da incollare in una chat Claude Code aperta su un progetto di lavoro.
 *
 * Serve a agganciare l'agente a QUESTO progetto del planner: da lì in poi
 * registra il lavoro e propone la pianificazione prima di progettare.
 *
 * È volutamente autosufficiente — base URL, id del progetto e procedura — così
 * funziona anche in un repo il cui CLAUDE.md non è stato ancora aggiornato.
 */

const DOC = 'https://github.com/dodogabrie/work-manager/blob/main/docs/API-CLIENT.md'

export function agentPrompt(project: { id: string; name: string }, base: string): string {
  return `Aggancia questo repository a Work Planner, progetto "${project.name}".

API:      ${base}
Progetto: ${project.id}
Token:    ~/.config/work-planner/token  (usalo come \`Authorization: Bearer <token>\`)

Da ora in avanti, PRIMA di progettare o scrivere codice per un'attività non
banale:

1. Leggi il piano corrente: GET ${base}/api/planning/context
2. Se il lavoro non è già un task in coda, crealo con
   POST ${base}/api/inbox/quick-add
   passando project_id "${project.id}" e una stima dell'effort IN MINUTI.
3. Chiedimi se va pianificato ora. Se sì, POST /api/tasks/{id}/status con
   {"status":"PLANNED"} restituisce una PROPOSAL: mostrami l'impatto (task
   spostati, consegne che slittano, warning) e fermati lì.
4. Non approvare mai una proposal di tua iniziativa: /approve si chiama solo
   se te lo chiedo esplicitamente.

Tre cose da non sbagliare:
- La posizione in coda è l'unica priorità: non esiste un campo "priority".
- L'effort è sempre in minuti.
- Una risposta 200 che contiene una proposal NON ha cambiato il piano.

L'effort da dichiarare è quello convenzionale del lavoro, non il tempo
compresso dall'uso dell'AI: il planner rappresenta l'allocazione concordata,
non cronometra le ore passate al computer.

Documentazione completa: ${DOC}

Conferma di esserti agganciato leggendo il contesto e dicendomi quanti task ci
sono già in coda per questo progetto.`
}
