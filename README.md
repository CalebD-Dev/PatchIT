# PatchIT

PatchIT is a support-desk application for tracking IT requests, technician assignments, troubleshooting notes, and common fixes. It uses a React + TypeScript frontend, a FastAPI REST API, and PostgreSQL.

## Features

- Create, search, filter, assign, and update support tickets.
- Track requesters, technicians, priorities, status, affected devices, and 24-hour target dates.
- Keep an activity log and append troubleshooting notes to each ticket.
- See open, high-priority, overdue, weekly resolved, and average resolution-time metrics calculated from ticket timestamps.
- Search a small starter knowledge base for common Windows, printer, network, and account issues.
- Start with fictional demo users, tickets, and articles.

## Run locally

Requirements: Python 3.11+, Node.js 20+, npm, and PostgreSQL 17+ (installed locally or started with Docker Desktop).

1. Choose one PostgreSQL option. To install PostgreSQL locally on Windows:

   ```powershell
   winget install --id PostgreSQL.PostgreSQL.17 --exact
   ```

   Keep the default port `5432` and set an administrator password in the installer. Stack Builder is optional.

   Or, if you have Docker Desktop, start the included development database:

   ```powershell
   docker compose up -d db
   ```

2. Configure the database connection in a `.env` file in the repository root:

   ```powershell
   Copy-Item .env.example .env
   ```

   If you installed PostgreSQL locally, create an application user and database. Open the PostgreSQL prompt:

   ```powershell
   & 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -U postgres -d postgres
   ```

   At the `postgres=#` prompt, enter:

   ```sql
   CREATE ROLE patchit LOGIN;
   CREATE DATABASE patchit OWNER patchit;
   \password patchit
   \q
   ```

   The `\password` command prompts for the new application password without displaying it. Set the connection string in `.env` using this PowerShell snippet; it prompts securely and URL-encodes special characters for you:

   ```powershell
   $securePassword = Read-Host "PostgreSQL patchit password" -AsSecureString
   $pointer = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
   try {
       $password = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
       $encoded = [System.Uri]::EscapeDataString($password)
       $envFile = Get-Content .env -Raw
       $envFile = $envFile.Replace("REPLACE_WITH_URL_ENCODED_PASSWORD", $encoded)
       [System.IO.File]::WriteAllText((Resolve-Path .env), $envFile, [System.Text.UTF8Encoding]::new($false))
   } finally {
       [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
       $securePassword.Dispose()
       $password = $null
       $encoded = $null
   }
   ```

   With Docker's included database, skip the role/database creation and password steps; its `patchit`/`patchit` credentials are already configured for local development. Keep `.env` private: it is ignored by Git and should not be committed.

3. Install and start the API from the `backend` directory:

   ```powershell
   cd backend
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

   The API creates fictional demo records on its first start. API documentation is available at `http://localhost:8000/docs`.

4. In a second terminal, install and start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

   Open the URL printed by Vite, typically `http://localhost:5173`.

## View the database in pgAdmin

The Windows PostgreSQL installer includes pgAdmin 4. Open it from the Start menu. If prompted to register a server, use these settings:

- **Name:** PatchIT local
- **Host:** `localhost`
- **Port:** `5432`
- **Maintenance database:** `patchit`
- **Username:** `patchit`
- **Password:** the application password used in `.env` (for Docker, `patchit`)

After connecting, expand **Servers → PatchIT local → Databases → patchit → Schemas → public → Tables**. To inspect ticket records, right-click **tickets** and select **View/Edit Data → All Rows**. To run a SQL query, right-click the `patchit` database, choose **Query Tool**, and run:

```sql
SELECT id, title, status, priority, category, created_at
FROM tickets
ORDER BY created_at DESC;
```

Run `alembic upgrade head` to create the tables. The demo users, tickets, and articles are inserted when the API starts for the first time.

The demo interface starts as the seeded administrator. Switching the profile changes the demo identity: requesters see only their own tickets; technicians see their assigned tickets and the unassigned or escalated team queue; administrators can see all tickets. New tickets are always unassigned and enter the technician queue. Technicians must claim an available ticket before editing it or adding internal notes. Only the assigned technician can escalate an active ticket back to the shared queue, where another technician can claim it. Ticket assignment and escalation are recorded in the activity history. Apply database changes with `alembic upgrade head` after updating the app. This is a demo-only identity header, not authentication; users can spoof it. Do not expose the API publicly until real authentication and server-verified roles are implemented.

## Tests and production build

Run backend tests from `backend`:

```powershell
pytest
```

Build the frontend from `frontend`:

```powershell
npm run build
```

## API outline

- `GET /api/dashboard`
- `GET /api/tickets` (supports `search`, `status`, `priority`, and `category`)
- `POST /api/tickets`
- `GET /api/tickets/{ticket_id}`
- `PATCH /api/tickets/{ticket_id}?actor_id=...`
- `POST /api/tickets/{ticket_id}/comments`
- `GET /api/users`
- `GET /api/knowledge?search=...`

Ticket changes and troubleshooting notes are recorded in the ticket history. The starter SLA target is 24 hours from ticket creation; overdue counts are computed from active tickets' target timestamps.
