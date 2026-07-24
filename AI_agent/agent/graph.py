import requests
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.config import cancelled_disruption_ids
from agent.amadeus_client import search_flight_alternatives, search_hotel_alternatives
from agent.mock_booking_client import book_flight, book_hotel
from agent.confidence import compute_confidence_score, parse_iso_time

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

# Alternate airport mappings for nearby search routing (§10 / §4.5)
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
    Parses an ISO 8601 timestamp string and normalizes it to UTC with Z suffix (§0).
    - If already Z-suffixed: returns as-is.
    - If explicit offset (e.g. +01:00, -04:00): parses and converts to UTC.
    - If naive (no offset): applies the airport's known UTC offset from AIRPORT_UTC_OFFSETS.
    """
    try:
        if time_str.endswith("Z"):
            return time_str

        # Parse the timestamp
        dt = datetime.fromisoformat(time_str)

        if dt.tzinfo is not None:
            # Explicit offset present — convert to UTC
            dt_utc = dt.astimezone(timezone.utc)
            return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Naive timestamp — apply airport offset to convert to UTC
        offset_hours = AIRPORT_UTC_OFFSETS.get(airport_code, 0)
        dt_utc = dt - timedelta(hours=offset_hours)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as e:
        print(f"Error converting time {time_str} at {airport_code} to UTC: {e}")
        if not time_str.endswith("Z"):
            return time_str + "Z"
        return time_str


def get_current_timestamp_z() -> str:
    """Returns ISO 8601 string with Z suffix to the second (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_candidate_trace_steps(
    winning_cand: Dict[str, Any],
    search_mode: str,
    original_price: float,
    original_arrival_time_str: str
) -> List[Dict[str, Any]]:
    """
    Builds the 'evaluate_cabin_match' / 'compute_confidence' reasoning steps from the
    candidate that ACTUALLY won (was booked, or is being proposed pending approval).
    """
    seg = winning_cand["segment_flat"]
    sub_scores = winning_cand["sub_scores"]
    score = winning_cand["score"]

    if sub_scores["same_cabin"] == 1.0:
        cabin_desc = f"{seg['flight_number']} preserves {seg['cabin_class']} class"
    elif sub_scores["same_cabin"] == 0.5:
        cabin_desc = f"{seg['flight_number']} downgrades to allowed {seg['cabin_class']} class"
    else:
        cabin_desc = f"{seg['flight_number']} downgrades to unauthorized {seg['cabin_class']} class"

    cabin_step = {
        "step_name": "evaluate_cabin_match",
        "input": seg["flight_number"],
        "output": cabin_desc,
        "timestamp": get_current_timestamp_z()
    }

    # Use Decimal for price delta arithmetic per §0 (never float-round money fields)
    p_delta = Decimal(str(seg["original_price"])) - Decimal(str(original_price))
    p_delta_sign = "+" if p_delta >= 0 else ""
    p_delta_str = f"{p_delta_sign}${p_delta:.2f}"

    arrival_dt = parse_iso_time(seg["arrival_time"])
    orig_arrival_dt = parse_iso_time(original_arrival_time_str)
    arr_delta_hours = abs((arrival_dt - orig_arrival_dt).total_seconds()) / 3600.0

    input_summary = (
        f"price_delta={p_delta_str}, "
        f"cabin_match={sub_scores['same_cabin']}, "
        f"loyalty_match={sub_scores['loyalty_program_match']}, "
        f"arrival_delta={int(arr_delta_hours)}h"
    )
    conf_step = {
        "step_name": "compute_confidence",
        "input": input_summary,
        "output": f"{score}",
        "timestamp": get_current_timestamp_z()
    }

    return [cabin_step, conf_step]


# =========================================================
# LangGraph Nodes
# =========================================================

def parse_disruption_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Pull disruption parameters and load member policy thresholds."""
    event = state["disruption_event"]
    flight_seg = event["flight_segment"]
    user = event["user"]

    # Member policy limits from user payload or defaults per §2/§7
    # Policy values arrive as Decimal from Pydantic model_dump(); keep as Decimal per §0
    max_price_delta = user.get("max_price_delta", Decimal("150.00"))
    allow_cabin_downgrade = bool(user.get("allow_cabin_downgrade", False))
    max_hotel_price_delta = user.get("max_hotel_price_delta", Decimal("100.00"))

    user_id = user["id"]

    # Parse segment dates to local departure date at origin airport
    dep_time_str = flight_seg["departure_time"]
    try:
        utc_str = dep_time_str[:-1] if dep_time_str.endswith("Z") else dep_time_str
        dt_utc = datetime.fromisoformat(utc_str)
        offset = AIRPORT_UTC_OFFSETS.get(flight_seg["origin"], 0)
        dt_local = dt_utc + timedelta(hours=offset)
        dep_date = dt_local.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error parsing local departure date from {dep_time_str}: {e}")
        dep_date = dep_time_str.split("T")[0] if "T" in dep_time_str else dep_time_str

    user_name = user.get("name")
    if not user_name or not user_name.strip():
        user_name = f"Traveler {user_id[:8]}"

    existing_hotel = event.get("existing_hotel")
    itinerary_id = event.get("itinerary_id")

    return {
        "origin": flight_seg["origin"],
        "destination": flight_seg["destination"],
        "departure_date": dep_date,
        "cabin_class": flight_seg["cabin_class"],
        "loyalty_program": user.get("loyalty_program"),
        "original_price": flight_seg["original_price"],  # Decimal from Pydantic model_dump()
        "original_arrival_time": flight_seg["arrival_time"],

        "user_id": user_id,
        "card_tier": user["card_tier"],
        "card_token": user["card_token"],
        "user_name": user_name,

        "max_price_delta": max_price_delta,
        "allow_cabin_downgrade": allow_cabin_downgrade,
        "max_hotel_price_delta": max_hotel_price_delta,

        "existing_hotel": existing_hotel,
        "itinerary_id": itinerary_id,
        "cancellation_token": state.get("cancellation_token"),

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
    """Node 2: Search flight alternatives via real Amadeus API (or fallback). Query hotel alternatives if active hotel stay exists."""
    print(f"LangGraph: Searching flights {state['origin']}->{state['destination']} on {state['departure_date']}")

    offers = search_flight_alternatives(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        cabin_class=state["cabin_class"]
    )

    has_real_flights = any(o.get("search_source") == "amadeus_real" for o in offers)
    source_tag_flights = "Amadeus real API" if has_real_flights else "synthetic fallback"

    step_flights = {
        "step_name": "search_alternatives",
        "input": f"{state['origin']}-{state['destination']}, {state['departure_date']}, {state['cabin_class']}",
        "output": f"{len(offers)} options found ({source_tag_flights})",
        "timestamp": get_current_timestamp_z()
    }

    hotel_offers = []
    reasoning_steps = state["reasoning_steps"] + [step_flights]

    if state.get("existing_hotel"):
        dest_airport = state["destination"]
        city_code = AIRPORT_TO_CITY.get(dest_airport, dest_airport)

        h_check_in = state["existing_hotel"]["check_in"].split("T")[0]
        h_check_out = state["existing_hotel"]["check_out"].split("T")[0]

        print(f"LangGraph: Triggering Hotel Search for city {city_code} from {h_check_in} to {h_check_out}")
        hotel_offers = search_hotel_alternatives(city_code, h_check_in, h_check_out)

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
    """
    Node 3: Rank flight candidates by confidence score and select hotel candidate.
    """
    print(f"LangGraph: Evaluating {len(state['flight_offers'])} flight candidates")
    evaluated = []

    for offer in state["flight_offers"]:
        try:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]

            first_leg = segments[0]
            last_leg = segments[-1]

            orig = first_leg["departure"]["iataCode"]
            dest = last_leg["arrival"]["iataCode"]

            flight_num = " / ".join(f"{s['carrierCode']}{s['number']}" for s in segments)
            carrier = first_leg["carrierCode"]

            dep_time_raw = first_leg["departure"]["at"]
            arr_time_raw = last_leg["arrival"]["at"]

            dep_time = normalize_to_utc_iso(dep_time_raw, orig)
            arr_time = normalize_to_utc_iso(arr_time_raw, dest)

            new_price = Decimal(offer["price"]["total"])  # §0: use Decimal for price fields

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

    # Sort candidates descending by confidence score
    evaluated.sort(key=lambda x: x["score"], reverse=True)

    new_steps = []
    if evaluated:
        top_cand = evaluated[0]["segment_flat"]
        top_score = evaluated[0]["score"]
        new_steps.append({
            "step_name": f"candidates_evaluated ({state['search_mode']})",
            "input": f"{len(evaluated)} candidates scored",
            "output": f"provisional leader {top_cand['flight_number']} at score {top_score:.2f} (subject to booking availability)",
            "timestamp": get_current_timestamp_z()
        })

    proposed_hotel = None
    if state.get("existing_hotel") and state.get("hotel_offers"):
        orig_hotel_name = state["existing_hotel"]["hotel_name"].lower()
        matched_hotel = None

        for h_off in state["hotel_offers"]:
            if h_off["hotel_name"].lower() in orig_hotel_name or orig_hotel_name in h_off["hotel_name"].lower():
                matched_hotel = h_off
                break

        if not matched_hotel:
            matched_hotel = state["hotel_offers"][0]

        proposed_hotel = {
            "id": matched_hotel.get("hotel_id"),
            "hotel_name": matched_hotel["hotel_name"],
            "check_in": matched_hotel["check_in"],
            "check_out": matched_hotel["check_out"],
            "status": "changed",
            "booking_reference": None
        }

    return {
        "evaluated_candidates": evaluated,
        "proposed_hotel_booking": proposed_hotel,
        "reasoning_steps": state["reasoning_steps"] + new_steps
    }


def widen_search_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Widen search parameters to nearby alternate airports."""
    # TODO(spec-gap): Lounge access check ownership (§10).
    # Section §10 specifies checkLoungeAccess(card_tier, new_airport_code) when rerouting to an alternate airport.
    # Open contract question: should this check be executed inside the agent or by the backend worker?
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

    search_pairs.sort(key=lambda p: (p[0] != orig, p[1] != dest))

    all_new_offers = list(state["flight_offers"])

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(search_flight_alternatives, alt_o, alt_d, state["departure_date"], state["cabin_class"])
            for alt_o, alt_d in search_pairs[:3]
        ]
        for future in futures:
            try:
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
    """Node 5: Select winning candidate and execute mock booking calls if score > 0.9."""
    disruption_id = state["disruption_event"]["id"]
    candidates = state["evaluated_candidates"]
    token = state.get("cancellation_token")

    if (token and token.is_cancelled) or disruption_id in cancelled_disruption_ids:
        print(f"LangGraph WARNING: Disruption {disruption_id} timed out. Aborting booking operations.")
        step = {
            "step_name": "booking_cancelled_timeout",
            "input": disruption_id,
            "output": "Planning timed out globally. Cancelled flight and hotel booking operations.",
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
            "proposed_hotel_booking": None,
            "reasoning_steps": state["reasoning_steps"] + [step]
        }

    best_cand = None
    winning_seg = None
    winning_score = 0.0
    reasoning_traces = list(state["reasoning_steps"])

    proposed_hotel = state.get("proposed_hotel_booking")

    for cand in candidates:
        cand_score = cand["score"]
        cand_offer = cand["offer_raw"]
        cand_seg = cand["segment_flat"]

        # Strict auto-approval threshold: score > 0.9 per §7
        auto_eligible = cand_score > 0.9

        if auto_eligible:
            if (token and token.is_cancelled) or disruption_id in cancelled_disruption_ids:
                print("LangGraph WARNING: Disruption timed out right before booking. Skipping flight booking.")
                reasoning_traces.append({
                    "step_name": "booking_cancelled_timeout",
                    "input": disruption_id,
                    "output": "Planning timed out globally just before booking. Cancelled booking attempt.",
                    "timestamp": get_current_timestamp_z()
                })
                break

            print(f"LangGraph: Candidate {cand_seg['flight_number']} qualifies for Auto-Approval (score={cand_score}). Hitting mock booking API...")

            try:
                booking_ref, booking_status = book_flight(
                    flight_offer=cand_offer,
                    traveler_name=state["user_name"],
                    card_token=state["card_token"],
                    disruption_id=disruption_id
                )

                if booking_status == "success":
                    best_cand = cand
                    cand_seg["booking_reference"] = booking_ref
                    winning_seg = cand_seg
                    winning_score = cand_score
                    reasoning_traces.extend(_build_candidate_trace_steps(
                        cand, state["search_mode"], state["original_price"], state["original_arrival_time"]
                    ))
                    break
                else:  # booking_status == "sold_out" (422)
                    print(f"LangGraph: Seat sold out on {cand_seg['flight_number']}. Retrying next-best option...")
                    retry_trace = {
                        "step_name": "booking_failed_retry",
                        "input": cand_seg["flight_number"],
                        "output": f"Booking {cand_seg['flight_number']} returned 422 (sold out). Attempting next candidate.",
                        "timestamp": get_current_timestamp_z()
                    }
                    reasoning_traces.append(retry_trace)
            except requests.RequestException as e:
                print(f"LangGraph ERROR: Flight booking failed with network exception: {e}")
                step = {
                    "step_name": "booking_unknown_outcome",
                    "input": cand_seg["flight_number"],
                    "output": f"Booking failed with network/system error: {str(e)}. Status is unknown.",
                    "timestamp": get_current_timestamp_z()
                }
                reasoning_traces.append(step)
                raise e
        else:
            # Pending approval path (score <= 0.9): return proposal without booking call
            print(f"LangGraph: Candidate {cand_seg['flight_number']} routed to pending approval (score={cand_score}).")
            best_cand = cand
            winning_seg = cand_seg
            winning_score = cand_score
            reasoning_traces.extend(_build_candidate_trace_steps(
                cand, state["search_mode"], state["original_price"], state["original_arrival_time"]
            ))
            break

    if not winning_seg:
        if (token and token.is_cancelled) or disruption_id in cancelled_disruption_ids:
            print("LangGraph: All auto-approval attempts were halted by a cancellation/timeout.")
            step = {
                "step_name": "booking_cancelled_timeout",
                "input": disruption_id,
                "output": "Planning timed out globally before any candidate could be booked or proposed.",
                "timestamp": get_current_timestamp_z()
            }
            return {
                "best_candidate": None,
                "confidence_score": 0.0,
                "proposed_flight_segment": None,
                "proposed_hotel_booking": None,
                "reasoning_steps": reasoning_traces + [step]
            }
        elif candidates:
            # All auto-booking attempts failed (422 sold out). Rather than reporting
            # "no alternative found" (misleading — alternatives exist, they just couldn't
            # be auto-booked), fall back to proposing the best candidate for manual
            # approval. booking_reference stays None since no booking was made.
            print("LangGraph: All auto-booking attempts failed (422). Falling back to pending_approval for best candidate.")
            best_cand = candidates[0]
            winning_seg = best_cand["segment_flat"]
            winning_score = best_cand["score"]
            reasoning_traces.extend(_build_candidate_trace_steps(
                best_cand, state["search_mode"], state["original_price"], state["original_arrival_time"]
            ))
            fallback_step = {
                "step_name": "booking_fallback",
                "input": winning_seg["flight_number"],
                "output": "All auto-booking attempts returned 422 (sold out). Proposing best candidate for manual approval.",
                "timestamp": get_current_timestamp_z()
            }
            reasoning_traces.append(fallback_step)
            # Note: winning_seg["booking_reference"] is already None (not booked)
        else:
            print("LangGraph: No viable rebooking candidates available at all.")
            step = {
                "step_name": "no_alternative_found",
                "input": "n/a",
                "output": "No candidate flights found in Amadeus inventory for this route/date/cabin.",
                "timestamp": get_current_timestamp_z()
            }
            return {
                "best_candidate": None,
                "confidence_score": 0.0,
                "proposed_flight_segment": None,
                "proposed_hotel_booking": None,
                "reasoning_steps": reasoning_traces + [step]
            }

    # Auto-book hotel stay only if the flight was actually booked (booking_reference set)
    # and proposed hotel exists (§6.1). Don't auto-book hotel if flight booking failed.
    flight_was_booked = winning_seg and winning_seg.get("booking_reference")
    if flight_was_booked and proposed_hotel and proposed_hotel.get("id"):
        if not (token and token.is_cancelled) and disruption_id not in cancelled_disruption_ids:
            print(f"LangGraph: Auto-approving hotel rebooking '{proposed_hotel['hotel_name']}'...")

            try:
                check_in = state["existing_hotel"]["check_in"] if state.get("existing_hotel") else proposed_hotel.get("check_in", get_current_timestamp_z())
                check_out = state["existing_hotel"]["check_out"] if state.get("existing_hotel") else proposed_hotel.get("check_out", get_current_timestamp_z())

                hotel_ref, hotel_status = book_hotel(
                    hotel_id=proposed_hotel["id"],
                    hotel_name=proposed_hotel["hotel_name"],
                    user_id=state["user_id"],
                    check_in=check_in,
                    check_out=check_out,
                    card_token=state["card_token"],
                    disruption_id=disruption_id
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
                else:
                    print("LangGraph ERROR: Hotel auto-booking failed (422 - sold out).")
            except requests.RequestException as e:
                print(f"LangGraph ERROR: Hotel booking failed with network exception: {e}")
                step = {
                    "step_name": "booking_unknown_outcome",
                    "input": proposed_hotel["hotel_name"],
                    "output": f"Hotel booking failed with network/system error: {str(e)}.",
                    "timestamp": get_current_timestamp_z()
                }
                reasoning_traces.append(step)
                raise e

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