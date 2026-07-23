import psycopg2
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.config import DATABASE_URL
from agent.amadeus_client import search_flight_alternatives, search_hotel_alternatives
from agent.mock_booking_client import book_flight
from agent.confidence import compute_confidence_score

# Alternate airport mappings for nearby search routing (§4.3)
NEARBY_AIRPORTS = {
    "JFK": ["LGA", "EWR"],
    "LGA": ["JFK", "EWR"],
    "EWR": ["JFK", "LGA"],
    "LHR": ["LGW", "LCY", "STN"],
    "LGW": ["LHR", "LCY", "STN"],
    "SFO": ["OAK", "SJC"],
    "OAK": ["SFO", "SJC"],
    "SJC": ["SFO", "OAK"],
    "LAX": ["SNA", "BUR", "ONT"],
    "CDG": ["ORY"],
    "ORY": ["CDG"]
}

def get_current_timestamp_z() -> str:
    """Returns ISO 8601 string with Z suffix to the second."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# =========================================================
# LangGraph Nodes
# =========================================================

def parse_disruption_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Pull disruption parameters and query PostgreSQL for the user policy."""
    event = state["disruption_event"]
    flight_seg = event["flight_segment"]
    user = event["user"]
    
    # Defaults per §2/§7
    max_price_delta = 150.00
    allow_cabin_downgrade = False
    max_hotel_price_delta = 100.00
    
    # Fetch customer custom policy from Postgres
    user_id = user["id"]
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT max_price_delta, allow_cabin_downgrade, max_hotel_price_delta FROM user_policies WHERE user_id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            max_price_delta = float(row[0])
            allow_cabin_downgrade = bool(row[1])
            max_hotel_price_delta = float(row[2])
            print(f"Loaded customized policy for user {user_id}: max_price_delta={max_price_delta}, allow_cabin_downgrade={allow_cabin_downgrade}")
    except Exception as e:
        print(f"Postgres connection / policy query failed for user {user_id}, falling back to defaults. Error: {e}")

    # Parse segment dates to departure date
    dep_time_str = flight_seg["departure_time"]
    dep_date = dep_time_str.split("T")[0] if "T" in dep_time_str else dep_time_str
    
    return {
        "origin": flight_seg["origin"],
        "destination": flight_seg["destination"],
        "departure_date": dep_date,
        "cabin_class": flight_seg["cabin_class"],
        "loyalty_program": user.get("loyalty_program"),
        "original_price": float(flight_seg["original_price"]),
        "original_arrival_time": flight_seg["arrival_time"],
        
        "user_id": user_id,
        "card_tier": user["card_tier"],
        "card_token": user["card_token"],
        "user_name": user.get("name", "Amir Khan"),
        
        "max_price_delta": max_price_delta,
        "allow_cabin_downgrade": allow_cabin_downgrade,
        "max_hotel_price_delta": max_hotel_price_delta,
        
        "search_mode": "same_airport",
        "flight_offers": [],
        "evaluated_candidates": [],
        "best_candidate": None,
        "confidence_score": 0.0,
        "proposed_flight_segment": None,
        "proposed_hotel_booking": None,
        "reasoning_steps": []
    }

