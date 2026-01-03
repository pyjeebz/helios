"""
Wave load pattern with mixed traffic.
Sinusoidal pattern - perfect for seasonality detection training.

Usage:
    locust -f wave_pattern.py --host=http://localhost:8000 --headless -t 30m
"""
from personas import BrowserUser, SearcherUser, BuyerUser
from shapes import WaveLoadShape


class WaveShape(WaveLoadShape):
    """6 sine wave cycles over 30 minutes."""
    min_users = 10
    max_users = 100
    period = 300             # 5 minute cycles
    num_cycles = 6           # 30 minutes total
    spawn_rate = 10
