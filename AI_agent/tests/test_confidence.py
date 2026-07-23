import pytest
from agent.confidence import compute_confidence_score

def test_worked_example_success():
    # JFK-LHR, BA112 cancelled, rebooked onto BA456 at $4910 vs original $4820
    # Price delta = +$90, cabin_match = 1, loyalty_match = 1, arrival_delta < 2hr
    # Formula terms:
    # price_delta_ok: +$90 is within $150 limit -> 0.7
    # same_cabin: business -> business -> 1.0
    # loyalty_program_match: BA matches BA Executive Club -> 1.0
    # arrival_time_delta_small: arrival within 2hrs -> 1.0
    # Expected score = 0.3*0.7 + 0.3*1.0 + 0.2*1.0 + 0.2*1.0 = 0.91
    
    score = compute_confidence_score(
        new_price=4910.00,
        original_price=4820.00,
        max_price_delta=150.00,
        new_cabin="business",
        original_cabin="business",
        allow_cabin_downgrade=False,
        carrier="BA",
        loyalty_program="BA Executive Club",
        new_arrival_time_str="2026-07-23T10:30:00Z", # original: 09:05:00Z (difference 1h25m)
        original_arrival_time_str="2026-07-23T09:05:00Z"
    )
    assert score == 0.91

def test_cabin_downgrade_allowed():
    # Cabin business -> economy (downgrade)
    # allow_cabin_downgrade = True -> same_cabin score = 0.5
    # Price delta: $0 -> price_delta_ok = 1.0
    # Loyalty match -> 1.0
    # Arrival delta: < 2hrs -> 1.0
    # Expected score = 0.3*1.0 + 0.3*0.5 + 0.2*1.0 + 0.2*1.0 = 0.3 + 0.15 + 0.2 + 0.2 = 0.85
    
    score = compute_confidence_score(
        new_price=4820.00,
        original_price=4820.00,
        max_price_delta=150.00,
        new_cabin="economy",
        original_cabin="business",
        allow_cabin_downgrade=True,
        carrier="BA",
        loyalty_program="BA Executive Club",
        new_arrival_time_str="2026-07-23T09:05:00Z",
        original_arrival_time_str="2026-07-23T09:05:00Z"
    )
    assert score == 0.85

def test_cabin_downgrade_not_allowed():
    # Cabin business -> economy (downgrade)
    # allow_cabin_downgrade = False -> same_cabin score = 0.0
    # Price delta: $0 -> price_delta_ok = 1.0
    # Loyalty match -> 1.0
    # Arrival delta: < 2hrs -> 1.0
    # Expected score = 0.3*1.0 + 0.3*0.0 + 0.2*1.0 + 0.2*1.0 = 0.3 + 0.0 + 0.2 + 0.2 = 0.70
    
    score = compute_confidence_score(
        new_price=4820.00,
        original_price=4820.00,
        max_price_delta=150.00,
        new_cabin="economy",
        original_cabin="business",
        allow_cabin_downgrade=False,
        carrier="BA",
        loyalty_program="BA Executive Club",
        new_arrival_time_str="2026-07-23T09:05:00Z",
        original_arrival_time_str="2026-07-23T09:05:00Z"
    )
    assert score == 0.70

def test_loyalty_mismatch():
    # Carrier AF, program BA Executive Club -> loyalty score = 0.0
    # Same price -> price_delta_ok = 1.0
    # Same cabin -> same_cabin = 1.0
    # Arrival delta < 2hr -> arrival_time_delta_small = 1.0
    # Expected score = 0.3*1.0 + 0.3*1.0 + 0.2*0.0 + 0.2*1.0 = 0.80
    
    score = compute_confidence_score(
        new_price=4820.00,
        original_price=4820.00,
        max_price_delta=150.00,
        new_cabin="business",
        original_cabin="business",
        allow_cabin_downgrade=False,
        carrier="AF",
        loyalty_program="BA Executive Club",
        new_arrival_time_str="2026-07-23T09:05:00Z",
        original_arrival_time_str="2026-07-23T09:05:00Z"
    )
    assert score == 0.80

def test_large_price_delta():
    # Price delta = +$400 vs $150 limit. Delta is > 2 * max_price_delta.
    # price_delta_ok = 0.0
    # Same cabin -> same_cabin = 1.0
    # Loyalty match -> 1.0
    # Arrival delta < 2hr -> arrival_time_delta_small = 1.0
    # Expected score = 0.3*0.0 + 0.3*1.0 + 0.2*1.0 + 0.2*1.0 = 0.70
    
    score = compute_confidence_score(
        new_price=5220.00,
        original_price=4820.00,
        max_price_delta=150.00,
        new_cabin="business",
        original_cabin="business",
        allow_cabin_downgrade=False,
        carrier="BA",
        loyalty_program="BA Executive Club",
        new_arrival_time_str="2026-07-23T09:05:00Z",
        original_arrival_time_str="2026-07-23T09:05:00Z"
    )
    assert score == 0.70
