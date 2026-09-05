"""Entry point FastAPI.

I router restano volutamente sottili: parsing della richiesta, chiamata a un
application service, serializzazione del DTO. Ogni regola di planning vive in
app/services e app/domain (vedi work-planner.md §29).

Anche la traduzione errore di dominio -> status HTTP sta qui e non nei router:
è una sola mappa, valida per tutte le superfici.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import auth, capacity, history, planning, proposals, share, tasks, tokens
from .config import settings
from .services.proposals import (
    HardConflictError,
    ProposalError,
    ProposalNotPendingError,
    StaleProposalError,
)
from .services.tasks import InvalidTransitionError

app = FastAPI(title="Work Planner", version="0.1.0")

#: Il frontend gira su un'origine diversa in sviluppo e deve poter mandare il
#: cookie di sessione, quindi allow_credentials con origini esplicite (mai "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_base_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router, tasks.router, planning.router, proposals.router,
    capacity.router, history.router, share.router, tokens.router,
):
    app.include_router(router)


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status)


@app.exception_handler(StaleProposalError)
def _stale(request: Request, exc: StaleProposalError) -> JSONResponse:
    """§12.1/§26: il piano è cambiato sotto la proposal — vera collisione."""
    return _error(409, str(exc))


@app.exception_handler(HardConflictError)
def _conflict(request: Request, exc: HardConflictError) -> JSONResponse:
    """§14.1: la richiesta è comprensibile ma non processabile: viola un vincolo hard."""
    return _error(422, str(exc))


@app.exception_handler(ProposalNotPendingError)
def _not_pending(request: Request, exc: ProposalNotPendingError) -> JSONResponse:
    return _error(409, str(exc))


@app.exception_handler(ProposalError)
def _proposal_error(request: Request, exc: ProposalError) -> JSONResponse:
    return _error(400, str(exc))


@app.exception_handler(LookupError)
def _not_found(request: Request, exc: LookupError) -> JSONResponse:
    return _error(404, str(exc))


@app.exception_handler(InvalidTransitionError)
def _invalid_transition(request: Request, exc: InvalidTransitionError) -> JSONResponse:
    return _error(409, str(exc))


@app.exception_handler(ValueError)
def _invalid(request: Request, exc: ValueError) -> JSONResponse:
    return _error(400, str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