def search_alternatives_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Search for alternatives at same airport."""
    print(f"LangGraph: Searching flights {state['origin']}->{state['destination']} on {state['departure_date']}")
    
    offers = search_flight_alternatives(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        cabin_class=state["cabin_class"]
    )
    
    step = {
        "step_name": "search_alternatives",
        "input": f"{state['origin']}-{state['destination']}, {state['departure_date']}, {state['cabin_class']}",
        "output": f"{len(offers)} options found",
        "timestamp": get_current_timestamp_z()
    }
    
    return {
        "flight_offers": offers,
        "reasoning_steps": state["reasoning_steps"] + [step]
    }

def evaluate_candidates_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Compute confidence scores for all retrieved offers, sort and rank them."""
    print(f"LangGraph: Evaluating {len(state['flight_offers'])} candidates")
    evaluated = []
    
    for offer in state["flight_offers"]:
        # Parse flight segment data from the Amadeus offer structure
        try:
            itinerary = offer["itineraries"][0]
            segment = itinerary["segments"][0]
            
            carrier = segment["carrierCode"]
            flight_num = f"{carrier}{segment['number']}"
            dep_time = segment["departure"]["at"]
            if not dep_time.endswith("Z"):
                dep_time += "Z"
            arr_time = segment["arrival"]["at"]
            if not arr_time.endswith("Z"):
                arr_time += "Z"
                
            orig = segment["departure"]["iataCode"]
            dest = segment["arrival"]["iataCode"]
            
            new_price = float(offer["price"]["total"])
            
            # Try to extract actual cabin class from travelerPricings or default to searched cabin class
            new_cabin = state["cabin_class"]
            try:
                traveler_pricings = offer.get("travelerPricings", [])
                if traveler_pricings:
                    fare_details = traveler_pricings[0].get("fareDetailsBySegment", [])
                    if fare_details:
                        cabin = fare_details[0].get("cabin")
                        if cabin:
                            new_cabin = cabin.lower()
            except Exception as cabin_err:
                print(f"Error extracting cabin class: {cabin_err}")
            
            score = compute_confidence_score(
                new_price=new_price,
                original_price=state["original_price"],
                max_price_delta=state["max_price_delta"],
                new_cabin=new_cabin,
                original_cabin=state["cabin_class"],
                allow_cabin_downgrade=state["allow_cabin_downgrade"],
                carrier=carrier,
                loyalty_program=state["loyalty_program"],
                new_arrival_time_str=arr_time,
                original_arrival_time_str=state["original_arrival_time"]
            )
            
            candidate_segment = {
                "flight_number": flight_num,
                "origin": orig,
                "destination": dest,
                "departure_time": dep_time,
                "arrival_time": arr_time,
                "cabin_class": new_cabin,
                "original_price": new_price,
                "booking_reference": None
            }
            
            evaluated.append({
                "offer_raw": offer,
                "segment_flat": candidate_segment,
                "score": score
            })
        except Exception as e:
            print(f"Failed to parse candidate offer: {e}")
            
    # Sort candidates descending by score
    evaluated.sort(key=lambda x: x["score"], reverse=True)
    
    # Write evaluation reasoning steps
    new_steps = []
    if evaluated:
        top_cand = evaluated[0]["segment_flat"]
        top_score = evaluated[0]["score"]
        
        # Add a trace for cabin check
        cabin_step = {
            "step_name": "evaluate_cabin_match",
            "input": top_cand["flight_number"],
            "output": f"{top_cand['flight_number']} preserves {top_cand['cabin_class']} class",
            "timestamp": get_current_timestamp_z()
        }
        
        # Add a trace for confidence computation
        p_delta = top_cand["original_price"] - state["original_price"]
        p_delta_sign = "+" if p_delta >= 0 else ""
        p_delta_str = f"{p_delta_sign}${int(p_delta)}"
        
        arrival_dt = datetime.fromisoformat(top_cand["arrival_time"][:-1])
        orig_arrival_dt = datetime.fromisoformat(state["original_arrival_time"][:-1])
        arr_delta_hours = abs((arrival_dt - orig_arrival_dt).total_seconds()) / 3600.0
        
        input_summary = f"price_delta={p_delta_str}, cabin_match=1, loyalty_match=1, arrival_delta={int(arr_delta_hours)}h"
        conf_step = {
            "step_name": "compute_confidence",
            "input": input_summary,
            "output": f"{top_score:.2f}",
            "timestamp": get_current_timestamp_z()
        }
        new_steps = [cabin_step, conf_step]
        
    return {
        "evaluated_candidates": evaluated,
        "reasoning_steps": state["reasoning_steps"] + new_steps
    }

