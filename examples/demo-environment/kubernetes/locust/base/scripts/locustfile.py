"""
Simplified locustfile for Kubernetes deployment.
All code in single file for ConfigMap deployment.
"""
import json
import random
import string
from typing import Any, Optional, List
from locust import HttpUser, task, between, tag


# ============== UTILITIES ==============

SEARCH_TERMS = [
    "shirt", "shoes", "pants", "jacket", "dress", "hat", "bag", "watch",
    "phone", "laptop", "headphones", "camera", "book", "toy", "game"
]

FIRST_NAMES = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Chris", "Amanda"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
CITIES = [
    ("New York", "NY", "10001"),
    ("Los Angeles", "CA", "90001"),
    ("Chicago", "IL", "60601"),
]

def random_email() -> str:
    username = ''.join(random.choices(string.ascii_lowercase, k=8))
    return f"{username}@loadtest.local"

def random_address() -> dict:
    city, state, postal = random.choice(CITIES)
    return {
        "firstName": random.choice(FIRST_NAMES),
        "lastName": random.choice(LAST_NAMES),
        "streetAddress1": f"{random.randint(100, 999)} Test Street",
        "city": city,
        "postalCode": postal,
        "country": "US",
        "countryArea": state,
    }


# ============== GRAPHQL QUERIES ==============

CATEGORIES_QUERY = """
query Categories($first: Int!) {
    categories(first: $first) {
        edges { node { id name slug } }
    }
}
"""

PRODUCTS_QUERY = """
query Products($first: Int!, $filter: ProductFilterInput, $sortBy: ProductOrder) {
    products(first: $first, filter: $filter, sortBy: $sortBy, channel: "default-channel") {
        edges { node { id name slug } }
        totalCount
    }
}
"""

PRODUCT_DETAIL_QUERY = """
query ProductDetail($slug: String!) {
    product(slug: $slug, channel: "default-channel") {
        id name slug description
        variants { id name sku quantityAvailable }
    }
}
"""

SEARCH_QUERY = """
query Search($search: String!, $first: Int!) {
    products(first: $first, filter: { search: $search }, channel: "default-channel") {
        edges { node { id name slug } }
        totalCount
    }
}
"""

CHECKOUT_CREATE = """
mutation CheckoutCreate($input: CheckoutCreateInput!) {
    checkoutCreate(input: $input) {
        checkout { id token lines { id } }
        errors { field message }
    }
}
"""

CHECKOUT_LINES_ADD = """
mutation CheckoutLinesAdd($id: ID!, $lines: [CheckoutLineInput!]!) {
    checkoutLinesAdd(id: $id, lines: $lines) {
        checkout { id lines { id } totalPrice { gross { amount } } }
        errors { field message }
    }
}
"""


# ============== GRAPHQL MIXIN ==============

