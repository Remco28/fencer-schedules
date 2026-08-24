from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fencer_schedules.config import Settings
from fencer_schedules.db import Store
from fencer_schedules.exports import csv_bytes, filename_for as export_filename, text_version
from fencer_schedules.load import load_tournament
from fencer_schedules.pdf import filename_for, render_pdf
from fencer_schedules.schedule import (
    add_manual,
    apply_overrides,
    event_by_id,
    is_tracked,
    search_loaded_fencers,
    track_named,
    tracking_overrides,
    untrack_named,
    visible_events,
    other_events,
)
from fencer_schedules.sources.askfred import AskFredClient

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
STATIC_DIR = Path(__file__).parent / "static"
_CODE = re.compile(r"\(([A-Z0-9]{2,8})\)\s*$")


def format_clock(clock) -> str:
    if clock is None:
        return ""
    return clock.strftime("%I:%M %p").lstrip("0")


def initials(name: str) -> str:
    if "," in name:
        last, first = (p.strip() for p in name.split(",", 1))
        return ((last[:1] + first[:1]) or "?").upper()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][:1] + parts[-1][:1]).upper()
    return (name[:2] or "?").upper()


def event_code(name: str) -> str:
    match = _CODE.search(name or "")
    return match.group(1) if match else ""


def format_span(start, end) -> str:
    if start == end:
        return start.strftime("%b %d, %Y").replace(" 0", " ")
    return f"{start.strftime('%b %d').replace(' 0', ' ')}–{end.strftime('%b %d, %Y').replace(' 0', ' ')}"


TEMPLATES.env.filters["clock"] = format_clock
TEMPLATES.env.filters["initials"] = initials
TEMPLATES.env.filters["code"] = event_code
TEMPLATES.env.filters["span"] = format_span


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
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "search.html",
            {"hits": None, "current": store.current(), "loaded": store.list(), "q": ""},
        )

    @app.get("/search", response_class=HTMLResponse)
    def search(request: Request, q: str = ""):
        client = askfred or AskFredClient(settings.askfred_api_token)
        hits = client.search(q)
        return TEMPLATES.TemplateResponse(
            request,
            "search.html",
            {"hits": hits, "current": store.current(), "loaded": store.list(), "q": q},
        )

    @app.post("/tournaments/{askfred_id}/open")
    def open_tournament(askfred_id: str) -> RedirectResponse:
        if store.has(askfred_id):
            store.select(askfred_id)
        else:
            store.save(load_tournament(askfred_id, settings, askfred=askfred))
        return RedirectResponse("/schedule", status_code=303)

    @app.post("/tournaments/{askfred_id}/load")
    def load(askfred_id: str) -> RedirectResponse:
        return open_tournament(askfred_id)

    @app.post("/tournaments/{askfred_id}/remove")
    def remove(askfred_id: str) -> RedirectResponse:
        store.remove(askfred_id)
        if store.current() is None:
            return RedirectResponse("/", status_code=303)
        return RedirectResponse("/schedule", status_code=303)

    @app.get("/schedule", response_class=HTMLResponse)
    def schedule(request: Request, track_q: str = ""):
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        suggestions = search_loaded_fencers(tournament, track_q) if track_q else []
        days = sorted({event.day for event in tournament.events})
        return TEMPLATES.TemplateResponse(
            request,
            "schedule.html",
            {
                "tournament": tournament,
                "events": visible_events(tournament, settings),
                "other_events": other_events(tournament, settings),
                "days": days,
                "loaded": store.list(),
                "settings": settings,
                "track_q": track_q,
                "suggestions": suggestions,
            },
        )

    @app.get("/schedule/events/{event_id}", response_class=HTMLResponse)
    def event_roster(request: Request, event_id: str):
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        event = event_by_id(tournament, event_id)
        if event is None:
            return RedirectResponse("/schedule", status_code=303)
        rows = [
            {"fencer": fencer, "tracked": is_tracked(fencer, settings)}
            for fencer in event.fencers
        ]
        return TEMPLATES.TemplateResponse(
            request,
            "event.html",
            {
                "tournament": tournament,
                "event": event,
                "rows": rows,
            },
        )

    @app.post("/schedule/track")
    def track(
        query: str | None = Form(default=None),
        name: str | None = Form(default=None),
        club: str | None = Form(default=None),
        next: str = Form(default="/schedule"),
    ) -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        if name and club:
            store.save(track_named(tournament, name, club, settings))
        elif query:
            store.save(add_manual(tournament, query, settings))
        return RedirectResponse(next or "/schedule", status_code=303)

    @app.post("/schedule/untrack")
    def untrack(
        name: str = Form(...),
        club: str = Form(...),
        next: str = Form(default="/schedule"),
    ) -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        store.save(untrack_named(tournament, name, club))
        return RedirectResponse(next or "/schedule", status_code=303)

    @app.post("/schedule/refresh")
    def refresh() -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        overrides = tracking_overrides(tournament)
        reloaded = load_tournament(tournament.askfred_id, settings, askfred=askfred)
        store.save(apply_overrides(reloaded, overrides))
        return RedirectResponse("/schedule", status_code=303)

    @app.get("/schedule.csv")
    def schedule_csv():
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        return Response(
            content=csv_bytes(tournament, settings),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{export_filename(tournament, ".csv")}"'},
        )

    @app.get("/schedule.txt")
    def schedule_txt():
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        return Response(
            content=text_version(tournament, settings),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="{export_filename(tournament, ".txt")}"'},
        )

    @app.get("/schedule.pdf")
    def schedule_pdf():
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


app = create_app()


def main() -> int:
    import uvicorn

    uvicorn.run("fencer_schedules.app:app", host="127.0.0.1", port=8765, reload=False)
    return 0