def widen_search_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Widen search parameters to nearby alternate airports."""
    print("LangGraph: No high-confidence candidates found. Widening search to nearby airports...")
    orig = state["origin"]
    dest = state["destination"]
    
    alt_origins = NEARBY_AIRPORTS.get(orig, [])
    alt_destinations = NEARBY_AIRPORTS.get(dest, [])
    
    # Formulate pairs to search
    search_pairs = []
    for alt_orig in [orig] + alt_origins:
        for alt_dest in [dest] + alt_destinations:
            if alt_orig == orig and alt_dest == dest:
                continue
            search_pairs.append((alt_orig, alt_dest))
            
    all_new_offers = list(state["flight_offers"]) # Keep previous offers
    
    for alt_o, alt_d in search_pairs[:3]: # Cap search pairs to keep execution quick and under 20s
        print(f"LangGraph: Searching nearby alternate pair {alt_o}->{alt_d}")
        offers = search_flight_alternatives(
            origin=alt_o,
            destination=alt_d,
            departure_date=state["departure_date"],
            cabin_class=state["cabin_class"]
        )
        all_new_offers.extend(offers)
        
    step = {
        "step_name": "widen_search",
        "input": f"Widen search beyond same-airport",
        "output": f"Expanded inventory pool to {len(all_new_offers)} total candidates",
        "timestamp": get_current_timestamp_z()
    }
    
    return {
        "flight_offers": all_new_offers,
        "search_mode": "nearby_airport",
        "reasoning_steps": state["reasoning_steps"] + [step]
    }

def decide_and_maybe_book_node(state: AgentState) -> Dict[str, Any]:
    """Node 5: Select winner and perform booking (or retry other candidates if booking fails with 422)."""
    candidates = state["evaluated_candidates"]
    
    if not candidates:
        print("LangGraph: No viable candidates available.")
        step = {
            "step_name": "no_alternative_found",
            "input": "n/a",
            "output": "No viable rebooking options in Amadeus inventory for this route/date/cabin.",
            "timestamp": get_current_timestamp_z()
        }
        return {
            "best_candidate": None,
            "confidence_score": 0.0,
            "proposed_flight_segment": None,
            "reasoning_steps": state["reasoning_steps"] + [step]
        }
        
    # Find winning candidate
    best_cand = None
    winning_seg = None
    winning_score = 0.0
    reasoning_traces = list(state["reasoning_steps"])
    
    for cand in candidates:
        cand_score = cand["score"]
        cand_offer = cand["offer_raw"]
        cand_seg = cand["segment_flat"]
        
        if cand_score > 0.9:
            # Auto-approval path: book immediately!
            print(f"LangGraph: Candidate {cand_seg['flight_number']} qualifies for Auto-Approval (score={cand_score}). Hitting mock booking API...")
            booking_ref = book_flight(
                flight_offer=cand_offer,
                traveler_name=state["user_name"],
                card_token=state["card_token"]
            )
            
            if booking_ref:
                # Booking succeeded! Set references and establish as the winner
                best_cand = cand
                cand_seg["booking_reference"] = booking_ref
                winning_seg = cand_seg
                winning_score = cand_score
                break
            else:
                # Booking failed (seat sold out). Append failure trace and retry next-best option
                print(f"LangGraph: Seat sold out on {cand_seg['flight_number']}. Retrying next-best option...")
                retry_trace = {
                    "step_name": "booking_failed_retry",
                    "input": cand_seg["flight_number"],
                    "output": f"Booking {cand_seg['flight_number']} returned 422 (sold out). Attempting next candidate.",
                    "timestamp": get_current_timestamp_z()
                }
                reasoning_traces.append(retry_trace)
        else:
            # Pending approval path: do NOT book, return offer as-is
            print(f"LangGraph: Candidate {cand_seg['flight_number']} scores below auto-approval threshold (score={cand_score}).")
            best_cand = cand
            winning_seg = cand_seg
            winning_score = cand_score
            break
            
    if not winning_seg:
        # All bookings failed or no option was viable
        print("LangGraph: All high-confidence rebooking candidate attempts returned sold-out status.")
        step = {
            "step_name": "no_alternative_found",
            "input": "n/a",
            "output": "All candidate bookings failed due to sold-out seat inventory.",
            "timestamp": get_current_timestamp_z()
        }
        return {
            "best_candidate": None,
            "confidence_score": 0.0,
            "proposed_flight_segment": None,
            "reasoning_steps": reasoning_traces + [step]
        }
        
    return {
        "best_candidate": best_cand,
        "confidence_score": winning_score,
        "proposed_flight_segment": winning_seg,
        "reasoning_steps": reasoning_traces
    }

def assemble_response_node(state: AgentState) -> Dict[str, Any]:
    """Node 6: Finalizes formatting of state elements to return the finalized HTTP JSON payload."""
    return {
        "proposed_flight_segment": state["proposed_flight_segment"],
        "proposed_hotel_booking": state["proposed_hotel_booking"],
        "confidence_score": state["confidence_score"],
        "reasoning_steps": state["reasoning_steps"]
    }

# =========================================================
# StateGraph State Machine Construction
# =========================================================

workflow = StateGraph(AgentState)

# Register Nodes
workflow.add_node("parse_disruption", parse_disruption_node)
workflow.add_node("search_alternatives", search_alternatives_node)
workflow.add_node("evaluate_candidates", evaluate_candidates_node)
workflow.add_node("widen_search", widen_search_node)
workflow.add_node("decide_and_maybe_book", decide_and_maybe_book_node)
workflow.add_node("assemble_response", assemble_response_node)

# Connect edges
workflow.set_entry_point("parse_disruption")
workflow.add_edge("parse_disruption", "search_alternatives")
workflow.add_edge("search_alternatives", "evaluate_candidates")

def should_widen_search(state: AgentState) -> str:
    """Conditional Edge routing deciding whether to widen search based on scores."""
    best_score = 0.0
    if state.get("evaluated_candidates"):
        best_score = state["evaluated_candidates"][0].get("score", 0.0)
        
    # Check if alternate airport routing is available for origin/destination
    orig_has_alt = state.get("origin") in NEARBY_AIRPORTS
    dest_has_alt = state.get("destination") in NEARBY_AIRPORTS
    has_alternate_airports = orig_has_alt or dest_has_alt
    
    if state.get("search_mode") == "same_airport" and has_alternate_airports:
        if not state.get("evaluated_candidates") or best_score <= 0.8:
            return "widen_search"
            
    return "decide_and_maybe_book"

workflow.add_conditional_edges(
    "evaluate_candidates",
    should_widen_search,
    {
        "widen_search": "widen_search",
        "decide_and_maybe_book": "decide_and_maybe_book"
    }
)

workflow.add_edge("widen_search", "evaluate_candidates")
workflow.add_edge("decide_and_maybe_book", "assemble_response")
workflow.add_edge("assemble_response", END)

# Compile
agent_graph = workflow.compile()
