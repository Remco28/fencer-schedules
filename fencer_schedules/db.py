from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import DateTime, Text, create_engine, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from fencer_schedules.models import Tournament


class Base(DeclarativeBase):
    pass


class LoadedTournament(Base):
    __tablename__ = "loaded_tournament"

    id: Mapped[int] = mapped_column(primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Store:
    def __init__(self, path: Path) -> None:
        self._engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self._engine)
        self._session = sessionmaker(self._engine, expire_on_commit=False)

    def save(self, tournament: Tournament) -> None:
        expires = datetime.combine(tournament.end_date, datetime.min.time()) + timedelta(hours=48)
        with self._session() as session:
            session.execute(delete(LoadedTournament))
            session.add(LoadedTournament(id=1, payload=tournament.model_dump_json(), expires_at=expires))
            session.commit()

    def current(self) -> Tournament | None:
        self.cleanup()
        with self._session() as session:
            row = session.get(LoadedTournament, 1)
            if row is None:
                return None
            return Tournament.model_validate_json(row.payload)

    def cleanup(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        with self._session() as session:
            session.execute(delete(LoadedTournament).where(LoadedTournament.expires_at < now))
            session.commit()
