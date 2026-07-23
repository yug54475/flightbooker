import psycopg2
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.config import DATABASE_URL, cancelled_disruption_ids, get_db_conn
from agent.amadeus_client import search_flight_alternatives, search_hotel_alternatives
from agent.mock_booking_client import book_flight, book_hotel
from agent.confidence import compute_confidence_score

# Timezone offsets for July 2026 (daylight saving time offsets)
AIRPORT_UTC_OFFSETS = {
    "JFK": -4,
    "LGA": -4,
    "EWR": -4,
    "LHR": 1,
    "LGW": 1,
    "LCY": 1,
    "STN": 1,
    "CDG": 2,
    "ORY": 2,
    "LAX": -7,
    "SNA": -7,
    "BUR": -7,
    "ONT": -7,
    "SFO": -7,
    "OAK": -7,
    "SJC": -7,
    "NRT": 9
}

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

# Airport IATA code to Amadeus major City Code mapping for Hotel Searches
AIRPORT_TO_CITY = {
    "LHR": "LON",
    "LGW": "LON",
    "LCY": "LON",
    "STN": "LON",
    "CDG": "PAR",
    "ORY": "PAR",
    "JFK": "NYC",
    "LGA": "NYC",
    "EWR": "NYC",
    "LAX": "LAX",
    "SFO": "SFO",
    "NRT": "TYO"
}

def normalize_to_utc_iso(time_str: str, airport_code: str) -> str:
    """
    Parses a local time string and converts it to UTC based on the airport's offset,
    returning an ISO 8601 UTC string (with Z suffix).
    """
    if "Z" in time_str or "+" in time_str or ("-" in time_str and time_str.count("-") > 2):
        return time_str
        
    try:
        dt = datetime.fromisoformat(time_str)
        offset = AIRPORT_UTC_OFFSETS.get(airport_code, 0)
        dt_utc = dt - timedelta(hours=offset)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        print(f"Error converting local time {time_str} at {airport_code} to UTC: {e}")
        if not time_str.endswith("Z"):
            return time_str + "Z"
        return time_str

