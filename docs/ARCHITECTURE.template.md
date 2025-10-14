# Architecture Overview (Template)

This template provides a fast, 2–3 minute overview of a system. Keep it short, focus on how components relate, and avoid implementation detail. Replace bracketed placeholders like [PROJECT_NAME] and [SERVICE_A] with your project’s terms.

## System Components

### Core Services
- **[SERVICE_A]** (`[path/to/service_a]`) – Short purpose one-liner.
- **[SERVICE_B]** (`[path/to/service_b]`) – Short purpose one-liner.

### Supporting Services (as applicable)
- **Database** – e.g., PostgreSQL/SQLite; primary data store for [DOMAIN].
- **Cache** – e.g., Redis, for hot paths only (optional).
- **Message Broker** – e.g., RabbitMQ/Kafka for async events (optional).

### Process Architecture
```
[Service A Process]      [Service B Process]
       |                        |
       +----- Shared Data ------+
       |                        |
       +----- External APIs ----+
```
Note: Prefer separate processes for clear scaling and fault isolation.

## Data Flow Examples

### Example: Creating a [DOMAIN_OBJECT]
```
Client → [Service A] → validate → persist → notify [Service B]/users (if applicable)
```

### Example: Updating a [DOMAIN_OBJECT]
```
Client → [Service B] → check auth/ownership → update → emit event → [Service A] reacts
```

Keep 1–3 concrete flows here that capture the “essence” of the system.

## Key Abstractions

- **Entities/Aggregates**: [Entity_A], [Entity_B]; relationships and lifecycle (open → closed, etc.).
- **Boundaries**: API surface, UI/WebApp, background jobs/workers.
- **Events (optional)**: [event.name] – who emits, who consumes, why.

## Authentication & Authorization (Optional)

- User identity: e.g., JWT/session/cookie or platform-provided (Telegram/Slack/etc.).
- Trust boundaries: public client vs server-only secrets; never expose server tokens to clients.
- Roles/permissions (if any): [admin], [member], etc.

## Configuration

- Central settings module/file: `[path/to/config]` with env-driven configuration.
- Typical envs: `LOG_LEVEL`, `[SERVICE]_URL`, `DATABASE_URL`/`DB_PATH`, `ALLOWED_ORIGINS`, `ADMIN_USER_IDS`.
- Prefer explicit, documented envs over ad-hoc flags.

## Integration Points

- **Database**: single source of truth for [DOMAIN]; write patterns and read models (brief).
- **External APIs**: list by name; note retry/backoff, timeouts, and error handling stance.
- **Messaging**: topics/queues (if used); idempotency keys and at-least-once handling.

## Runtime & Operations Notes

- Processes: [Service A] and [Service B] run separately; communicate via DB/HTTP/queue.
- Defaults: ports (e.g., 8080), bind addresses (e.g., 127.0.0.1 in dev), reverse proxy in prod.
- Concurrency: keep transactions short; connection-per-thread/process; WAL or proper isolation for multi-process DB access.
- Security: input validation; signed tokens/sessions; secret storage via env/secret manager; treat notification failures as best-effort unless critical.
- Observability: include identifiers (e.g., `user_id`, `resource_id`, `action`) in INFO logs; provide `GET /healthz`; optionally metrics (requests/sec, error rate).
- Schema evolution: prefer additive migrations; for breaking changes, ship one-off scripts and document the rollout.

## Development Guidelines

### For Developers
- Read this file first to understand relationships.
- Follow existing patterns in code (handlers, services, modules) before adding new ones.
- Keep flows cohesive; avoid leaking implementation detail across boundaries.
- Add small, focused tests around the code you change.

### For Architects/Tech Leads
- Keep this doc accurate when adding/removing major components.
- Focus on interactions (who talks to whom, and why), not how.
- Update the data flow examples when user journeys change materially.
- Document new integration points (APIs, tables, topics) in one line each.

## How NOT to Use This File

- Don’t duplicate code-level docs or function signatures here.
- Don’t include long code examples; link to files instead.
- Don’t turn this into a deployment guide; keep ops in separate docs.
- Don’t let it bloat; if it takes >3 pages, trim it.

## Red Flags

- If readers need this to understand basic function calls → code needs better naming.
- If this explains “how to implement” instead of “what connects to what” → too detailed.
- If every refactor requires updating this file → coupling is too tight.
- If newcomers spend >5 minutes reading this → it’s too verbose.

## Related Docs (Placeholders)

- ROADMAP: `[docs/ROADMAP.md]`
- Task specs: `[comms/tasks/YYYY-MM-DD-*.md]`
- Ops/Deployment: `[docs/deployment.md]`
- ADRs (optional): `[docs/adr/0001-something.md]`

---

Use this as your starting point for each new project. Keep it short, current, and focused on the architecture’s shape and interactions.

