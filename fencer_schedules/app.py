from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.load import load_tournament
from fencer_schedules.models import Tournament
from fencer_schedules.pdf import filename_for, render_pdf
from fencer_schedules.schedule import add_manual, search_loaded_fencers, visible_events
from fencer_schedules.sources.askfred import AskFredClient

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(
    settings: Settings | None = None,
    store: Store | None = None,
    askfred: AskFredClient | None = None,
) -> FastAPI:
    settings = settings or Settings.load()
    store = store or Store(settings.database_path)
    app = FastAPI(title="Fencer Schedules")
    app.state.settings = settings
    app.state.store = store
    app.state.askfred = askfred

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        current = store.current()
        return TEMPLATES.TemplateResponse(
            request,
            "search.html",
            {"hits": None, "current": current, "q": ""},
        )

    @app.get("/search", response_class=HTMLResponse)
    def search(request: Request, q: str = "") -> HTMLResponse:
        client = askfred or AskFredClient(settings.askfred_api_token)
        hits = client.search(q)
        return TEMPLATES.TemplateResponse(
            request,
            "search.html",
            {"hits": hits, "current": store.current(), "q": q},
        )

    @app.post("/tournaments/{askfred_id}/load")
    def load(askfred_id: str) -> RedirectResponse:
        tournament = load_tournament(askfred_id, settings, askfred=askfred)
        store.save(tournament)
        return RedirectResponse("/schedule", status_code=303)

    @app.get("/schedule", response_class=HTMLResponse)
    def schedule(request: Request, track_q: str = "") -> HTMLResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        suggestions = search_loaded_fencers(tournament, track_q) if track_q else []
        return TEMPLATES.TemplateResponse(
            request,
            "schedule.html",
            {
                "tournament": tournament,
                "events": visible_events(tournament, settings),
                "settings": settings,
                "track_q": track_q,
                "suggestions": suggestions,
            },
        )

    @app.post("/schedule/track")
    def track(query: str = Form(...)) -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        store.save(add_manual(tournament, query))
        return RedirectResponse("/schedule", status_code=303)

    @app.post("/schedule/refresh")
    def refresh() -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        manuals = _manuals(tournament)
        reloaded = load_tournament(tournament.askfred_id, settings, askfred=askfred)
        for name, club in manuals:
            reloaded = add_manual(reloaded, name)
        store.save(reloaded)
        return RedirectResponse("/schedule", status_code=303)

    @app.get("/schedule.pdf")
    def schedule_pdf() -> Response:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        data = render_pdf(tournament, settings)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_for(tournament)}"'},
        )

    return app


def _manuals(tournament: Tournament) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for event in tournament.events:
        for fencer in event.fencers:
            if fencer.source != "manual":
                continue
            key = (fencer.name, fencer.club)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


app = create_app()


def main() -> int:
    import uvicorn

    uvicorn.run("fencer_schedules.app:app", host="127.0.0.1", port=8765, reload=False)
    return 0
