"""
Approximate USD prices per 1M tokens, for rough cost estimates only.

These change often and vary by exact model - treat /usage numbers as
ballpark, not a bill. Update PRICES as providers change their pricing.
Unlisted models simply show "cost unknown" instead of guessing.
"""

# (provider_id, model) -> (input $ per 1M tokens, output $ per 1M tokens)
PRICES = {
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("anthropic", "claude-sonnet-4-5"): (3.00, 15.00),
    ("google", "gemini-2.0-flash"): (0.10, 0.40),
    ("mistral", "mistral-large-latest"): (2.00, 6.00),
    ("together", "meta-llama/Llama-3.3-70B-Instruct-Turbo"): (0.88, 0.88),
    ("openrouter", "openai/gpt-4o-mini"): (0.15, 0.60),
}


def estimate_cost(provider_id: str, model: str, input_tokens: int, output_tokens: int):
    """Returns a USD float, or None if we don't have pricing for this model."""
    if provider_id == "free_trial":
        return 0.0
    prices = PRICES.get((provider_id, model))
    if not prices:
        return None
    in_price, out_price = prices
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price
