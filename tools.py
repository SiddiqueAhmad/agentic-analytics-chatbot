import json

# --- FIX 1: Correct imports from 'typing' ---
from typing import Any, Dict, Optional

from langchain_core.tools import tool


# --- Tool 1: Identity Verification ---
@tool
def verify_identity(email: Optional[str] = None, phone: Optional[str] = None) -> str:
    """
    Verifies a user based on email or phone.
    Returns the 'customer_id' if found, or 'Not Found'.
    Call this when the user provides contact details.
    """
    # Mock user found
    user = {"id": "123", "name": "Siddique"}

    if user:
        return f"User Verified. customer_id: {user['id']}. Name: {user['name']}"
    return "User not found. Please ask for valid credentials."


# --- Tool 2: Validator ---
# --- FIX 2: Fixed input type (Dict[str, Any]) and return type (str) ---
@tool
def validate_order_query(query_json: Dict[str, Any]) -> str:
    """
    Validates a CubeJS query structure before execution.
    Always call this before executing a query.
    """
    # Note: Ensure 'meta_context' is available here or mocked
    is_valid, error = True, None

    # The code returns a string, so the annotation must be '-> str'
    return "Valid" if is_valid else f"Error: {error}"


# --- Tool 3: Executor ---
# --- FIX 3: Fixed input type to Dict[str, Any] ---
@tool
def execute_order_query(query_json: Dict[str, Any], customer_id: str) -> str:
    """
    Executes the query to fetch order data.
    REQUIRES a valid 'customer_id' retrieved from verify_identity.
    """
    if not customer_id or customer_id == "None":
        print("Authentication required. Please verify identity first.")
        return "Error: Authentication required. Please verify identity first."

    # Use standard logging or print
    print(f"Executing query for query_json: {query_json}")

    return json.dumps([{"id": 123, "date": "2024-01-01", "total": 100}])
