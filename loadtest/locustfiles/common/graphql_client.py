"""
GraphQL client utilities for Saleor API interactions.
"""
import json
from typing import Any, Optional


class SaleorGraphQL:
    """Helper class for Saleor GraphQL operations."""
    
    # ============== QUERIES ==============
    
    SHOP_INFO = """
    query ShopInfo {
        shop {
            name
            description
            defaultCountry { code country }
        }
    }
    """
    
    CATEGORIES = """
    query Categories($first: Int!) {
        categories(first: $first) {
            edges {
                node {
                    id
                    name
                    slug
                    description
                    products(first: 5) {
                        totalCount
                    }
                }
            }
        }
    }
    """
    
    CATEGORY_PRODUCTS = """
    query CategoryProducts($slug: String!, $first: Int!, $after: String) {
        category(slug: $slug) {
            id
            name
            products(first: $first, after: $after, channel: "default-channel") {
                edges {
                    node {
                        id
                        name
                        slug
                        thumbnail { url }
                        pricing {
                            priceRange {
                                start { gross { amount currency } }
                            }
                        }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
    """
    
    PRODUCTS = """
    query Products($first: Int!, $after: String, $filter: ProductFilterInput, $sortBy: ProductOrder) {
        products(first: $first, after: $after, filter: $filter, sortBy: $sortBy, channel: "default-channel") {
            edges {
                node {
                    id
                    name
                    slug
                    thumbnail { url }
                    category { name }
                    pricing {
                        priceRange {
                            start { gross { amount currency } }
                            stop { gross { amount currency } }
                        }
                    }
                }
            }
            pageInfo { hasNextPage endCursor }
            totalCount
        }
    }
    """
    
    PRODUCT_DETAIL = """
    query ProductDetail($slug: String!) {
        product(slug: $slug, channel: "default-channel") {
            id
            name
            slug
            description
            category { id name }
            thumbnail { url }
            media { url type }
            variants {
                id
                name
                sku
                pricing {
                    price { gross { amount currency } }
                }
                quantityAvailable
            }
            pricing {
                priceRange {
                    start { gross { amount currency } }
                    stop { gross { amount currency } }
                }
            }
        }
    }
    """
    
    SEARCH_PRODUCTS = """
    query SearchProducts($search: String!, $first: Int!) {
        products(first: $first, filter: { search: $search }, channel: "default-channel") {
            edges {
                node {
                    id
                    name
                    slug
                    thumbnail { url }
                    pricing {
                        priceRange {
                            start { gross { amount currency } }
                        }
                    }
                }
            }
            totalCount
        }
    }
    """
    
    CHECKOUT = """
    query Checkout($id: ID!) {
        checkout(id: $id) {
            id
            token
            email
            lines {
                id
                quantity
                variant { id name }
                totalPrice { gross { amount currency } }
            }
            subtotalPrice { gross { amount currency } }
            totalPrice { gross { amount currency } }
            shippingMethods {
                id
                name
                price { amount currency }
            }
        }
    }
    """
    
    # ============== MUTATIONS ==============
    
    CHECKOUT_CREATE = """
    mutation CheckoutCreate($input: CheckoutCreateInput!) {
        checkoutCreate(input: $input) {
            checkout {
                id
                token
                lines { id quantity variant { id name } }
            }
            errors { field message code }
        }
    }
    """
    
    CHECKOUT_LINES_ADD = """
    mutation CheckoutLinesAdd($id: ID!, $lines: [CheckoutLineInput!]!) {
        checkoutLinesAdd(id: $id, lines: $lines) {
            checkout {
                id
                lines { id quantity variant { id name } }
                totalPrice { gross { amount currency } }
            }
            errors { field message code }
        }
    }
    """
    
    CHECKOUT_EMAIL_UPDATE = """
    mutation CheckoutEmailUpdate($id: ID!, $email: String!) {
        checkoutEmailUpdate(id: $id, email: $email) {
            checkout { id email }
            errors { field message code }
        }
    }
    """
    
    CHECKOUT_SHIPPING_ADDRESS_UPDATE = """
    mutation CheckoutShippingAddressUpdate($id: ID!, $address: AddressInput!) {
        checkoutShippingAddressUpdate(id: $id, shippingAddress: $address) {
            checkout {
                id
                shippingAddress { firstName lastName streetAddress1 city country { code } }
            }
            errors { field message code }
        }
    }
    """
    
    CHECKOUT_BILLING_ADDRESS_UPDATE = """
    mutation CheckoutBillingAddressUpdate($id: ID!, $address: AddressInput!) {
        checkoutBillingAddressUpdate(id: $id, billingAddress: $address) {
            checkout {
                id
                billingAddress { firstName lastName streetAddress1 city country { code } }
            }
            errors { field message code }
        }
    }
    """
    
    CHECKOUT_DELIVERY_METHOD_UPDATE = """
    mutation CheckoutDeliveryMethodUpdate($id: ID!, $deliveryMethodId: ID!) {
        checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $deliveryMethodId) {
            checkout {
                id
                deliveryMethod {
                    ... on ShippingMethod { id name }
                }
            }
            errors { field message code }
        }
    }
    """
    
    CHECKOUT_COMPLETE = """
    mutation CheckoutComplete($id: ID!) {
        checkoutComplete(id: $id) {
            order {
                id
                number
                status
                total { gross { amount currency } }
            }
            errors { field message code }
        }
    }
    """
    
    # Admin mutations
    PRODUCT_CREATE = """
    mutation ProductCreate($input: ProductCreateInput!) {
        productCreate(input: $input) {
            product {
                id
                name
                slug
            }
            errors { field message code }
        }
    }
    """
    
    PRODUCT_UPDATE = """
    mutation ProductUpdate($id: ID!, $input: ProductInput!) {
        productUpdate(id: $id, input: $input) {
            product {
                id
                name
                description
            }
            errors { field message code }
        }
    }
    """
    
    PRODUCT_VARIANT_CREATE = """
    mutation ProductVariantCreate($input: ProductVariantCreateInput!) {
        productVariantCreate(input: $input) {
            productVariant {
                id
                name
                sku
            }
            errors { field message code }
        }
    }
    """
    
    TOKEN_CREATE = """
    mutation TokenCreate($email: String!, $password: String!) {
        tokenCreate(email: $email, password: $password) {
            token
            refreshToken
            errors { field message code }
        }
    }
    """

    @staticmethod
    def build_request(query: str, variables: Optional[dict] = None) -> dict:
        """Build a GraphQL request payload."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return payload
