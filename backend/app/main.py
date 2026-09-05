"""Entry point FastAPI.

I router restano volutamente sottili: parsing della richiesta, chiamata a un
application service, serializzazione del DTO. Ogni regola di planning vive in
app/services e app/domain (vedi work-planner.md §29).
"""

from fastapi import FastAPI

app = FastAPI(title="Work Planner", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
