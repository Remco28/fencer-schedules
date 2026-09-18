from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fencer_schedules.config import DEFAULT_ALERT_RECIPIENT, Settings
from fencer_schedules.db import Store
from fencer_schedules.exports import csv_bytes, text_version
from fencer_schedules.exports import filename_for as export_filename
from fencer_schedules.load import load_tournament
from fencer_schedules.monitor import alert_times_for, normalize_alert_times
from fencer_schedules.pdf import filename_for, render_pdf
from fencer_schedules.schedule import (
    add_manual,
    day_label,
    day_parts,
    event_by_id,
    is_tracked,
    merge_refresh,
    other_events,
    result_label,
    result_place,
    search_loaded_fencers,
    track_named,
    untrack_named,
    visible_events,
)
from fencer_schedules.sources.askfred import AskFredClient
from fencer_schedules.sources.usfa import UsfaClient

logger = logging.getLogger("fencer_schedules.app")

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
STATIC_DIR = Path(__file__).parent / "static"
_CODE = re.compile(r"\(([A-Z0-9]{2,8})\)\s*$")


def _results_due(tournament, event, now: datetime) -> bool:
    """False while a recent attempt to fetch this event's results is still fresh."""
    checked = tournament.results_checked.get(event.source_event_id)
    if checked is None:
        return True
    return now - checked >= RESULTS_RETRY


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


def event_finished(event, today: date | None = None) -> bool:
    return event.day < (today or date.today())


def format_span(start, end) -> str:
    if start == end:
        return start.strftime("%b %d, %Y").replace(" 0", " ")
    return f"{start.strftime('%b %d').replace(' 0', ' ')}–{end.strftime('%b %d, %Y').replace(' 0', ' ')}"


TEMPLATES.env.filters["clock"] = format_clock
TEMPLATES.env.filters["initials"] = initials
TEMPLATES.env.filters["code"] = event_code
TEMPLATES.env.filters["span"] = format_span
TEMPLATES.env.filters["finished"] = event_finished
TEMPLATES.env.filters["result_place"] = result_place
TEMPLATES.env.filters["result_label"] = result_label
TEMPLATES.env.filters["day_label"] = day_label
TEMPLATES.env.filters["day_parts"] = day_parts
TEMPLATES.env.tests["finished"] = event_finished

# How long to leave a finished event alone before asking USA Fencing again for
# results it has not published yet.
RESULTS_RETRY = timedelta(minutes=30)

_SOURCE_ERRORS = {
    "refresh": "Could not refresh from AskFRED. The saved start list is unchanged.",
    "search": "Could not search AskFRED right now. Try again in a moment.",
    "load": "Could not load that tournament from AskFRED. Try again in a moment.",
}
_SOURCE_NOTICES = {
    "refresh": "Start list updated.",
}


def source_error(request: Request) -> str | None:
    return _SOURCE_ERRORS.get(request.query_params.get("error") or "")


def source_notice(request: Request) -> str | None:
    return _SOURCE_NOTICES.get(request.query_params.get("ok") or "")


