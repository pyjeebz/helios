"""
Ramp load pattern with mixed traffic.
Gradual growth - perfect for trend detection training.

Usage:
    locust -f ramp_pattern.py --host=http://localhost:8000 --headless -t 20m
"""
from personas import BrowserUser, SearcherUser, BuyerUser
from shapes import RampLoadShape


class RampShape(RampLoadShape):
    """Ramp from 0 to 100 users over 5 minutes, hold 10 minutes, ramp down."""
    max_users = 100
    ramp_duration = 300      # 5 min ramp up
    hold_duration = 600      # 10 min hold
    spawn_rate = 5
