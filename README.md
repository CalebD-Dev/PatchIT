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

1. Install PostgreSQL locally on Windows, if needed:

   ```powershell
   winget install --id PostgreSQL.PostgreSQL.17 --exact
   ```

   Keep the default port `5432` and set an administrator password in the installer. Stack Builder is optional.

   Alternatively, start the included Docker database:

   ```powershell
   docker compose up -d db
   ```

2. Copy `.env.example` to `.env` in the repository root. Create a dedicated application user and database with the PostgreSQL command-line client:

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

   `\password` prompts for the new application password without displaying it. Set `DATABASE_URL` in `.env` to `postgresql+psycopg://patchit:<url-encoded-password>@localhost:5432/patchit`. The `.env` file is ignored by Git; do not commit it. When using Docker's included database, its demo credentials are `patchit`/`patchit` and are intended only for local development.

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

The demo interface operates as the seeded administrator. Authentication and server-enforced role permissions are not yet enabled; do not expose this demo API publicly.

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
