"""
Write-heavy traffic pattern.
Use this to test database write scaling and transaction handling.

Usage:
    locust -f write_heavy.py --host=http://localhost:8000
"""
from personas.buyer import BuyerUser
from personas.admin import AdminUser


class HighVolumeBuyerUser(BuyerUser):
    """Buyer with increased purchase frequency for write-heavy tests."""
    weight = 60
    
    # Faster actions for more write pressure
    from locust import between
    wait_time = between(1, 2)


class ActiveAdminUser(AdminUser):
    """Admin with higher weight for write-heavy tests."""
    weight = 40
    
    # More frequent admin actions
    from locust import between
    wait_time = between(2, 4)
