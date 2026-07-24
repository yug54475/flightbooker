from decimal import Decimal
from datetime import datetime
from typing import Optional

CABIN_RANKS = {
    "economy": 1,
    "premium_economy": 2,
    "business": 3,
    "first": 4
}

def parse_iso_time(time_str: str) -> datetime:
    """Parses ISO 8601 UTC timestamp string with Z or standard offsets safely (Issue 5)."""
    if time_str.endswith("Z"):
        time_str = time_str[:-1] + "+00:00"
    return datetime.fromisoformat(time_str)

def get_cabin_match_score(new_cabin: str, original_cabin: str, allow_cabin_downgrade: bool) -> float:
    new_cabin = new_cabin.lower()
    original_cabin = original_cabin.lower()
    
    if new_cabin == original_cabin:
        return 1.0
        
    new_rank = CABIN_RANKS.get(new_cabin, 1)
    original_rank = CABIN_RANKS.get(original_cabin, 1)
    
    # Check if it is a downgrade
    if new_rank < original_rank:
        if allow_cabin_downgrade:
            return 0.5
        else:
            return 0.0
            
    # Upgrade or equal rank
    return 1.0

def get_price_delta_score(new_price: Decimal, original_price: Decimal, max_price_delta: Decimal) -> float:
    if new_price <= original_price:
        return 1.0
        
    delta = new_price - original_price
    if delta <= max_price_delta:
        return 0.7
    elif delta <= 2 * max_price_delta:
        return 0.3
    else:
        return 0.0

def get_loyalty_match_score(carrier_code_or_name: str, loyalty_program: Optional[str]) -> float:
    if not loyalty_program:
        return 0.0
        
    carrier_lower = carrier_code_or_name.lower()
    program_lower = loyalty_program.lower()
    
    # Explicit mapping for the main demo carriers
    # BA Executive Club (BA), Flying Blue (AF), JAL Mileage Bank (JL)
    if "ba" in carrier_lower or "british" in carrier_lower:
        if "ba" in program_lower or "executive club" in program_lower:
            return 1.0
    if "af" in carrier_lower or "france" in carrier_lower:
        if "flying blue" in program_lower or "france" in program_lower:
            return 1.0
    if "jl" in carrier_lower or "jal" in carrier_lower or "japan" in carrier_lower:
        if "jal" in program_lower or "mileage bank" in program_lower:
            return 1.0
            
    # Fallback to simple matching
    if carrier_lower in program_lower or program_lower in carrier_lower:
        return 1.0
        
    return 0.0

def get_arrival_time_delta_score(new_arrival: datetime, original_arrival: datetime) -> float:
    delta_seconds = abs((new_arrival - original_arrival).total_seconds())
    delta_hours = delta_seconds / 3600.0
    
    if delta_hours <= 2.0:
        return 1.0
    elif delta_hours <= 6.0:
        return 0.6
    elif delta_hours <= 12.0:
        return 0.3
    else:
        return 0.0

def compute_confidence_score(
    new_price: float,
    original_price: float,
    max_price_delta: float,
    new_cabin: str,
    original_cabin: str,
    allow_cabin_downgrade: bool,
    carrier: str,
    loyalty_program: Optional[str],
    new_arrival_time_str: str,
    original_arrival_time_str: str
) -> tuple:
    """
    Computes the total confidence score based on the §7 formula:
    score = 0.3*price_delta_ok + 0.3*same_cabin + 0.2*loyalty_program_match + 0.2*arrival_time_delta_small
    """
    p_score = get_price_delta_score(Decimal(str(new_price)), Decimal(str(original_price)), Decimal(str(max_price_delta)))
    c_score = get_cabin_match_score(new_cabin, original_cabin, allow_cabin_downgrade)
    l_score = get_loyalty_match_score(carrier, loyalty_program)
    
    new_arrival = parse_iso_time(new_arrival_time_str)
    orig_arrival = parse_iso_time(original_arrival_time_str)
    a_score = get_arrival_time_delta_score(new_arrival, orig_arrival)
    
    # Use Decimal arithmetic for the weighted sum per §0 (never float-round money/score fields)
    raw_score = float(
        Decimal("0.3") * Decimal(str(p_score))
        + Decimal("0.3") * Decimal(str(c_score))
        + Decimal("0.2") * Decimal(str(l_score))
        + Decimal("0.2") * Decimal(str(a_score))
    )
    sub_scores = {
        "price_delta_ok": p_score,
        "same_cabin": c_score,
        "loyalty_program_match": l_score,
        "arrival_time_delta_small": a_score
    }
    return round(raw_score, 3), sub_scores
