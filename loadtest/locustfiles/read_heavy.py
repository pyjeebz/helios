"""
Read-heavy traffic pattern.
Use this to test read scaling and cache effectiveness.

Usage:
    locust -f read_heavy.py --host=http://localhost:8000
"""
from locust import HttpUser, between
from personas.browser import BrowserUser
from personas.searcher import SearcherUser


class ReadOnlyBrowserUser(BrowserUser):
    """Browser with higher weight for read-heavy tests."""
    weight = 70


class ReadOnlySearcherUser(SearcherUser):
    """Searcher with adjusted weight for read-heavy tests."""
    weight = 30
