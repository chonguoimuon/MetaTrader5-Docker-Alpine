swagger_config = {
    "swagger": "2.0",
    "info": {
        "title": "MetaTrader5 API",
        "description": "API documentation for MetaTrader5 Flask application.",
        "version": "1.0.0"
    },
    "basePath": "/",
    "https": True,
    "schemes": [
        "https"
    ],
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter 'Bearer {token}' where {token} is the fixed API token configured via the MT5_API_AUTH_TOKEN environment variable."
        }
    },
    # --- Global Security Requirement (Optional but Recommended) ---
    # This attempts to apply Bearer security to all endpoints by default.
    # Individual endpoints can override this if needed (e.g., health check).
    # Use the secure_swag_from helper for more reliable application per-endpoint.
    "security": [
        {
            "Bearer": []
        }
    ],    
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,  # Include all routes
            "model_filter": lambda tag: True,  # Include all models
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "headers": []
}

# --- Helper function to add security requirements to swag definitions ---
def secure_swag_from(specs):
    """
    Adds the Bearer security requirement to a Flasgger swag definition dictionary,
    unless the tag is 'Health'.
    It also ensures the 'security' key is correctly formatted as a list of dictionaries.
    """
    # Skip security for the 'Health' tag
    if "tags" in specs and "Health" in specs["tags"]:
        # Explicitly remove security if it exists for Health endpoint
        specs.pop("security", None)
        return specs

    # Apply Bearer security requirement to other endpoints
    # Ensure 'security' is a list containing the Bearer requirement dictionary
    specs["security"] = [{"Bearer": []}]
    return specs
