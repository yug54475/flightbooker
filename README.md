# Travel Disruption Concierge

An intelligent AI agent that detects travel disruptions and autonomously rebooks flights, rearranges hotel stays, and notifies card members — all in real time.

## The Problem & Solution
**The Problem:** When mass flight disruptions occur (e.g., severe weather), thousands of stranded travelers flood call centers simultaneously. This leads to hours-long hold times, high anxiety, and a terrible customer experience.

**The Solution:** The Travel Disruption Concierge is a proactive, event-driven AI system. Instead of forcing passengers to call in, the system instantly detects flight cancellations via webhook, evaluates alternative flights using an AI agent constrained by the user's specific policy/tier, and autonomously rebooks them. Passengers receive an instant notification with their new itinerary before they even realize they were stranded.

## Project Structure

```text
flightbooker/
├── backend/          # Go API Server + Background Worker + SQS
├── AI_agent/         # Python/LangGraph AI planning agent
└── frontend/         # React + Vite frontend
```

## Prerequisites

Make sure you have the following installed:

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for PostgreSQL, Redis, LocalStack)
- [Go 1.21+](https://go.dev/dl/)
- [Python 3.10+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/) (includes npm)

## Setup & Run

You will need **4 separate terminal windows** to run all services.

---

### Step 1: Clone & Configure Environment

```bash
git clone https://github.com/yug54475/flightbooker.git
cd flightbooker

# Windows (PowerShell)
copy backend\.env.example backend\.env
copy AI_agent\.env.example AI_agent\.env

# Mac / Linux (Bash)
cp backend/.env.example backend/.env
cp AI_agent/.env.example AI_agent/.env
```

The default `.env` values work out of the box for local development. No changes needed.

---

### Step 2: Start Infrastructure (Terminal 1)

Start PostgreSQL, Redis, and LocalStack (SQS):

```powershell
cd backend
docker-compose up -d
```

Wait a few seconds for containers to be healthy, then run database migrations.

**For Windows (PowerShell):**
```powershell
Get-Content migrations\000001_initial_schema.up.sql | docker exec -i flightbooker-postgres psql -U flightbooker -d flightbooker
Get-Content migrations\000002_seed_data.up.sql | docker exec -i flightbooker-postgres psql -U flightbooker -d flightbooker
```

**For Mac / Linux (Bash):**
```bash
cat migrations/000001_initial_schema.up.sql | docker exec -i flightbooker-postgres psql -U flightbooker -d flightbooker
cat migrations/000002_seed_data.up.sql | docker exec -i flightbooker-postgres psql -U flightbooker -d flightbooker
```

---

### Step 3: Start the AI Agent (Terminal 2)

```bash
cd AI_agent

# Create virtual environment
python -m venv venv

# Activate it (Windows)
.\venv\Scripts\activate
# Activate it (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the agent service (Windows PowerShell)
$env:PYTHONPATH="." ; uvicorn agent.main:app --host 127.0.0.1 --port 8001 --reload

# Start the agent service (Mac/Linux Bash)
PYTHONPATH="." uvicorn agent.main:app --host 127.0.0.1 --port 8001 --reload
```

---

### Step 4: Start the Go Backend (Terminals 3 & 4)

**Terminal 3** — API Server:
```powershell
cd backend
go run ./cmd/api
```

**Terminal 4** — Background Worker:
```powershell
cd backend
go run ./cmd/worker
```

---

### Step 5: Start the Frontend (Terminal 5)

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Demo Users

All passwords are `demo1234`.

| Name | Email | Card Tier |
|---|---|---|
| Amir Khan | amir@example.com | premium |
| Sara Patel | sara@example.com | mid |
| Jordan Lee | jordan@example.com | entry |

## How to Test

1. Log in with any demo user.
2. On the **Trips** page, click **"DEMO · Simulate disruption"** on any flight.
3. The AI agent will evaluate alternatives, score confidence, and either auto-book or request your approval.
4. Check the **Notifications** page for real-time updates.

## Resetting the Demo

If you have already simulated disruptions and want to start fresh to present the clean demo from the beginning, you no longer need to touch the database!

1. Log in with your demo user.
2. At the top right of the **Trips** page, click the **"↺ Reset Demo"** button.
3. This instantly wipes out the AI's rebooking history and resets all flights for that user back to their original `scheduled` status.

## Ports

| Service | Port | Description |
|---|---|---|
| Frontend | 5173 | React web app |
| Backend API | 8000 | Go REST API |
| AI Agent | 8001 | Python LangGraph service |
| PostgreSQL | 5433 | Database (mapped from container 5432) |
| Redis | 6379 | Cache |
| LocalStack | 4566 | Local AWS SQS |
