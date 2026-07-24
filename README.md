# Travel Disruption Concierge

An intelligent agent that detects travel disruptions and autonomously rebooks flights, rearranges hotel stays, and notifies card members.

## Project Structure

```text
flightbooker/
├── backend/          # Go API Server + Background Worker + SQS
├── AI_agent/         # Python/LangGraph AI planning agent
└── frontend/         # React + Vite frontend
```

## Running the Application (Windows)

You will need to open **4 separate terminal windows** to run all the microservices concurrently.

### 1. Database and Infrastructure
First, start the required background services (PostgreSQL, Redis, LocalStack SQS):
```powershell
cd backend
docker-compose up -d
```
*Note: Postgres is mapped to port `5433` locally to avoid conflicts with existing Windows Postgres installations.*

### 2. Python AI Agent
In your second terminal, start the Python AI Agent:
```powershell
cd AI_agent
# Activate your virtual environment if you have one setup
# .\venv\Scripts\activate
$env:PYTHONPATH="."
uvicorn agent.main:app --host 127.0.0.1 --port 8001 --reload
```

### 3. Go Backend (API & Worker)
In your third terminal, start the API server:
```powershell
cd backend
go run ./cmd/api
```
Open a new terminal tab (your fourth) and start the background worker:
```powershell
cd backend
go run ./cmd/worker
```

### 4. React Frontend
In your final terminal, start the UI:
```powershell
cd frontend
npm install
npm run dev
```

## Seed Users (password: `demo1234`)

| Name | Email | Card Tier |
|---|---|---|
| Amir Khan | amir@example.com | premium |
| Sara Patel | sara@example.com | mid |
| Jordan Lee | jordan@example.com | entry |

## Ports & Architecture

| Service | Port | Description |
|---|---|---|
| Backend API | 8000 | Main backend entrypoint |
| AI Agent | 8001 | Python LangGraph service |
| Frontend | 5173 | React web app |
| Postgres | 5433 | Local mapping for the database |
| Redis | 6379 | In-memory cache |
| LocalStack | 4566 | Local SQS queues |
