# Setup

Club start list + PDF. Regional/national names come from USA Fencing. Search uses the AskFRED API.

## Once

```bash
cd ~/Dev/fencer-schedules
uv sync --extra dev --python 3.12
```

AskFRED token lives in gitignored `.env` as `ASKFRED_API_TOKEN`. Do not paste it in chat. Club name is `config.yaml`.

## Run

```bash
./run.sh
```

Opens http://127.0.0.1:8765 on this machine.

Phone on the LAN: say so first; that needs `--host 0.0.0.0` and is not the default.

## Tests

```bash
uv run pytest tests/ -q
```
