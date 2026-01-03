from typing import Optional

from langchain_core.tools import tool


# --- Tool 1: Identity Verification ---
@tool
def verify_identity(email: Optional[str] = None, phone: Optional[str] = None):
    """
    Verifies a user based on email or phone.
    Returns the 'customer_id' if found, or 'Not Found'.
    Call this when the user provides contact details.
    """
    # Mock user found
    user = {"id": "123", "name": "Siddique"}

    if user:
        # FIX: Use brackets ['key'] instead of dot notation .key
        return f"User Verified. customer_id: {user['id']}. Name: {user['name']}"
    return "User not found. Please ask for valid credentials."


# --- Tool 2: Validator ---
@tool
def validate_order_query(query_json: dict):
    """
    Validates a CubeJS query structure before execution.
    Always call this before executing a query.
    """
    # Note: Ensure 'meta_context' is available here or mocked
    is_valid, error = True, None
    return "Valid" if is_valid else f"Error: {error}"


# --- Tool 3: Executor ---
@tool
def execute_order_query(query_json: dict, customer_id: str):
    """
    Executes the query to fetch order data.
    REQUIRES a valid 'customer_id' retrieved from verify_identity.
    """
    if not customer_id or customer_id == "None":
        print("Authentication required. Please verify identity first.")
        return "Error: Authentication required. Please verify identity first."
    print("Executing query for query_json: %s", query_json)

    return [{"id": 123, "date": "2024-01-01", "total": 100}]
