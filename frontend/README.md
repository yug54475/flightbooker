# Concierge frontend

React + Vite member experience for the Travel Disruption Concierge.

## Prerequisites

The frontend calls the Go API only. Before starting it, make sure these services
are running:

1. Infrastructure from `backend/`: `docker-compose up -d`
2. Database migrations
3. Go API: `go run cmd/api/main.go`
4. Go worker in a separate terminal: `go run cmd/worker/main.go`
5. Python agent service from `AI_agent/` on port `8001`

`docker-compose up -d` starts infrastructure only; it does not start the API,
worker, or Python agent.

## Configuration

Copy `.env.example` to `.env` if the API is not available at the default URL:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Do not include a trailing slash.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

## Demo accounts

All seeded accounts use password `demo1234`.

| Member | Email | Scenario |
|---|---|---|
| Amir Khan | `amir@example.com` | Premium, already disrupted |
| Sara Patel | `sara@example.com` | Mid-tier, active trip |
| Jordan Lee | `jordan@example.com` | Entry, active trip |

Use the clearly marked **Demo · Simulate disruption** control on a scheduled
flight to exercise the live worker and agent flow.
