from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import DateTime, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from fencer_schedules.models import Tournament


class Base(DeclarativeBase):
    pass


class StoredTournament(Base):
    __tablename__ = "stored_tournaments"

    askfred_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Selection(Base):
    __tablename__ = "selection"

    id: Mapped[int] = mapped_column(primary_key=True)
    askfred_id: Mapped[str | None] = mapped_column(String, nullable=True)


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[int] = mapped_column(primary_key=True)
    askfred_id: Mapped[str] = mapped_column(String, index=True)
    event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    notify_kind: Mapped[str] = mapped_column(String)  # "club" | "all"
    last_seen: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Store:
    def __init__(self, path: Path) -> None:
        self._engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self._engine)
        self._session = sessionmaker(self._engine, expire_on_commit=False)

    # ---- tournaments ----

    def save(self, tournament: Tournament, select: bool = True, now: datetime | None = None) -> None:
        now = now or datetime.now()
        event_expiry = datetime.combine(tournament.end_date, datetime.min.time()) + timedelta(hours=48)
        expires = max(event_expiry, now + timedelta(hours=48))
        with self._session() as session:
            session.merge(
                StoredTournament(
                    askfred_id=tournament.askfred_id,
                    payload=tournament.model_dump_json(),
                    expires_at=expires,
                )
            )
            if select:
                session.merge(Selection(id=1, askfred_id=tournament.askfred_id))
            session.commit()

    def get(self, askfred_id: str, now: datetime | None = None) -> Tournament | None:
        self.cleanup(now=now)
        with self._session() as session:
            row = session.get(StoredTournament, askfred_id)
            if row is None:
                return None
            return Tournament.model_validate_json(row.payload)

    def has(self, askfred_id: str) -> bool:
        return self.get(askfred_id) is not None

    def list(self, now: datetime | None = None) -> list[Tournament]:
        self.cleanup(now=now)
        with self._session() as session:
            rows = session.scalars(select(StoredTournament)).all()
        tournaments = [Tournament.model_validate_json(row.payload) for row in rows]
        tournaments.sort(key=lambda t: (t.start_date, t.name))
        return tournaments

    def select(self, askfred_id: str) -> Tournament | None:
        tournament = self.get(askfred_id)
        if tournament is None:
            return None
        with self._session() as session:
            session.merge(Selection(id=1, askfred_id=askfred_id))
            session.commit()
        return tournament

    def current(self, now: datetime | None = None) -> Tournament | None:
        self.cleanup(now=now)
        with self._session() as session:
            sel = session.get(Selection, 1)
            if sel is None or not sel.askfred_id:
                return None
            row = session.get(StoredTournament, sel.askfred_id)
            if row is None:
                return None
            return Tournament.model_validate_json(row.payload)

    def remove(self, askfred_id: str) -> None:
        with self._session() as session:
            session.execute(delete(StoredTournament).where(StoredTournament.askfred_id == askfred_id))
            session.execute(delete(Watch).where(Watch.askfred_id == askfred_id))
            sel = session.get(Selection, 1)
            if sel and sel.askfred_id == askfred_id:
                leftover = session.scalars(select(StoredTournament.askfred_id)).first()
                sel.askfred_id = leftover
            session.commit()

    def cleanup(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        with self._session() as session:
            expired = session.scalars(
                select(StoredTournament.askfred_id).where(StoredTournament.expires_at < now)
            ).all()
            session.execute(delete(StoredTournament).where(StoredTournament.expires_at < now))
            if expired:
                session.execute(delete(Watch).where(Watch.askfred_id.in_(list(expired))))
            sel = session.get(Selection, 1)
            if sel and sel.askfred_id:
                still = session.get(StoredTournament, sel.askfred_id)
                if still is None:
                    sel.askfred_id = session.scalars(select(StoredTournament.askfred_id)).first()
            session.commit()

    # ---- watches ----

    def watches(self) -> list[Watch]:
        with self._session() as session:
            return list(session.scalars(select(Watch)).all())

    def watch_for(self, askfred_id: str, event_id: str | None, notify_kind: str) -> Watch | None:
        with self._session() as session:
            stmt = select(Watch).where(
                Watch.askfred_id == askfred_id,
                Watch.event_id == event_id,
                Watch.notify_kind == notify_kind,
            )
            return session.scalars(stmt).first()

    def set_watch(self, askfred_id: str, event_id: str | None, notify_kind: str) -> Watch:
        with self._session() as session:
            stmt = select(Watch).where(
                Watch.askfred_id == askfred_id,
                Watch.event_id == event_id,
                Watch.notify_kind == notify_kind,
            )
            row = session.scalars(stmt).first()
            if row is not None:
                row.updated_at = datetime.now()
                session.commit()
                return row
            row = Watch(askfred_id=askfred_id, event_id=event_id, notify_kind=notify_kind)
            session.add(row)
            session.commit()
            return row

    def delete_watch(self, askfred_id: str, event_id: str | None, notify_kind: str) -> None:
        with self._session() as session:
            stmt = delete(Watch).where(
                Watch.askfred_id == askfred_id,
                Watch.event_id == event_id,
                Watch.notify_kind == notify_kind,
            )
            session.execute(stmt)
            session.commit()

    def delete_watches(self, askfred_id: str) -> None:
        with self._session() as session:
            session.execute(delete(Watch).where(Watch.askfred_id == askfred_id))
            session.commit()

    def save_last_seen(self, watch: Watch, last_seen: dict) -> None:
        with self._session() as session:
            row = session.get(Watch, watch.id)
            if row is None:
                return
            row.last_seen = json.dumps(last_seen)
            row.updated_at = datetime.now()
            session.commit()

    # ---- app settings ----

    def get_setting(self, key: str, default: str = "") -> str:
        with self._session() as session:
            row = session.get(AppSetting, key)
            return row.value if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self._session() as session:
            session.merge(AppSetting(key=key, value=value))
            session.commit()
