# Deployment Guide: Fencer Schedules

**Target Platform:** Hetzner Cloud (VPS) + Coolify (PaaS)
**Database:** PostgreSQL (Managed by Coolify)
**Domain Provider:** Namecheap

---

## 1. Prerequisites (Local Repo)

Ensure your repository has the following "Cloud Ready" files (already added):

-   **`Procfile`**: Tells the server how to start the app.
    ```text
    web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    ```
-   **`requirements.txt`**: Lists Python libraries (must include `psycopg2-binary`).
-   **`app/database.py`**: Configured to read `DATABASE_URL` environment variable.
-   **`/health` endpoint**: Added to `app/main.py` for health checks.

---

## 2. Server Setup (Hetzner)

1.  **Create Server:** Buy a standard Linux VPS (e.g., CPX11, Ubuntu/Debian).
2.  **Install Coolify:** SSH into the server and run:
    ```bash
    curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
    ```
3.  **Access Dashboard:** Visit `http://<YOUR_SERVER_IP>:8000`.

---

## 3. Coolify Configuration

### A. Create Project
1.  **Add Project:** "Fencing Apps" -> **+ New** -> **Public Repository**.
2.  **Repo:** `Remco28/fencer-schedules` (Branch: `main`).
3.  **Build Pack:** Nixpacks (Auto-detected).

### B. Add Database
1.  **+ New Resource** -> **Database** -> **PostgreSQL**.
2.  **Copy URL:** Copy the internal connection string (`postgresql://...`).

### C. Configure App Environment
Go to **Environment Variables** in your app settings and add:

| Key | Value | Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://user:pass@db:5432/...` | Paste from step B |
| `SECRET_KEY` | `(random string)` | For session security |
| `FTL_TIMEOUT` | `15` | Seconds to wait for FTL |

### D. Health Check (Critical)
To prevent "No available server" errors:
1.  Go to **Health Checks**.
2.  Set **Health Check Path** to: `/health`
3.  Set **Port** to: `8000`

### E. Domains
1.  Set **Domains** to: `https://fencerschedules.mydomain.com`
2.  (Coolify handles SSL automatically via Let's Encrypt).

---

## 4. DNS Setup (Namecheap)

1.  **A Record:** Host `*` -> Value `<YOUR_SERVER_IP>` (Wildcard)
2.  **A Record:** Host `@` -> Value `<YOUR_SERVER_IP>` (Root)

---

## 5. Updates & Maintenance

-   **Manual Update:** Click "Deploy" in Coolify UI.
-   **Auto Update:** Configure Webhooks in Coolify + GitHub Settings -> Webhooks.
-   **Logs:** View build/runtime logs in the Coolify dashboard if errors occur.
