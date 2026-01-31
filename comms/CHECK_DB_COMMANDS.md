# Coolify Debug Commands (FTL Round Discovery)

## Event page round discovery (pools + DE)

```bash
python3 - <<'PY'
import re
import requests

url = "https://www.fencingtimelive.com/events/view/632701A80E1840AB98D7AA92D796203F"
html = requests.get(url, timeout=15).text
open("/tmp/ftl_event.html", "w").write(html)
print("wrote /tmp/ftl_event.html", "len=", len(html))

links = re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S)

def clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())

pool = [(h, clean(t)) for h, t in links if "/pools/" in h or "pools" in h.lower()]
de = [(h, clean(t)) for h, t in links if "/tableaus/scores/" in h]

out = ["POOL LINKS:"]
out += [f"{h} | {t}" for h, t in pool]
out.append("")
out.append("DE LINKS:")
out += [f"{h} | {t}" for h, t in de]

open("/tmp/ftl_event_rounds.txt", "w").write("\n".join(out))
print("wrote /tmp/ftl_event_rounds.txt")
PY
```

```bash
python3 - <<'PY'
import re

html = open("/tmp/ftl_event.html").read()
pools = sorted(set(re.findall(r"/pools/scores/([A-Fa-f0-9]{32})/([A-Fa-f0-9]{32})", html)))
des = sorted(set(re.findall(r"/tableaus/scores/([A-Fa-f0-9]{32})/([A-Fa-f0-9]{32})", html)))

out = ["POOL EVENT/ROUND IDS:"]
out += [f"{e} / {r}" for e, r in pools]
out.append("")
out.append("DE EVENT/ROUND IDS:")
out += [f"{e} / {r}" for e, r in des]

open("/tmp/ftl_event_round_ids.txt", "w").write("\n".join(out))
print("wrote /tmp/ftl_event_round_ids.txt")
PY
```

## Pools page round discovery (flight tabs often appear here)

```bash
python3 - <<'PY'
import re
import requests

url = "https://www.fencingtimelive.com/pools/scores/632701A80E1840AB98D7AA92D796203F/271FAAD3D1E14CD68C28D064F3B81CF5"
html = requests.get(url, timeout=15).text
open("/tmp/ftl_pools_page.html", "w").write(html)
print("wrote /tmp/ftl_pools_page.html", "len=", len(html))

links = re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S)

def clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())

pool = [(h, clean(t)) for h, t in links if "/pools/" in h]
out = ["POOLS PAGE LINKS:"]
out += [f"{h} | {t}" for h, t in pool]

open("/tmp/ftl_pools_page_rounds.txt", "w").write("\n".join(out))
print("wrote /tmp/ftl_pools_page_rounds.txt")
PY
```

```bash
python3 - <<'PY'
import re

html = open("/tmp/ftl_pools_page.html").read()
pools = sorted(set(re.findall(r"/pools/scores/([A-Fa-f0-9]{32})/([A-Fa-f0-9]{32})", html)))

out = ["POOLS PAGE EVENT/ROUND IDS:"]
out += [f"{e} / {r}" for e, r in pools]

open("/tmp/ftl_pools_page_round_ids.txt", "w").write("\n".join(out))
print("wrote /tmp/ftl_pools_page_round_ids.txt")
PY
```

## Tableau JS trees discovery (check for multiple trees/tableaus)

```bash
python3 - <<'PY'
import json
import requests

base = "https://www.fencingtimelive.com/tableaus/scores/632701A80E1840AB98D7AA92D796203F/0DF4467DCA3D40BA97D4E45C07E097D1"
trees = json.loads(requests.get(base + "/trees", timeout=15).text)
open("/tmp/ftl_de_trees.json", "w").write(json.dumps(trees, indent=2))
print("wrote /tmp/ftl_de_trees.json", "count=", len(trees))

lines = []
for t in trees:
    lines.append(
        f"guid={t.get('guid')} title={t.get('title')} numTables={t.get('numTables')} "
        f"firstIncompleteTable={t.get('firstIncompleteTable')}"
    )
open("/tmp/ftl_de_trees_summary.txt", "w").write("\\n".join(lines))
print("wrote /tmp/ftl_de_trees_summary.txt")
PY
```

```bash
python3 - <<'PY'
import json

trees = json.load(open("/tmp/ftl_de_trees.json"))
guids = [t.get("guid") for t in trees if t.get("guid")]
open("/tmp/ftl_de_tree_guids.txt", "w").write("\\n".join(guids))
print("wrote /tmp/ftl_de_tree_guids.txt")
PY
```
