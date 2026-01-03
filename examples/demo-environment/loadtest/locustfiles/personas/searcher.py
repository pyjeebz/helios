"""
Searcher Persona - Search-focused behavior.

Simulates users who:
- Use search functionality heavily
- Apply filters and sorting
- Compare products
- May or may not proceed to purchase
"""
import random
from locust import HttpUser, task, between, tag

from common import GraphQLMixin, SaleorGraphQL, random_search_term, SEARCH_TERMS


class SearcherUser(HttpUser, GraphQLMixin):
    """
    Simulates a user who heavily uses search and filtering.
    Read-heavy with emphasis on search operations.
    """
    
    # Shorter wait times - searchers are more impatient
    wait_time = between(1, 3)
    weight = 25  # Common but less than browsers
    
    def on_start(self):
        """Initialize search session."""
        self.recent_searches = []
        self.found_products = []
    
    @task(40)
    @tag("read", "search")
    def search_products(self):
        """Perform a product search."""
        search_term = random_search_term()
        
        data = self.graphql(
            SaleorGraphQL.SEARCH_PRODUCTS,
            variables={"search": search_term, "first": 20},
            name=f"[Searcher] Search"
        )
        
        if data and "data" in data:
            edges = data.get("data", {}).get("products", {}).get("edges", [])
            self.found_products = [
                {"id": e["node"]["id"], "slug": e["node"]["slug"]}
                for e in edges
            ]
            self.recent_searches.append(search_term)
            # Keep only last 5 searches
            self.recent_searches = self.recent_searches[-5:]
    
    @task(20)
    @tag("read", "search", "filter")
    def search_with_filter(self):
        """Search with price filters."""
        search_term = random_search_term()
        
        # Random price range
        min_price = random.choice([0, 10, 25, 50, 100])
        max_price = min_price + random.choice([50, 100, 200, 500])
        
        self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={
                "first": 20,
                "filter": {
                    "search": search_term,
                    "price": {
                        "gte": min_price,
                        "lte": max_price
                    }
                }
            },
            name="[Searcher] Search + Filter"
        )
    
    @task(15)
    @tag("read", "search", "sort")
    def search_with_sort(self):
        """Search with sorting applied."""
        search_term = random_search_term()
        
        sort_options = [
            {"field": "NAME", "direction": "ASC"},
            {"field": "NAME", "direction": "DESC"},
            {"field": "PRICE", "direction": "ASC"},
            {"field": "PRICE", "direction": "DESC"},
            {"field": "RATING", "direction": "DESC"},
            {"field": "DATE", "direction": "DESC"},
        ]
        
        self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={
                "first": 20,
                "filter": {"search": search_term},
                "sortBy": random.choice(sort_options)
            },
            name="[Searcher] Search + Sort"
        )
    
    @task(10)
    @tag("read", "search")
    def refine_search(self):
        """Refine a previous search (simulate user adjusting query)."""
        if self.recent_searches:
            base_term = random.choice(self.recent_searches)
            # Add a modifier
            modifiers = ["best", "cheap", "premium", "new", "sale", "top"]
            refined_term = f"{random.choice(modifiers)} {base_term}"
            
            self.graphql(
                SaleorGraphQL.SEARCH_PRODUCTS,
                variables={"search": refined_term, "first": 20},
                name="[Searcher] Refined Search"
            )
        else:
            self.search_products()
    
    @task(15)
    @tag("read", "search", "detail")
    def view_search_result(self):
        """View a product from search results."""
        if not self.found_products:
            self.search_products()
        
        if self.found_products:
            product = random.choice(self.found_products)
            self.graphql(
                SaleorGraphQL.PRODUCT_DETAIL,
                variables={"slug": product["slug"]},
                name="[Searcher] View Result"
            )
    
    @task(5)
    @tag("read", "search")
    def paginate_results(self):
        """Paginate through search results."""
        search_term = random_search_term()
        
        # First page
        data = self.graphql(
            SaleorGraphQL.PRODUCTS,
            variables={"first": 12, "filter": {"search": search_term}},
            name="[Searcher] Results Page 1"
        )
        
        # Get next page cursor
        if data and "data" in data:
            page_info = data.get("data", {}).get("products", {}).get("pageInfo", {})
            if page_info.get("hasNextPage"):
                cursor = page_info.get("endCursor")
                self.graphql(
                    SaleorGraphQL.PRODUCTS,
                    variables={
                        "first": 12,
                        "after": cursor,
                        "filter": {"search": search_term}
                    },
                    name="[Searcher] Results Page 2"
                )