def get_current_timestamp_z() -> str:
    """Returns ISO 8601 string with Z suffix to the second."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# =========================================================
# LangGraph Nodes
# =========================================================

def parse_disruption_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Pull disruption parameters, load user policy and any existing hotel stays."""
    event = state["disruption_event"]
    flight_seg = event["flight_segment"]
    user = event["user"]
    
    # Defaults per §2/§7
    max_price_delta = 150.00
    allow_cabin_downgrade = False
    max_hotel_price_delta = 100.00
    
    # Fetch customer custom policy from Postgres using Connection Pool
    user_id = user["id"]
    try:
        with get_db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT max_price_delta, allow_cabin_downgrade, max_hotel_price_delta FROM user_policies WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
            cur.close()
            if row:
                max_price_delta = float(row[0])
                allow_cabin_downgrade = bool(row[1])
                max_hotel_price_delta = float(row[2])
                print(f"Loaded customized policy for user {user_id}: max_price_delta={max_price_delta}, allow_cabin_downgrade={allow_cabin_downgrade}")
    except psycopg2.OperationalError as e:
        print(f"Postgres Connection Error: Cannot connect to database. Using default limits for user {user_id}. Details: {e}")
    except psycopg2.ProgrammingError as e:
        print(f"Postgres Schema Error: Query failed (possible missing table/column 'user_policies'). Using default limits for user {user_id}. Details: {e}")
    except psycopg2.Error as e:
        print(f"Postgres Database Error: Execution failure for user {user_id}. Details: {e}")
    except Exception as e:
        print(f"Postgres unexpected failure for user {user_id}, falling back to defaults. Error: {e}")

    # Query for any active scheduled hotel booking on this itinerary (Issue 2) using Connection Pool
    existing_hotel = None
    try:
        with get_db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT hb.id, hb.hotel_name, hb.check_in, hb.check_out, hb.status, hb.booking_reference
                   FROM hotel_bookings hb
                   JOIN itineraries i ON hb.itinerary_id = i.id
                   JOIN flight_segments fs ON fs.itinerary_id = i.id
                   WHERE fs.id = %s AND hb.status = 'scheduled'""",
                (flight_seg["id"],)
            )
            hotel_row = cur.fetchone()
            cur.close()
            if hotel_row:
                existing_hotel = {
                    "id": hotel_row[0],
                    "hotel_name": hotel_row[1],
                    "check_in": hotel_row[2].isoformat() if isinstance(hotel_row[2], datetime) else hotel_row[2],
                    "check_out": hotel_row[3].isoformat() if isinstance(hotel_row[3], datetime) else hotel_row[3],
                    "status": hotel_row[4],
                    "booking_reference": hotel_row[5]
                }
                print(f"Loaded existing hotel booking: '{existing_hotel['hotel_name']}'")
    except Exception as e:
        print(f"Postgres hotel query failed: {e}")

    # Parse segment dates to local departure date at the origin airport (Issue 3)
    dep_time_str = flight_seg["departure_time"]
    try:
        utc_str = dep_time_str[:-1] if dep_time_str.endswith("Z") else dep_time_str
        dt_utc = datetime.fromisoformat(utc_str)
        offset = AIRPORT_UTC_OFFSETS.get(flight_seg["origin"], 0)
        dt_local = dt_utc + timedelta(hours=offset)
        dep_date = dt_local.strftime("%Y-%m-%d")
        print(f"Parsed local departure date at {flight_seg['origin']}: UTC={dep_time_str} -> Local={dt_local.isoformat()} -> Date={dep_date}")
    except Exception as e:
        print(f"Error parsing local departure date from {dep_time_str}: {e}")
        dep_date = dep_time_str.split("T")[0] if "T" in dep_time_str else dep_time_str
    
    # Assert traveler name exists; throw loud Error if missing to prevent "Amir Khan" defaults (Issue 1)
    user_name = user.get("name")
    if not user_name:
         raise ValueError(f"CRITICAL ERROR: 'name' field is missing from user payload under disruption event {event['id']}")
         
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
        "user_name": user_name,
        
        "max_price_delta": max_price_delta,
        "allow_cabin_downgrade": allow_cabin_downgrade,
        "max_hotel_price_delta": max_hotel_price_delta,
        
        "existing_hotel": existing_hotel,
        
        "search_mode": "same_airport",
        "flight_offers": [],
        "hotel_offers": [],
        "evaluated_candidates": [],
        "best_candidate": None,
        "confidence_score": 0.0,
        "proposed_flight_segment": None,
        "proposed_hotel_booking": None,
        "reasoning_steps": []
    }

def search_alternatives_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Search flight alternatives. Query hotel alternatives if there's an active hotel stay (Issue 2)."""
    print(f"LangGraph: Searching flights {state['origin']}->{state['destination']} on {state['departure_date']}")
    
    offers = search_flight_alternatives(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        cabin_class=state["cabin_class"]
    )
    
    # Identify search source for transparent tracing (Issue 4)
    has_real_flights = any(o.get("search_source") == "amadeus_real" for o in offers)
    source_tag_flights = "Amadeus real API" if has_real_flights else "synthetic fallback"
    
    step_flights = {
        "step_name": "search_alternatives",
        "input": f"{state['origin']}-{state['destination']}, {state['departure_date']}, {state['cabin_class']}",
        "output": f"{len(offers)} options found ({source_tag_flights})",
        "timestamp": get_current_timestamp_z()
    }
    
    # Query hotel alternatives if there is an existing hotel booking associated with the trip (Issue 2)
    hotel_offers = []
    reasoning_steps = state["reasoning_steps"] + [step_flights]
    
    if state.get("existing_hotel"):
        dest_airport = state["destination"]
        city_code = AIRPORT_TO_CITY.get(dest_airport, dest_airport)
        
        # Format check-in/out dates from existing hotel
        h_check_in = state["existing_hotel"]["check_in"].split("T")[0]
        h_check_out = state["existing_hotel"]["check_out"].split("T")[0]
        
        print(f"LangGraph: Triggering real Hotel Search for city {city_code} from {h_check_in} to {h_check_out}")
        hotel_offers = search_hotel_alternatives(city_code, h_check_in, h_check_out)
        
        # Transparent tracing tag for hotels
        has_real_hotels = any(ho.get("search_source") == "amadeus_real" for ho in hotel_offers)
        source_tag_hotels = "Amadeus real API" if has_real_hotels else "synthetic fallback"
        
        step_hotels = {
            "step_name": "search_hotel_alternatives",
            "input": f"City={city_code}, Dates={h_check_in} to {h_check_out}",
            "output": f"{len(hotel_offers)} hotels found ({source_tag_hotels})",
            "timestamp": get_current_timestamp_z()
        }
        reasoning_steps.append(step_hotels)
        
    return {
        "flight_offers": offers,
        "hotel_offers": hotel_offers,
        "reasoning_steps": reasoning_steps
    }

