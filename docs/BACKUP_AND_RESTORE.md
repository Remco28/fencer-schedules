# Backup & Restore Guide

Since we are hosting on a self-managed VPS (Hetzner), we are responsible for our own data.

## Strategy A: Automated Cloud Backups (Recommended / Free)
Use Coolify's built-in backup system with Cloudflare R2 (which has a generous free tier).

1.  **Cloudflare R2 Setup:**
    *   Create a bucket named `fencer-backups`.
    *   Generate S3 API Tokens (Access Key ID, Secret Access Key).
    *   Endpoint URL: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

2.  **Coolify Setup:**
    *   **Settings** -> **S3 Storages** -> Add R2 credentials.
    *   **Project** -> **Database** -> **Scheduled Backups**.
    *   Set Schedule: `0 3 * * *` (3 AM daily).
    *   Select the S3 storage you just added.

## Strategy B: Manual Local Backup
Run this from your **local computer** to pull a database dump.

1.  **Find Container ID:**
    *   SSH into server: `ssh root@<SERVER_IP>`
    *   Run `docker ps | grep postgres` to find the container ID.

2.  **Execute Dump:**
    ```bash
    ssh root@<SERVER_IP> "docker exec -t <CONTAINER_ID> pg_dump -U postgres -d postgres" > fencer_backup_$(date +%F).sql
    ```
    *(Note: Replace `postgres` with the specific DB user/name found in your Coolify connection string if different)*

## Strategy C: Server Snapshots (Paid)
Enable Hetzner Backups in the Hetzner Cloud Console.
*   **Cost:** ~20% of server price (~€1/mo).
*   **Recovery:** Restores the entire machine state exactly as it was.

---

## Disaster Recovery (Restoring)

### Scenario: The Server Died Completely
1.  **Provision:** Buy a new Hetzner VPS.
2.  **Install:** Run the Coolify install script.
3.  **Restore Code:** Connect GitHub and deploy the `fencer-schedules` repo.
4.  **Restore Data:**
    *   **If using Strategy A:** Connect S3 in Coolify, select the backup, click Restore.
    *   **If using Strategy B:**
        1.  SSH into new server.
        2.  Find new DB container ID.
        3.  Upload dump: `scp backup.sql root@<IP>:backup.sql`
        4.  Import: `docker exec -i <NEW_ID> psql -U postgres -d postgres < backup.sql`
