# Coolify DB Commands (Short)

## Check DB connection info

```bash
python3 -c "import os; print('DATABASE_URL=', os.getenv('DATABASE_URL')); print('DB_PATH=', os.getenv('DB_PATH'))"
```

## Postgres queries (tables + cached events + tracked fencers)

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); print(conn.execute(sa.text(\"select table_name from information_schema.tables where table_schema='public'\" )).fetchall()); print(conn.execute(sa.text(\"select id,event_id,pool_round_id,de_round_id,is_completed from cached_events where tracked_tournament_id=10\" )).fetchall()); print(conn.execute(sa.text(\"select id,fencer_name,source from tracked_fencers where tracked_tournament_id=10\" )).fetchall()); conn.close()"
```

## Same queries for tournament id 13 (current Freehold event)

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); print(conn.execute(sa.text(\"select id,event_id,pool_round_id,de_round_id,is_completed from cached_events where tracked_tournament_id=13\" )).fetchall()); print(conn.execute(sa.text(\"select id,fencer_name,source from tracked_fencers where tracked_tournament_id=13\" )).fetchall()); conn.close()"
```

## Check is_completed after a refresh (tournament id 13)

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); print(conn.execute(sa.text(\"select id,event_id,is_completed from cached_events where tracked_tournament_id=13\" )).fetchall()); conn.close()"
```

## Show counts for all tournaments (to find the one with data)

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); print('cached_events counts:', conn.execute(sa.text(\"select tracked_tournament_id, count(*) from cached_events group by tracked_tournament_id order by tracked_tournament_id\" )).fetchall()); print('tracked_fencers counts:', conn.execute(sa.text(\"select tracked_tournament_id, count(*) from tracked_fencers group by tracked_tournament_id order by tracked_tournament_id\" )).fetchall()); conn.close()"
```

## List tracked fencers for ALL tournaments

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); print(conn.execute(sa.text(\"select tracked_tournament_id,fencer_name,source from tracked_fencers order by tracked_tournament_id,fencer_name\" )).fetchall()); conn.close()"
```

## Reset cached events for a tournament

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); conn.execute(sa.text(\"delete from cached_events where tracked_tournament_id=10\")); conn.commit(); conn.close(); print('ok')"
```

## Reset cached events for tournament id 13

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); conn.execute(sa.text(\"delete from cached_events where tracked_tournament_id=13\")); conn.commit(); conn.close(); print('ok')"
```

## Reset completion flag for tournament id 13 and immediately verify

```bash
python3 -c "import os; import sqlalchemy as sa; url=os.environ['DATABASE_URL'].replace('postgres://','postgresql://',1); eng=sa.create_engine(url); conn=eng.connect(); conn.execute(sa.text(\"update cached_events set is_completed=false, completed_at=NULL where tracked_tournament_id=13\")); conn.commit(); print(conn.execute(sa.text(\"select id,event_id,is_completed,completed_at from cached_events where tracked_tournament_id=13\" )).fetchall()); conn.close()"
```

---

## DE tableau debug (save raw HTML + JS table HTML)

```bash
# Save the DE tableau HTML to /tmp/ftl_de.html
python3 -c "import requests; url='https://www.fencingtimelive.com/tableaus/scores/BA660C4B8C3949DAB4250EA99848E00E/15C08869F21543279512948F0398C58F'; html=requests.get(url, timeout=15).text; open('/tmp/ftl_de.html','w').write(html); print('wrote /tmp/ftl_de.html', 'len=', len(html))"
```

```bash
# Quick sanity check: does the HTML contain elimTableau?
python3 -c "html=open('/tmp/ftl_de.html').read(); print('has elimTableau=', 'elimTableau' in html, 'has tableauPanel=', 'tableauPanel' in html)"
```

```bash
# If it is JS-rendered, fetch trees and table HTML directly and save to /tmp/ftl_de_table.html
python3 -c "import requests, json; base='https://www.fencingtimelive.com/tableaus/scores/BA660C4B8C3949DAB4250EA99848E00E/15C08869F21543279512948F0398C58F'; trees=json.loads(requests.get(base+'/trees', timeout=15).text); tree=trees[0]; guid=tree.get('guid'); num_tables=tree.get('numTables',4); table_html=requests.get(f'{base}/trees/{guid}/tables/0/{num_tables}', timeout=15).text; open('/tmp/ftl_de_table.html','w').write(table_html); print('wrote /tmp/ftl_de_table.html', 'len=', len(table_html))"
```

```bash
# Optional: dump a snippet of the table HTML to /tmp/ftl_de_table_snip.txt for sharing
python3 -c "html=open('/tmp/ftl_de_table.html').read(); open('/tmp/ftl_de_table_snip.txt','w').write(html[:4000]); print('wrote /tmp/ftl_de_table_snip.txt')"
```
