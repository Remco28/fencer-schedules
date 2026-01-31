# Coolify DB Commands (Short)

## Check DB connection info

```bash
python3 -c "import os; print('DATABASE_URL=', os.getenv('DATABASE_URL')); print('DB_PATH=', os.getenv('DB_PATH'))"
```

## Postgres queries (tables + cached events + tracked fencers)

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); print(conn.execute(sa.text(\"select table_name from information_schema.tables where table_schema='public'\" )).fetchall()); print(conn.execute(sa.text(\"select id,event_id,pool_round_id,de_round_id,is_completed from cached_events where tracked_tournament_id=10\" )).fetchall()); print(conn.execute(sa.text(\"select id,fencer_name,source from tracked_fencers where tracked_tournament_id=10\" )).fetchall()); conn.close()"
```

## Reset cached events for a tournament

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); conn.execute(sa.text(\"delete from cached_events where tracked_tournament_id=10\")); conn.commit(); conn.close(); print('ok')"
```
