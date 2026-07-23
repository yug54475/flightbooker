# Travel Disruption Concierge

An intelligent agent that detects travel disruptions and autonomously rebooks flights, rearranges hotel stays, and notifies card members.

## Project Structure

```
flightbooker/
├── backend/          # Go backend (API + Worker + Mock APIs)
├── AI agent/         # Python/LangGraph AI planning agent
└── frontend/         # React frontend
```

## Quick Start (Backend)

```bash
cd backend

# 1. Start infrastructure
docker-compose up -d

# 2. Install migrate CLI, then run migrations
migrate -path migrations -database "postgres://flightbooker:flightbooker@localhost:5432/flightbooker?sslmode=disable" up

# 3. Start API server (port 8000)
go run cmd/api/main.go

# 4. Start worker (separate terminal, port 8000)
go run cmd/worker/main.go
```

## Seed Users (password: `demo1234`)

| Name | Email | Card Tier |
|---|---|---|
| Amir Khan | amir@example.com | premium |
| Sara Patel | sara@example.com | mid |
| Jordan Lee | jordan@example.com | entry |

## Ports

| Service | Port |
|---|---|
| Backend API | 8000 |
| AI Agent | 8001 |
| Frontend | 5173 |
| Postgres | 5432 |
| Redis | 6379 |
| LocalStack (SQS) | 4566 |