def create_app(
    settings: Settings | None = None,
    store: Store | None = None,
    askfred: AskFredClient | None = None,
    usfa: UsfaClient | None = None,
) -> FastAPI:
    settings = settings or Settings.load()
    store = store or Store(settings.database_path)
    # One HTTP client per upstream for the whole process: building them per
    # request leaked connection pools and defeated the AskFRED search cache.
    askfred = askfred or AskFredClient(settings.askfred_api_token)
    usfa = usfa or UsfaClient()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        for client in (app.state.askfred, app.state.usfa):
            close = getattr(client, "close", None)
            if callable(close):
                close()

    app = FastAPI(title="Fencer Schedules", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.askfred = askfred
    app.state.usfa = usfa
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def load_visible_results(tournament):
        if not tournament.usfa_id:
            return tournament
        events = visible_events(tournament, settings)
        now = datetime.now()
        wanted = {
            event.source_event_id
            for event in events
            if event_finished(event)
            and event.results is None
            and _results_due(tournament, event, now)
        }
        if not wanted:
            return tournament
        changed = False
        checked = dict(tournament.results_checked)
        updated_events = []
        for event in tournament.events:
            if event.source_event_id not in wanted:
                updated_events.append(event)
                continue
            checked[event.source_event_id] = now
            try:
                results = usfa.fetch_results(tournament.usfa_id, event.source_event_id)
            except Exception as exc:
                results = []
                logger.warning(
                    "results fetch failed for %s/%s: %s",
                    tournament.usfa_id,
                    event.source_event_id,
                    exc,
                )
            if results:
                event = event.model_copy(update={"results": results})
                changed = True
            updated_events.append(event)
        if not changed and checked == tournament.results_checked:
            return tournament
        tournament = tournament.model_copy(
            update={"events": updated_events, "results_checked": checked}
        )
        store.save(tournament, select=False, keep_expiry=True)
        return tournament


    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return TEMPLATES.TemplateResponse(
            request,
            "search.html",
            {
                "hits": None,
                "current": store.current(),
                "loaded": store.list(),
                "q": "",
                "error": source_error(request),
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    def search(request: Request, q: str = ""):
        try:
            hits = askfred.search(q)
            error = None
        except Exception:
            logger.exception("AskFRED search failed")
            hits = []
            error = _SOURCE_ERRORS["search"]
        return TEMPLATES.TemplateResponse(
            request,
            "search.html",
            {
                "hits": hits,
                "current": store.current(),
                "loaded": store.list(),
                "q": q,
                "error": error,
            },
        )

    @app.post("/tournaments/{askfred_id}/open")
    def open_tournament(askfred_id: str) -> RedirectResponse:
        if store.has(askfred_id):
            store.select(askfred_id)
            return RedirectResponse("/schedule", status_code=303)
        try:
            store.save(load_tournament(askfred_id, settings, askfred=askfred, usfa=usfa))
        except Exception:
            logger.exception("load failed for %s", askfred_id)
            return RedirectResponse("/?error=load", status_code=303)
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
        tournament = load_visible_results(tournament)
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
                "club_watching": store.watch_for(tournament.askfred_id, None, "club") is not None,
                "error": source_error(request),
                "notice": source_notice(request),
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
        if (
            event_finished(event)
            and tournament.usfa_id
            and event.results is None
            and _results_due(tournament, event, datetime.now())
        ):
            checked = dict(tournament.results_checked)
            checked[event.source_event_id] = datetime.now()
            try:
                results = usfa.fetch_results(tournament.usfa_id, event.source_event_id)
                if results:
                    event = event.model_copy(update={"results": results})
            except Exception as exc:
                # Results are a convenience; a temporary upstream failure must
                # not make the saved roster unavailable.
                logger.warning(
                    "results fetch failed for %s/%s: %s",
                    tournament.usfa_id,
                    event.source_event_id,
                    exc,
                )
            tournament = tournament.model_copy(
                update={
                    "events": [
                        event if candidate.source_event_id == event_id else candidate
                        for candidate in tournament.events
                    ],
                    "results_checked": checked,
                }
            )
            store.save(tournament, select=False, keep_expiry=True)
        rows = [
            {
                "fencer": fencer,
                "tracked": is_tracked(fencer, settings),
                "place": result_place(event, fencer),
                "place_label": result_label(event, fencer),
            }
            for fencer in event.fencers
        ]
        result_rows = [
            {
                "result": result,
                "tracked": any(
                    fencer.name.casefold() == result.name.casefold()
                    and fencer.club.casefold() == result.club.casefold()
                    and is_tracked(fencer, settings)
                    for fencer in event.fencers
                ),
            }
            for result in (event.results or [])
        ]
        return TEMPLATES.TemplateResponse(
            request,
            "event.html",
            {
                "tournament": tournament,
                "event": event,
                "rows": rows,
                "event_watching": store.watch_for(tournament.askfred_id, event_id, "all") is not None,
                "event_finished": event_finished(event),
                "result_rows": result_rows,
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
        try:
            reloaded = load_tournament(
                tournament.askfred_id, settings, askfred=askfred, usfa=usfa
            )
        except Exception:
            logger.exception("refresh failed for %s", tournament.askfred_id)
            return RedirectResponse("/schedule?error=refresh", status_code=303)
        store.save(merge_refresh(tournament, reloaded))
        return RedirectResponse("/schedule?ok=refresh", status_code=303)

    @app.post("/schedule/watch")
    def toggle_club_watch(next: str = Form(default="/schedule")) -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        if store.watch_for(tournament.askfred_id, None, "club") is not None:
            store.delete_watch(tournament.askfred_id, None, "club")
        else:
            store.set_watch(tournament.askfred_id, None, "club")
        return RedirectResponse(next or "/schedule", status_code=303)

    @app.post("/schedule/events/{event_id}/watch")
    def toggle_event_watch(event_id: str, next: str = Form(default="")) -> RedirectResponse:
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        if store.watch_for(tournament.askfred_id, event_id, "all") is not None:
            store.delete_watch(tournament.askfred_id, event_id, "all")
        else:
            store.set_watch(tournament.askfred_id, event_id, "all")
        return RedirectResponse(next or f"/schedule/events/{event_id}", status_code=303)

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        recipient = store.get_setting("alert_recipient", DEFAULT_ALERT_RECIPIENT)
        return TEMPLATES.TemplateResponse(
            request,
            "settings.html",
            {
                "recipient": recipient,
                "alert_times": alert_times_for(store),
                "saved": request.query_params.get("saved") == "1",
            },
        )

    @app.post("/settings")
    async def settings_save(request: Request) -> RedirectResponse:
        form = await request.form()
        recipient = str(form.get("recipient", "") or "").strip()
        raw_times = form.getlist("alert_times")
        normalized = normalize_alert_times(raw_times)
        store.set_setting("alert_recipient", recipient)
        if normalized:
            store.set_setting("alert_times", normalized)
        else:
            # Empty/invalid posts fall back to the default on read; persist
            # the default so the stored value stays a valid HH:MM list.
            store.set_setting("alert_times", ",".join(alert_times_for(store)))
        return RedirectResponse("/settings?saved=1", status_code=303)

    @app.get("/schedule.csv")
    def schedule_csv():
        tournament = store.current()
        if tournament is None:
            return RedirectResponse("/", status_code=303)
        tournament = load_visible_results(tournament)
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
        tournament = load_visible_results(tournament)
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
        tournament = load_visible_results(tournament)
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

    uvicorn.run("fencer_schedules.app:app", host="0.0.0.0", port=8765, reload=False)
    return 0
