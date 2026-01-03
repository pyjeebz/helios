"""
Common utilities and base classes for Locust load tests.
"""
import json
import random
import string
from typing import Any, Optional, List
from locust import HttpUser, between


# Sample data for generating realistic requests
SEARCH_TERMS = [
    "shirt", "shoes", "pants", "jacket", "dress", "hat", "bag", "watch",
    "phone", "laptop", "headphones", "camera", "book", "toy", "game",
    "kitchen", "furniture", "decor", "outdoor", "sports", "fitness"
]

FIRST_NAMES = [
    "John", "Jane", "Michael", "Sarah", "David", "Emily", "Chris", "Amanda",
    "James", "Jessica", "Robert", "Ashley", "William", "Megan", "Daniel", "Lauren"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Jackson"
]

CITIES = [
    ("New York", "NY", "10001"),
    ("Los Angeles", "CA", "90001"),
    ("Chicago", "IL", "60601"),
    ("Houston", "TX", "77001"),
    ("Phoenix", "AZ", "85001"),
    ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"),
    ("San Diego", "CA", "92101"),
]

STREET_TYPES = ["Street", "Avenue", "Boulevard", "Drive", "Lane", "Road", "Way"]


def random_email() -> str:
    """Generate a random email address."""
    username = ''.join(random.choices(string.ascii_lowercase, k=8))
    domain = random.choice(["example.com", "test.com", "loadtest.local"])
    return f"{username}@{domain}"


def random_address() -> dict:
    """Generate a random US address."""
    city, state, postal = random.choice(CITIES)
    street_num = random.randint(100, 9999)
    street_name = ''.join(random.choices(string.ascii_uppercase, k=6)).title()
    street_type = random.choice(STREET_TYPES)
    
    return {
        "firstName": random.choice(FIRST_NAMES),
        "lastName": random.choice(LAST_NAMES),
        "streetAddress1": f"{street_num} {street_name} {street_type}",
        "city": city,
        "postalCode": postal,
        "country": "US",
        "countryArea": state,
    }


def random_search_term() -> str:
    """Get a random search term."""
    return random.choice(SEARCH_TERMS)


def random_product_name() -> str:
    """Generate a random product name."""
    adjectives = ["Premium", "Deluxe", "Classic", "Modern", "Vintage", "Ultra", "Pro"]
    nouns = ["Widget", "Gadget", "Device", "Tool", "Item", "Product", "Gear"]
    return f"{random.choice(adjectives)} {random.choice(nouns)} {random.randint(100, 999)}"


class GraphQLMixin:
    """Mixin for GraphQL operations in Locust users."""
    
    def graphql(
        self,
        query: str,
        variables: Optional[dict] = None,
        name: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> dict:
        """Execute a GraphQL query/mutation."""
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        with self.client.post(
            "/graphql/",
            json=payload,
            headers=headers,
            name=name or "GraphQL",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return {}
            
            try:
                data = response.json()
                if "errors" in data and data["errors"]:
                    # Check if it's a critical error
                    error_msg = data["errors"][0].get("message", "Unknown error")
                    if "not found" not in error_msg.lower():
                        response.failure(f"GraphQL Error: {error_msg}")
                return data
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
                return {}
    
    def extract_ids(self, data: dict, path: str) -> List[str]:
        """Extract IDs from a GraphQL response using a dot-notation path."""
        try:
            parts = path.split(".")
            current = data
            for part in parts:
                if part == "edges":
                    return [edge["node"]["id"] for edge in current.get("edges", [])]
                current = current.get(part, {})
            return []
        except (KeyError, TypeError):
            return []
