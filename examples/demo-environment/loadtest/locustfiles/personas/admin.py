"""
Admin Persona - Administrative operations.

Simulates admin users who:
- Create and update products
- Manage inventory
- Generate write pressure on the system
"""
import random
import string
from locust import HttpUser, task, between, tag

from common import GraphQLMixin, SaleorGraphQL, random_product_name


class AdminUser(HttpUser, GraphQLMixin):
    """
    Simulates an admin user performing write-heavy operations.
    Requires authentication.
    """
    
    # Admins work more slowly and deliberately
    wait_time = between(3, 8)
    weight = 5  # Rare but impactful
    
    def on_start(self):
        """Initialize admin session and authenticate."""
        self.auth_token = None
        self.product_types = []
        self.categories = []
        self.created_products = []
        
        # Authenticate
        self._authenticate()
        
        # Fetch product types and categories
        if self.auth_token:
            self._fetch_metadata()
    
    def _authenticate(self):
        """Authenticate as admin user."""
        # Use environment variables in production
        import os
        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        password = os.environ.get("ADMIN_PASSWORD", "admin123456")
        
        data = self.graphql(
            SaleorGraphQL.TOKEN_CREATE,
            variables={"email": email, "password": password},
            name="[Admin] Login"
        )
        
        if data and "data" in data:
            token_data = data.get("data", {}).get("tokenCreate", {})
            self.auth_token = token_data.get("token")
    
    def _fetch_metadata(self):
        """Fetch product types and categories for creating products."""
        # Fetch categories
        data = self.graphql(
            SaleorGraphQL.CATEGORIES,
            variables={"first": 50},
            name="[Admin] Fetch Categories",
            auth_token=self.auth_token
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("categories", {}).get("edges", [])
            self.categories = [e["node"]["id"] for e in edges]
    
    @task(15)
    @tag("read", "admin")
    def view_products(self):
        """View product listing (admin dashboard)."""
        if not self.auth_token:
            self._authenticate()
            return
        
        self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={"first": 50},
            name="[Admin] View Products",
            auth_token=self.auth_token
        )
    
    @task(10)
    @tag("write", "admin", "product")
    def create_product(self):
        """Create a new product."""
        if not self.auth_token:
            self._authenticate()
            return
        
        if not self.categories:
            self._fetch_metadata()
            return
        
        product_name = random_product_name()
        slug = product_name.lower().replace(" ", "-") + "-" + ''.join(random.choices(string.ascii_lowercase, k=4))
        
        # Note: This requires a product type ID which we'd need to fetch
        # For now, this demonstrates the pattern
        data = self.graphql(
            """
            mutation CreateProduct($input: ProductCreateInput!) {
                productCreate(input: $input) {
                    product { id name slug }
                    errors { field message }
                }
            }
            """,
            variables={
                "input": {
                    "name": product_name,
                    "slug": slug,
                    "description": f"Load test product: {product_name}",
                    "category": random.choice(self.categories) if self.categories else None,
                }
            },
            name="[Admin] Create Product",
            auth_token=self.auth_token
        )
        
        if data and "data" in data:
            product = data.get("data", {}).get("productCreate", {}).get("product", {})
            if product:
                self.created_products.append(product.get("id"))
    
    @task(20)
    @tag("write", "admin", "product")
    def update_product(self):
        """Update an existing product."""
        if not self.auth_token:
            self._authenticate()
            return
        
        # First fetch a product to update
        data = self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={"first": 10},
            name="[Admin] Fetch for Update",
            auth_token=self.auth_token
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            if edges:
                product = random.choice(edges)["node"]
                
                # Update the product
                self.graphql(
                    SaleorGraphQL.PRODUCT_UPDATE,
                    variables={
                        "id": product["id"],
                        "input": {
                            "description": f"Updated at {random.randint(1000, 9999)} by load test"
                        }
                    },
                    name="[Admin] Update Product",
                    auth_token=self.auth_token
                )
    
    @task(5)
    @tag("read", "admin")
    def view_categories(self):
        """View category listing."""
        if not self.auth_token:
            self._authenticate()
            return
        
        self.graphql(
            SaleorGraphQL.CATEGORIES,
            variables={"first": 50},
            name="[Admin] View Categories",
            auth_token=self.auth_token
        )
    
    @task(3)
    @tag("read", "admin")
    def view_product_detail(self):
        """View detailed product info (admin editing)."""
        if not self.auth_token:
            self._authenticate()
            return
        
        # Fetch products first
        data = self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={"first": 20},
            name="[Admin] Fetch Product List",
            auth_token=self.auth_token
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            if edges:
                product = random.choice(edges)["node"]
                self.graphql(
                    SaleorGraphQL.PRODUCT_DETAIL,
                    variables={"slug": product["slug"]},
                    name="[Admin] View Product Detail",
                    auth_token=self.auth_token
                )
