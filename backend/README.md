# Travel Disruption Concierge — Backend

Go backend for the Travel Disruption Concierge. Implements the API layer, SQS worker, mock airline/hotel APIs, and all supporting services per `implementation_spec_v3.md`.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| **Go** | 1.21+ | [go.dev/dl](https://go.dev/dl/) |
| **Docker + Docker Compose** | Any recent | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **golang-migrate CLI** | v4+ | `go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest` |

## Quick Start

```bash
# 1. Clone and enter the repo
cd backend

# 2. Copy environment file
cp .env.example .env
# (defaults work out of the box — no changes needed for local dev)

# 3. Start Postgres + LocalStack (SQS)
docker-compose up -d

# 4. Wait for Postgres to be healthy (~10s)
docker-compose ps  # check "healthy" status

# 5. Run migrations + seed data
migrate -path migrations -database "postgres://flightbooker:flightbooker@localhost:5432/flightbooker?sslmode=disable" up

# 6. Start the API server (terminal 1)
go run ./cmd/api

# 7. Start the worker (terminal 2)
go run ./cmd/worker

# 8. Start the AI agent service (terminal 3, port 8001)
# (see the agent teammate's README)
```

## Verify It's Working

```bash
# Health check
curl http://localhost:8000/health
# → {"status":"ok"}

# Login with seeded user
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"amir@example.com","password":"demo1234"}'
# → {"token":"eyJ...","user_id":"..."}
```

## Ports

| Service | Port |
|---|---|
| Backend API + Mock APIs | 8000 |
| AI Agent (separate repo) | 8001 |
| Frontend (separate repo) | 5173 |
| Postgres | 5432 |
| LocalStack (SQS) | 4566 |

## Project Structure

```
cmd/
  api/          → HTTP server (go run ./cmd/api)
  worker/       → SQS consumer + approval timeout ticker (go run ./cmd/worker)
internal/
  auth/         → JWT middleware, ownership checks
  booking/      → Shared booking execution logic
  db/           → Postgres connection pool
  handlers/     → HTTP handlers (auth, itineraries, approvals, etc.)
  mockapi/      → Mock airline/hotel booking APIs
  models/       → Request/response structs
  queue/        → SQS publish/consume
  agentclient/  → HTTP client for AI agent
  insurance/    → Insurance eligibility logic
  lounge/       → Lounge access checks
  validation/   → Request validation helpers
migrations/     → Versioned SQL schema + seed data
```

## Resetting the Database

```bash
# Drop everything and re-migrate
migrate -path migrations -database "postgres://flightbooker:flightbooker@localhost:5432/flightbooker?sslmode=disable" down -all
migrate -path migrations -database "postgres://flightbooker:flightbooker@localhost:5432/flightbooker?sslmode=disable" up
```

## Stopping Everything

```bash
docker-compose down        # stop containers, keep data
docker-compose down -v     # stop containers AND wipe Postgres data
```
