"""
Spike load pattern with mixed traffic.
Flash-sale simulation - perfect for anomaly detection training.

Usage:
    locust -f spike_pattern.py --host=http://localhost:8000 --headless -t 20m
"""
from personas import BrowserUser, SearcherUser, BuyerUser
from shapes import SpikeLoadShape


class SpikeShape(SpikeLoadShape):
    """3 spikes with 2 min baseline, 1 min spike, 3 min recovery each."""
    baseline_users = 20
    spike_users = 200
    baseline_duration = 120   # 2 min baseline
    spike_duration = 60       # 1 min spike
    recovery_duration = 180   # 3 min recovery
    num_spikes = 3
    spawn_rate = 50
