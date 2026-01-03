"""
Combined locustfile with all personas.
Use this for realistic mixed traffic patterns.

Usage:
    locust -f locustfile.py --host=http://localhost:8000
"""
from personas import BrowserUser, SearcherUser, BuyerUser, AdminUser

# All user classes are automatically discovered by Locust
# Weight distribution (defined in each class):
#   BrowserUser: 50  (casual browsing)
#   SearcherUser: 25 (search-heavy)
#   BuyerUser: 20    (purchase journey)
#   AdminUser: 5     (admin operations)