def evaluate_candidates_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Rank candidates, handle connecting flight legs correctly (Issue 1), evaluate hotels (Issue 2)."""
    print(f"LangGraph: Evaluating {len(state['flight_offers'])} flight candidates")
    evaluated = []
    
    for offer in state["flight_offers"]:
        try:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            
            # Robust extraction of origin (first leg) and destination (last leg) for connections (Issue 1)
            first_leg = segments[0]
            last_leg = segments[-1]
            
            orig = first_leg["departure"]["iataCode"]
            dest = last_leg["arrival"]["iataCode"]
            
            # Formulate flight numbers across legs (e.g. 'BA112 / BA304' for connections)
            flight_num = " / ".join(f"{s['carrierCode']}{s['number']}" for s in segments)
            carrier = first_leg["carrierCode"]
            
            dep_time_raw = first_leg["departure"]["at"]
            arr_time_raw = last_leg["arrival"]["at"]
            
            # Normalize to timezone-aware UTC timestamps
            dep_time = normalize_to_utc_iso(dep_time_raw, orig)
            arr_time = normalize_to_utc_iso(arr_time_raw, dest)
            
            new_price = float(offer["price"]["total"])
            
            # Parse traveler pricing structure for actual cabin class
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
            
            # Get score and actual sub-scores dictionary from confidence engine (Issue 2)
            score, sub_scores = compute_confidence_score(
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
                "score": score,
                "sub_scores": sub_scores
            })
        except Exception as e:
            print(f"Failed to parse candidate offer: {e}")
            
    # Sort candidates descending by score
    evaluated.sort(key=lambda x: x["score"], reverse=True)
    
    # Generate transparent reasoning steps
    new_steps = []
    if evaluated:
        top_cand = evaluated[0]["segment_flat"]
        top_score = evaluated[0]["score"]
        top_sub_scores = evaluated[0]["sub_scores"]
        
        # Word cabin description dynamically based on actual same_cabin score (Issue 2)
        if top_sub_scores["same_cabin"] == 1.0:
            cabin_desc = f"{top_cand['flight_number']} preserves {top_cand['cabin_class']} class"
        elif top_sub_scores["same_cabin"] == 0.5:
            cabin_desc = f"{top_cand['flight_number']} downgrades to allowed {top_cand['cabin_class']} class"
        else:
            cabin_desc = f"{top_cand['flight_number']} downgrades to unauthorized {top_cand['cabin_class']} class"
            
        cabin_step = {
            "step_name": f"evaluate_cabin_match ({state['search_mode']})", # Clear path labels (Issue 3)
            "input": top_cand["flight_number"],
            "output": cabin_desc,
            "timestamp": get_current_timestamp_z()
        }
        
        p_delta = top_cand["original_price"] - state["original_price"]
        p_delta_sign = "+" if p_delta >= 0 else ""
        p_delta_str = f"{p_delta_sign}${int(p_delta)}"
        
        arrival_dt = datetime.fromisoformat(top_cand["arrival_time"][:-1])
        orig_arrival_dt = datetime.fromisoformat(state["original_arrival_time"][:-1])
        arr_delta_hours = abs((arrival_dt - orig_arrival_dt).total_seconds()) / 3600.0
        
        # Populate input summary dynamically from computed sub-scores, not mock literals (Issue 2)
        input_summary = (
            f"price_delta={p_delta_str} (score={top_sub_scores['price_delta_ok']}), "
            f"cabin_match={top_sub_scores['same_cabin']}, "
            f"loyalty_match={top_sub_scores['loyalty_program_match']}, "
            f"arrival_delta={int(arr_delta_hours)}h"
        )
        conf_step = {
            "step_name": f"compute_confidence ({state['search_mode']})", # Clear path labels (Issue 3)
            "input": input_summary,
            "output": f"{top_score:.2f}",
            "timestamp": get_current_timestamp_z()
        }
        new_steps = [cabin_step, conf_step]
        
    # Evaluate hotel candidate matching original hotel name (Issue 2)
    proposed_hotel = None
    if state.get("existing_hotel") and state.get("hotel_offers"):
        orig_hotel_name = state["existing_hotel"]["hotel_name"].lower()
        matched_hotel = None
        
        # Try finding a matching hotel offer based on name
        for h_off in state["hotel_offers"]:
            if h_off["hotel_name"].lower() in orig_hotel_name or orig_hotel_name in h_off["hotel_name"].lower():
                matched_hotel = h_off
                break
                
        # Fall back to first offer if no match
        if not matched_hotel:
            matched_hotel = state["hotel_offers"][0]
            
        proposed_hotel = {
            "id": matched_hotel["hotel_id"],
            "hotel_name": matched_hotel["hotel_name"],
            "check_in": matched_hotel["check_in"],
            "check_out": matched_hotel["check_out"],
            "status": "changed",
            "booking_reference": None
        }
        print(f"LangGraph: Proposed hotel rebooking: '{proposed_hotel['hotel_name']}'")
        
    return {
        "evaluated_candidates": evaluated,
        "proposed_hotel_booking": proposed_hotel,
        "reasoning_steps": state["reasoning_steps"] + new_steps
    }

def widen_search_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Widen search parameters to nearby alternate airports. Uses thread-level concurrency to respect SLA (Issue 2)."""
    print("LangGraph: No high-confidence candidates found. Widening search to nearby airports...")
    orig = state["origin"]
    dest = state["destination"]
    
    alt_origins = NEARBY_AIRPORTS.get(orig, [])
    alt_destinations = NEARBY_AIRPORTS.get(dest, [])
    
    search_pairs = []
    for alt_orig in [orig] + alt_origins:
        for alt_dest in [dest] + alt_destinations:
            if alt_orig == orig and alt_dest == dest:
                continue
            search_pairs.append((alt_orig, alt_dest))
            
    all_new_offers = list(state["flight_offers"])
    
    # Execute searches in parallel to prevent sequential execution block exceeding the 20-second timeout (Issue 2)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(search_flight_alternatives, alt_o, alt_d, state["departure_date"], state["cabin_class"])
            for alt_o, alt_d in search_pairs[:3]
        ]
        for future in futures:
            try:
                # Limit the wait time of individual tasks to keep within budget safely
                offers = future.result(timeout=8.0)
                all_new_offers.extend(offers)
            except Exception as exc:
                print(f"Parallel search pair failed: {exc}")
        
    has_real_flights = any(o.get("search_source") == "amadeus_real" for o in all_new_offers)
    source_tag_flights = "Amadeus real API" if has_real_flights else "synthetic fallback"
    
    step = {
        "step_name": "widen_search",
        "input": "Widen search beyond same-airport",
        "output": f"Expanded inventory pool to {len(all_new_offers)} total candidates ({source_tag_flights})",
        "timestamp": get_current_timestamp_z()
    }
    
    return {
        "flight_offers": all_new_offers,
        "search_mode": "nearby_airport",
        "reasoning_steps": state["reasoning_steps"] + [step]
    }

