"""
Buyer Persona - Full purchase journey.

Simulates users who:
- Browse products
- Add items to cart
- Go through checkout process
- Complete (or abandon) purchases
"""
import random
from locust import HttpUser, task, between, tag, events

from common import GraphQLMixin, SaleorGraphQL, random_email, random_address


class BuyerUser(HttpUser, GraphQLMixin):
    """
    Simulates a buyer going through the full purchase journey.
    Mix of read and write operations.
    """
    
    # Moderate wait times - buyers are engaged but thoughtful
    wait_time = between(2, 4)
    weight = 20  # Less common but high value
    
    def on_start(self):
        """Initialize buyer session."""
        self.products = []
        self.product_variants = {}  # product_id -> [variant_ids]
        self.checkout_id = None
        self.checkout_token = None
        self.cart_items = 0
        
        # Pre-fetch some products
        self._fetch_products()
    
    def _fetch_products(self):
        """Fetch available products with variants."""
        data = self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={"first": 30},
            name="[Buyer] Fetch Products"
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            self.products = [
                {"id": e["node"]["id"], "slug": e["node"]["slug"], "name": e["node"]["name"]}
                for e in edges
            ]
    
    def _get_product_variants(self, product_slug: str) -> list:
        """Get variants for a product."""
        if product_slug in self.product_variants:
            return self.product_variants[product_slug]
        
        data = self.graphql(
            SaleorGraphQL.PRODUCT_DETAIL,
            variables={"slug": product_slug},
            name="[Buyer] Get Variants"
        )
        
        variants = []
        if data and "data" in data:
            product = data.get("data", {}).get("product", {})
            if product:
                variants = [
                    {"id": v["id"], "name": v["name"]}
                    for v in product.get("variants", [])
                    if v.get("quantityAvailable", 0) > 0
                ]
                self.product_variants[product_slug] = variants
        
        return variants
    
    def _create_checkout(self, variant_id: str, quantity: int = 1):
        """Create a new checkout with an item."""
        email = random_email()
        
        data = self.graphql(
            SaleorGraphQL.CHECKOUT_CREATE,
            variables={
                "input": {
                    "channel": "default-channel",
                    "email": email,
                    "lines": [{"variantId": variant_id, "quantity": quantity}]
                }
            },
            name="[Buyer] Create Checkout"
        )
        
        if data and "data" in data:
            checkout = data.get("data", {}).get("checkoutCreate", {}).get("checkout", {})
            if checkout:
                self.checkout_id = checkout.get("id")
                self.checkout_token = checkout.get("token")
                self.cart_items = quantity
                return True
        
        return False
    
    @task(25)
    @tag("read", "browse")
    def browse_products(self):
        """Browse products (buyer still browses)."""
        data = self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={"first": 20},
            name="[Buyer] Browse Products"
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            self.products = [
                {"id": e["node"]["id"], "slug": e["node"]["slug"], "name": e["node"]["name"]}
                for e in edges
            ]
    
    @task(20)
    @tag("read", "browse", "detail")
    def view_product_detail(self):
        """View product detail (pre-purchase research)."""
        if not self.products:
            self._fetch_products()
        
        if self.products:
            product = random.choice(self.products)
            self._get_product_variants(product["slug"])
    
    @task(15)
    @tag("write", "cart")
    def add_to_cart(self):
        """Add item to cart."""
        if not self.products:
            self._fetch_products()
        
        if not self.products:
            return
        
        product = random.choice(self.products)
        variants = self._get_product_variants(product["slug"])
        
        if not variants:
            return
        
        variant = random.choice(variants)
        quantity = random.randint(1, 3)
        
        if not self.checkout_id:
            # Create new checkout
            self._create_checkout(variant["id"], quantity)
        else:
            # Add to existing checkout
            data = self.graphql(
                SaleorGraphQL.CHECKOUT_LINES_ADD,
                variables={
                    "id": self.checkout_id,
                    "lines": [{"variantId": variant["id"], "quantity": quantity}]
                },
                name="[Buyer] Add to Cart"
            )
            
            if data and "data" in data:
                checkout = data.get("data", {}).get("checkoutLinesAdd", {}).get("checkout", {})
                if checkout:
                    self.cart_items += quantity
    
    @task(10)
    @tag("read", "cart")
    def view_cart(self):
        """View current cart."""
        if self.checkout_id:
            self.graphql(
                SaleorGraphQL.CHECKOUT,
                variables={"id": self.checkout_id},
                name="[Buyer] View Cart"
            )
    
    @task(8)
    @tag("write", "checkout")
    def set_shipping_address(self):
        """Set shipping address on checkout."""
        if not self.checkout_id or self.cart_items == 0:
            return
        
        address = random_address()
        
        self.graphql(
            SaleorGraphQL.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
            variables={
                "id": self.checkout_id,
                "address": address
            },
            name="[Buyer] Set Shipping Address"
        )
    
    @task(8)
    @tag("write", "checkout")
    def set_billing_address(self):
        """Set billing address on checkout."""
        if not self.checkout_id or self.cart_items == 0:
            return
        
        address = random_address()
        
        self.graphql(
            SaleorGraphQL.CHECKOUT_BILLING_ADDRESS_UPDATE,
            variables={
                "id": self.checkout_id,
                "address": address
            },
            name="[Buyer] Set Billing Address"
        )
    
    @task(5)
    @tag("write", "checkout")
    def complete_checkout(self):
        """Attempt to complete the checkout (order placement)."""
        if not self.checkout_id or self.cart_items == 0:
            return
        
        # Set addresses first
        address = random_address()
        
        self.graphql(
            SaleorGraphQL.CHECKOUT_SHIPPING_ADDRESS_UPDATE,
            variables={"id": self.checkout_id, "address": address},
            name="[Buyer] Checkout - Shipping"
        )
        
        self.graphql(
            SaleorGraphQL.CHECKOUT_BILLING_ADDRESS_UPDATE,
            variables={"id": self.checkout_id, "address": address},
            name="[Buyer] Checkout - Billing"
        )
        
        # Complete checkout
        data = self.graphql(
            SaleorGraphQL.CHECKOUT_COMPLETE,
            variables={"id": self.checkout_id},
            name="[Buyer] Complete Checkout"
        )
        
        # Reset cart regardless of outcome
        self.checkout_id = None
        self.checkout_token = None
        self.cart_items = 0
    
    @task(4)
    @tag("write", "cart")
    def abandon_cart(self):
        """Abandon current cart (simulate cart abandonment)."""
        if self.checkout_id and random.random() < 0.3:  # 30% abandon rate
            self.checkout_id = None
            self.checkout_token = None
            self.cart_items = 0