class GraphQLMixin:
    def graphql(self, query: str, variables: dict = None, name: str = "GraphQL"):
        headers = {"Content-Type": "application/json"}
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        with self.client.post("/graphql/", json=payload, headers=headers, 
                              name=name, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return {}
            try:
                data = response.json()
                if "errors" in data and data["errors"]:
                    error_msg = data["errors"][0].get("message", "Unknown")
                    if "not found" not in error_msg.lower():
                        response.failure(f"GraphQL: {error_msg}")
                return data
            except json.JSONDecodeError:
                response.failure("Invalid JSON")
                return {}


# ============== USER PERSONAS ==============

class BrowserUser(HttpUser, GraphQLMixin):
    """Casual browser - read-heavy."""
    wait_time = between(2, 5)
    weight = 50
    
    def on_start(self):
        self.products = []
        self._fetch_products()
    
    def _fetch_products(self):
        data = self.graphql(PRODUCTS_QUERY, {"first": 20}, "[Browser] Products")
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            self.products = [e["node"] for e in edges]
    
    @task(30)
    @tag("read")
    def browse_categories(self):
        self.graphql(CATEGORIES_QUERY, {"first": 20}, "[Browser] Categories")
    
    @task(50)
    @tag("read")
    def browse_products(self):
        self.graphql(PRODUCTS_QUERY, {"first": 20}, "[Browser] Products")
    
    @task(20)
    @tag("read")
    def view_product(self):
        if not self.products:
            self._fetch_products()
        if self.products:
            product = random.choice(self.products)
            self.graphql(PRODUCT_DETAIL_QUERY, {"slug": product["slug"]}, "[Browser] Detail")


class SearcherUser(HttpUser, GraphQLMixin):
    """Search-focused user."""
    wait_time = between(1, 3)
    weight = 25
    
    @task(60)
    @tag("read", "search")
    def search_products(self):
        term = random.choice(SEARCH_TERMS)
        self.graphql(SEARCH_QUERY, {"search": term, "first": 20}, "[Searcher] Search")
    
    @task(30)
    @tag("read", "search")
    def search_with_sort(self):
        term = random.choice(SEARCH_TERMS)
        sorts = [
            {"field": "NAME", "direction": "ASC"},
            {"field": "PRICE", "direction": "ASC"},
            {"field": "PRICE", "direction": "DESC"},
        ]
        self.graphql(PRODUCTS_QUERY, {
            "first": 20,
            "filter": {"search": term},
            "sortBy": random.choice(sorts)
        }, "[Searcher] Search+Sort")
    
    @task(10)
    @tag("read")
    def browse(self):
        self.graphql(PRODUCTS_QUERY, {"first": 20}, "[Searcher] Browse")


class BuyerUser(HttpUser, GraphQLMixin):
    """Buyer going through purchase journey."""
    wait_time = between(2, 4)
    weight = 20
    
    def on_start(self):
        self.products = []
        self.checkout_id = None
        self._fetch_products()
    
    def _fetch_products(self):
        data = self.graphql(PRODUCTS_QUERY, {"first": 30}, "[Buyer] Products")
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            self.products = [e["node"] for e in edges]
    
    def _get_variant(self, slug: str):
        data = self.graphql(PRODUCT_DETAIL_QUERY, {"slug": slug}, "[Buyer] GetVariant")
        if data and "data" in data:
            product = data.get("data", {}).get("product", {})
            if product:
                variants = [v for v in product.get("variants", []) 
                           if v.get("quantityAvailable", 0) > 0]
                return variants[0]["id"] if variants else None
        return None
    
    @task(30)
    @tag("read")
    def browse_products(self):
        self._fetch_products()
    
    @task(25)
    @tag("read")
    def view_product(self):
        if self.products:
            product = random.choice(self.products)
            self.graphql(PRODUCT_DETAIL_QUERY, {"slug": product["slug"]}, "[Buyer] Detail")
    
    @task(20)
    @tag("write", "cart")
    def add_to_cart(self):
        if not self.products:
            return
        
        product = random.choice(self.products)
        variant_id = self._get_variant(product["slug"])
        if not variant_id:
            return
        
        if not self.checkout_id:
            data = self.graphql(CHECKOUT_CREATE, {
                "input": {
                    "channel": "default-channel",
                    "email": random_email(),
                    "lines": [{"variantId": variant_id, "quantity": 1}]
                }
            }, "[Buyer] CreateCart")
            if data and "data" in data:
                checkout = data.get("data", {}).get("checkoutCreate", {}).get("checkout", {})
                self.checkout_id = checkout.get("id")
        else:
            self.graphql(CHECKOUT_LINES_ADD, {
                "id": self.checkout_id,
                "lines": [{"variantId": variant_id, "quantity": 1}]
            }, "[Buyer] AddToCart")
    
    @task(5)
    @tag("write")
    def abandon_cart(self):
        if self.checkout_id and random.random() < 0.3:
            self.checkout_id = None


class AdminUser(HttpUser, GraphQLMixin):
    """Admin operations - read-heavy for now."""
    wait_time = between(3, 8)
    weight = 5
    
    @task(40)
    @tag("read", "admin")
    def view_products(self):
        self.graphql(PRODUCTS_QUERY, {"first": 50}, "[Admin] Products")
    
    @task(30)
    @tag("read", "admin")
    def view_categories(self):
        self.graphql(CATEGORIES_QUERY, {"first": 50}, "[Admin] Categories")
    
    @task(30)
    @tag("read", "admin")
    def view_detail(self):
        data = self.graphql(PRODUCTS_QUERY, {"first": 10}, "[Admin] FetchList")
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            if edges:
                product = random.choice(edges)["node"]
                self.graphql(PRODUCT_DETAIL_QUERY, {"slug": product["slug"]}, "[Admin] Detail")
