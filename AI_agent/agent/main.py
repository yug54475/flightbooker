import asyncio
import traceback
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agent.models import AgentPlanRequest, AgentPlanResponse
from agent.graph import agent_graph
from agent.config import (
    cancelled_disruption_ids, 
    get_db_conn, 
    init_db_pool, 
    close_db_pool
)

# ==========================================
# Modern Lifespan Handler (FastAPI Standard)
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("FastAPI: Initializing database connection pools on startup...")
    init_db_pool()
    yield
    print("FastAPI: Releasing database connection pools on shutdown...")
    close_db_pool()

app = FastAPI(
    title="Travel Disruption Concierge — AI Planning Agent",
    description="Standalone HTTP service using LangGraph to plan travel rebookings.",
    version="1.0.0",
    lifespan=lifespan
)

# Global structures for thread/coroutine safety and request deduplication
completed_proposals_cache = {}
processing_locks = {}
cache_lock = asyncio.Lock()


# ==========================================
# Middleware: Correlation ID Tracing
# ==========================================

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

app.add_middleware(CorrelationIDMiddleware)


# ==========================================
# HTTP Endpoint Router
# ==========================================

@app.post(
    "/agent/plan",
    response_model=AgentPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a rebooking proposal for a travel disruption event"
)
async def plan_rebooking(request: Request, body: AgentPlanRequest):
    correlation_id = request.state.correlation_id
    disruption_id = body.disruption_event.id
    
    print(f"[Correlation-ID: {correlation_id}] FastAPI: Received disruption request for event {disruption_id}")
    
    # 1. Coordinate locking globally per disruption event ID
    async with cache_lock:
        if disruption_id not in processing_locks:
            processing_locks[disruption_id] = asyncio.Lock()
        disruption_lock = processing_locks[disruption_id]
        
    # 2. Synchronize processing to prevent concurrent duplicates
    async with disruption_lock:
        # Check if the proposal has already been processed and cached
        if disruption_id in completed_proposals_cache:
            print(f"[Correlation-ID: {correlation_id}] FastAPI: Returning cached proposal for disruption {disruption_id}")
            return completed_proposals_cache[disruption_id]
            
        print(f"[Correlation-ID: {correlation_id}] FastAPI: Processing planning for disruption {disruption_id}")
        
        # Pack input state using modern model_dump() (silencing Pydantic v2 warning)
        initial_state = {
            "disruption_event": body.disruption_event.model_dump()
        }
        
        try:
            # Run graph execution with a strict 20-second timeout per §2.4
            result = await asyncio.wait_for(
                asyncio.to_thread(agent_graph.invoke, initial_state),
                timeout=20.0
            )
            
            # Log reasoning steps as they are generated per §7
            print(f"[Correlation-ID: {correlation_id}] FastAPI: Execution trace completed successfully. Traced steps:")
            for idx, step in enumerate(result.get("reasoning_steps", [])):
                print(f"  [{idx+1}] {step['step_name']}: input='{step['input']}' -> output='{step['output']}'")
                
            # Cache the successful output
            completed_proposals_cache[disruption_id] = result
            return result
            
        except asyncio.TimeoutError:
            print(f"[Correlation-ID: {correlation_id}] FastAPI ERROR: Graph invocation timed out (> 20s) for disruption {disruption_id}")
            # Register in cancellation token list to prevent background thread booking (Issue 5)
            cancelled_disruption_ids.add(disruption_id)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": f"AI agent planning request timed out (limit: 20 seconds) for disruption {disruption_id}."
                    }
                }
            )
        except Exception as e:
            print(f"[Correlation-ID: {correlation_id}] FastAPI ERROR: Unhandled exception during planning for disruption {disruption_id}: {e}")
            traceback.print_exc()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": f"An unhandled error occurred in the planning agent: {str(e)}"
                    }
                }
            )

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Live database-reachability health check matching §12.5 requirements."""
    try:
        with get_db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.fetchone()
            cur.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        print(f"FastAPI ERROR: Health check failed - Database is unreachable: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "message": f"Database is unreachable: {str(e)}"
            }
        )
