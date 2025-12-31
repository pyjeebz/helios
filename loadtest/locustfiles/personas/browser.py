"""
Browser Persona - Casual browsing behavior.

Simulates users who:
- Browse category listings
- View product details
- Look at multiple pages
- Don't necessarily buy
"""
import random
from locust import HttpUser, task, between, tag

from common import GraphQLMixin, SaleorGraphQL


class BrowserUser(HttpUser, GraphQLMixin):
    """
    Simulates a casual browser who browses categories and views products.
    This is read-heavy traffic - no cart or checkout operations.
    """
    
    # Wait 2-5 seconds between requests (simulates reading time)
    wait_time = between(2, 5)
    weight = 50  # Most common user type
    
    def on_start(self):
        """Initialize user session and fetch available categories/products."""
        self.categories = []
        self.products = []
        self.product_slugs = []
        
        # Fetch categories on start
        self._fetch_categories()
    
    def _fetch_categories(self):
        """Fetch available categories."""
        data = self.graphql(
            SaleorGraphQL.CATEGORIES,
            variables={"first": 20},
            name="[Browser] Get Categories"
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("categories", {}).get("edges", [])
            self.categories = [
                {"id": e["node"]["id"], "slug": e["node"]["slug"], "name": e["node"]["name"]}
                for e in edges
            ]
    
    def _fetch_products(self, category_slug: str = None):
        """Fetch products, optionally filtered by category."""
        if category_slug:
            data = self.graphql(
                SaleorGraphQL.CATEGORY_PRODUCTS,
                variables={"slug": category_slug, "first": 12},
                name="[Browser] Category Products"
            )
            if data and "data" in data:
                products = data.get("data", {}).get("category", {}).get("products", {}).get("edges", [])
                self.products = [
                    {"id": e["node"]["id"], "slug": e["node"]["slug"], "name": e["node"]["name"]}
                    for e in products
                ]
        else:
            data = self.graphql(
                SaleorGraphQL.PRODUCTS,
                variables={"first": 20},
                name="[Browser] All Products"
            )
            if data and "data" in data:
                edges = data.get("data", {}).get("products", {}).get("edges", [])
                self.products = [
                    {"id": e["node"]["id"], "slug": e["node"]["slug"], "name": e["node"]["name"]}
                    for e in edges
                ]
    
    @task(10)
    @tag("read", "browse")
    def browse_categories(self):
        """Browse the category listing."""
        self.graphql(
            SaleorGraphQL.CATEGORIES,
            variables={"first": 20},
            name="[Browser] Browse Categories"
        )
    
    @task(30)
    @tag("read", "browse")
    def browse_category_products(self):
        """Browse products in a specific category."""
        if not self.categories:
            self._fetch_categories()
            
        if self.categories:
            category = random.choice(self.categories)
            self._fetch_products(category["slug"])
    
    @task(40)
    @tag("read", "browse")
    def view_product_list(self):
        """View the main product listing with pagination."""
        page_size = random.choice([12, 24, 48])
        
        data = self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={
                "first": page_size,
                "sortBy": random.choice([
                    {"field": "NAME", "direction": "ASC"},
                    {"field": "PRICE", "direction": "ASC"},
                    {"field": "PRICE", "direction": "DESC"},
                    {"field": "DATE", "direction": "DESC"},
                ])
            },
            name="[Browser] Product List"
        )
        
        # Cache some products for detail views
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            self.products = [
                {"id": e["node"]["id"], "slug": e["node"]["slug"], "name": e["node"]["name"]}
                for e in edges
            ]
    
    @task(20)
    @tag("read", "browse", "detail")
    def view_product_detail(self):
        """View a specific product's detail page."""
        if not self.products:
            self._fetch_products()
        
        if self.products:
            product = random.choice(self.products)
            self.graphql(
                SaleorGraphQL.PRODUCT_DETAIL,
                variables={"slug": product["slug"]},
                name="[Browser] Product Detail"
            )
    
    @task(5)
    @tag("read")
    def get_shop_info(self):
        """Fetch shop information (header/footer data)."""
        self.graphql(
            SaleorGraphQL.SHOP_INFO,
            name="[Browser] Shop Info"
        )