def decide_and_maybe_book_node(state: AgentState) -> Dict[str, Any]:
    """Node 5: Select winner and perform booking. Distinguishes 422 vs network/5xx system errors (Issue 1)."""
    disruption_id = state["disruption_event"]["id"]
    candidates = state["evaluated_candidates"]
    
    # 1. Enforce proactive cancellation check before booking (Issue 5)
    if disruption_id in cancelled_disruption_ids:
        print(f"LangGraph WARNING: Disruption {disruption_id} previously TIMED OUT. Aborting any booking operations to prevent double-booking.")
        step = {
            "step_name": "booking_cancelled_timeout",
            "input": disruption_id,
            "output": f"Planning timed out globally. Proactively cancelled flight and hotel booking operations.",
            "timestamp": get_current_timestamp_z()
        }
        return {
            "best_candidate": None,
            "confidence_score": 0.0,
            "proposed_flight_segment": None,
            "proposed_hotel_booking": None,
            "reasoning_steps": state["reasoning_steps"] + [step]
        }
    
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
        
    best_cand = None
    winning_seg = None
    winning_score = 0.0
    reasoning_traces = list(state["reasoning_steps"])
    
    for cand in candidates:
        cand_score = cand["score"]
        cand_offer = cand["offer_raw"]
        cand_seg = cand["segment_flat"]
        
        if cand_score > 0.9:
            # Re-check cancellation status inside the loop (safeguarding against race conditions)
            if disruption_id in cancelled_disruption_ids:
                print("LangGraph WARNING: Disruption timed out during evaluation. Skipping booking.")
                break
                
            # Auto-approval path: book immediately!
            print(f"LangGraph: Candidate {cand_seg['flight_number']} qualifies for Auto-Approval (score={cand_score}). Hitting mock booking API...")
            
            # This call propagates requests.RequestException on network/system error (Issue 1)
            booking_ref, booking_status = book_flight(
                flight_offer=cand_offer,
                traveler_name=state["user_name"],
                card_token=state["card_token"]
            )
            
            if booking_status == "success":
                best_cand = cand
                cand_seg["booking_reference"] = booking_ref
                winning_seg = cand_seg
                winning_score = cand_score
                break
            else: # booking_status == "sold_out" (422)
                print(f"LangGraph: Seat sold out on {cand_seg['flight_number']}. Retrying next-best option...")
                retry_trace = {
                    "step_name": "booking_failed_retry",
                    "input": cand_seg["flight_number"],
                    "output": f"Booking {cand_seg['flight_number']} returned 422 (sold out). Attempting next candidate.",
                    "timestamp": get_current_timestamp_z()
                }
                reasoning_traces.append(retry_trace)
        else:
            # Pending approval path: do NOT book
            print(f"LangGraph: Candidate {cand_seg['flight_number']} scores below auto-approval threshold (score={cand_score}).")
            best_cand = cand
            winning_seg = cand_seg
            winning_score = cand_score
            break
            
    if not winning_seg:
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
        
    # Auto-book hotel stay if applicable (Issue 2)
    proposed_hotel = state.get("proposed_hotel_booking")
    if winning_score > 0.9 and proposed_hotel:
        if disruption_id not in cancelled_disruption_ids:
            print(f"LangGraph: Auto-approving hotel rebooking '{proposed_hotel['hotel_name']}'...")
            
            # This call propagates requests.RequestException on network/system error (Issue 1)
            hotel_ref, hotel_status = book_hotel(
                hotel_id=proposed_hotel["id"],
                hotel_name=proposed_hotel["hotel_name"],
                user_id=state["user_id"],
                check_in=proposed_hotel["check_in"],
                check_out=proposed_hotel["check_out"],
                card_token=state["card_token"]
            )
            if hotel_status == "success":
                proposed_hotel["booking_reference"] = hotel_ref
                step_hotel_book = {
                    "step_name": "hotel_rebooking_confirmed",
                    "input": proposed_hotel["hotel_name"],
                    "output": f"Successfully rebooked '{proposed_hotel['hotel_name']}' under reference {hotel_ref}",
                    "timestamp": get_current_timestamp_z()
                }
                reasoning_traces.append(step_hotel_book)
            else: # hotel_status == "sold_out" (422)
                print("LangGraph ERROR: Hotel auto-booking failed (422 - sold out).")
        else:
            print("LangGraph WARNING: Disruption timed out. Skipping hotel booking.")
            
    return {
        "best_candidate": best_cand,
        "confidence_score": winning_score,
        "proposed_flight_segment": winning_seg,
        "proposed_hotel_booking": proposed_hotel,
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
