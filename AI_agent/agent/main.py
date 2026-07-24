import asyncio
import traceback
import uuid
from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agent.models import AgentPlanRequest, AgentPlanResponse
from agent.graph import agent_graph
from agent.config import (
    cancelled_disruption_ids, 
    CancellationToken
)

app = FastAPI(
    title="Travel Disruption Concierge — AI Planning Agent",
    description="Standalone HTTP service using LangGraph to plan travel rebookings.",
    version="1.0.0"
)


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
# HTTP Endpoint Router (§4.4 / §4.5)
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
    
    # Initialize CancellationToken and run Graph execution
    token = CancellationToken()
    initial_state = {
        "disruption_event": body.disruption_event.model_dump(),
        "cancellation_token": token
    }
    
    try:
        # Run graph execution with a strict 20-second timeout per §4.2
        result = await asyncio.wait_for(
            asyncio.to_thread(agent_graph.invoke, initial_state),
            timeout=20.0
        )
        
        # Log reasoning steps as they are generated per §4.5 / §7
        print(f"[Correlation-ID: {correlation_id}] FastAPI: Execution trace completed successfully. Traced steps:")
        for idx, step in enumerate(result.get("reasoning_steps", [])):
            print(f"  [{idx+1}] {step['step_name']}: input='{step['input']}' -> output='{step['output']}'")
            
        return result
        
    except asyncio.TimeoutError:
        print(f"[Correlation-ID: {correlation_id}] FastAPI ERROR: Graph invocation timed out (> 20s) for disruption {disruption_id}")
        token.is_cancelled = True
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
        print(f"[Correlation-ID: {correlation_id}] FastAPI ERROR: Unhandled exception during plan: {e}")
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
    """Health check endpoint per §12.5 requirements."""
    return {"status": "ok"}
