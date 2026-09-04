# Setup

Club start list + PDF. Regional/national names come from USA Fencing. Search uses the AskFRED API.

## Once

```bash
cd ~/Projects/fencer-schedules
uv sync --extra dev --python 3.12
```

Secrets live in gitignored `.env`:

- `ASKFRED_API_TOKEN` — catalog + events
- `ASKFRED_EMAIL` / `ASKFRED_PASSWORD` — local tournament names (logged-in prereg page)
- `AGENTMAIL_API_KEY` / `AGENTMAIL_INBOX` — registrant-watcher emails (same inbox as other AgentMail jobs on this machine)

Do not paste secrets in chat. Club name is `config.yaml`.

Alert recipients are **not** in `.env`. Default is `frankcng@gmail.com`. Change them in the app: gear → Settings. Comma-separated for more than one person.

## Run locally

```bash
./run.sh
```

Listens on http://0.0.0.0:8765 (this machine and Tailscale).

Phone on the tailnet: `http://100.64.238.100:8765` or `http://frank-hp-elitedesk-800-g5-desktop-mini.taild9032.ts.net:8765`.

## Run as a service (this machine)

```bash
sudo cp deploy/fencer-schedules.service /etc/systemd/system/fencer-schedules.service
sudo cp deploy/fencer-schedules-monitor.service /etc/systemd/system/fencer-schedules-monitor.service
sudo cp deploy/fencer-schedules-monitor.timer /etc/systemd/system/fencer-schedules-monitor.timer
sudo systemctl daemon-reload
sudo systemctl enable --now fencer-schedules.service
sudo systemctl enable --now fencer-schedules-monitor.timer
```

The web app restarts on crash and on boot. The watcher runs at 09:00 and 21:00 America/New_York.

Manual one-shot:

```bash
uv run python -m fencer_schedules.monitor --once
uv run python -m fencer_schedules.monitor --dry-run
```

`--dry-run` prints any digest it *would* send and does not email or write `last_seen`.

## Tests

```bash
uv run pytest tests/ -q
```
