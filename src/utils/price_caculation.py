"""Price calculation for Gemini API."""

GEMINI_PRICE: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.6},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00, "cached_content": 0.05},
    "gemini-3-pro-preview": {"input": 2.0, "output": 12.0, "cached_content": 0.2},
}


MILLION_TOKENS: int = 1000000


def get_base_model_name(endpoint_name: str) -> str:
    """Get the base model name from the endpoint name.

    Validates that the endpoint name starts with a known base model name.
    This allows endpoint variants like 'gemini-2.5-flash-001' while rejecting
    arbitrary strings that happen to contain a model name as a substring.

    Args:
        endpoint_name (str): The name of the endpoint.

    Returns:
        str: The base model name.

    Raises:
        ValueError: If the model is not found.
    """
    for base_name in GEMINI_PRICE:
        if endpoint_name.startswith(base_name):
            return base_name
    msg = f"Unknown model: {endpoint_name}"
    raise ValueError(msg)


def calculate_inference_price(
    model_name: str,
    total_input_token_count: int,
    cached_content_token_count: int,
    total_output_token_count: int,
) -> float:
    """Calculate the inference price for a given model.

    Args:
        model_name (str): The name of the model.
        total_input_token_count (int): The total number of input tokens.
        cached_content_token_count (int): The total number of cached content tokens.
        total_output_token_count (int): The total number of output tokens.

    Returns:
        float: The inference price.
    """
    base_model = get_base_model_name(endpoint_name=model_name)
    input_price = GEMINI_PRICE[base_model]["input"]
    output_price = GEMINI_PRICE[base_model]["output"]
    cached_content_price = GEMINI_PRICE[base_model].get("cached_content", 0)
    input_price_total = input_price * total_input_token_count / MILLION_TOKENS
    output_price_total = output_price * total_output_token_count / MILLION_TOKENS
    cached_content_price_total = cached_content_price * cached_content_token_count / MILLION_TOKENS
    return input_price_total + output_price_total + cached_content_price_total
