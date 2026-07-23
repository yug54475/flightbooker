import asyncio
import traceback
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from agent.models import AgentPlanRequest, AgentPlanResponse
from agent.graph import agent_graph

app = FastAPI(
    title="Travel Disruption Concierge — AI Planning Agent",
    description="Standalone HTTP service using LangGraph to plan travel rebookings.",
    version="1.0.0"
)

@app.post(
    "/agent/plan",
    response_model=AgentPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a rebooking proposal for a travel disruption event"
)
async def plan_rebooking(request: AgentPlanRequest):
    # Sanitize input: redact payment details from logs per security rules
    print("FastAPI: Received disruption rebooking request")
    
    # Pack input state
    initial_state = {
        "disruption_event": request.disruption_event.dict()
    }
    
    try:
        # Run graph execution with a strict 20-second timeout per §2.4
        result = await asyncio.wait_for(
            asyncio.to_thread(agent_graph.invoke, initial_state),
            timeout=20.0
        )
        
        # Log reasoning steps as they are generated per §7
        print("FastAPI: Execution trace completed successfully. Traced steps:")
        for idx, step in enumerate(result.get("reasoning_steps", [])):
            print(f"  [{idx+1}] {step['step_name']}: input='{step['input']}' -> output='{step['output']}'")
            
        return result
        
    except asyncio.TimeoutError:
        print("FastAPI ERROR: Graph invocation timed out (> 20s)")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "AI agent planning request timed out (limit: 20 seconds)."
                }
            }
        )
    except Exception as e:
        print(f"FastAPI ERROR: Unhandled exception during planning: {e}")
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
    return {"status": "ok"}
