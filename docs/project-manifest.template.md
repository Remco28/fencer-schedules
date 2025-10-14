# Project Manifest Template

**Purpose:** This file acts as a "map" for an AI coding agent. It provides a stable set of pointers to critical project documentation and context, allowing the AI to quickly orient itself at the start of a new session.

**How to Use:**
1. Copy this template to the root of your project and rename it to `project-manifest.md`.
2. Customize the file paths to match your project's structure.
3. Use this manifest as the foundation for your initial "bootstrap prompt" when starting a session with an AI.


---

## 1. Core Identity (Stable)
*These files define the project's high-level architecture, goals, and the roles of the participants. They should change infrequently.*

- **Architecture:** `docs/ARCHITECTURE.md`
- **Roadmap/Goals:** `docs/ROADMAP.md`

## 2. Dynamic State (Volatile)
*These files and directories reflect the current status, recent work, and active tasks. The AI should check these to understand what's happening right now.*

- **Activity Log:** `comms/log.md`
- **Active Task Directory:** `comms/tasks/` (Note: specs for completed tasks are typically moved to an `archive/` sub-directory).


## 3. Code & Config (Entrypoints)
*These are the primary technical entrypoints for understanding the application's structure, dependencies, and configuration.*

- **Main Application:** `src/main.py` or `app/main.js`
- **Dependencies:** `requirements.txt` or `package.json`
- **Environment Configuration:** `.env.example`
- **Database Schema:** `src/models.py` or `prisma/schema.prisma`
- **API Routes:** `src/routes/` or `app/api/`
