"""
One function per provider "kind" that takes (api_key, model, message) and
returns (reply_text, input_tokens, output_tokens). Token counts come from
each API's own usage field where available; if a provider doesn't report
them we return (0, 0) rather than guessing.
"""

import requests

TIMEOUT = 60


def call_openai_compatible(base_url: str, api_key: str, model: str, message: str):
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [{"role": "user", "content": message}]},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def call_anthropic(base_url: str, api_key: str, model: str, message: str):
    resp = requests.post(
        f"{base_url}/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": message}],
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []))
    usage = data.get("usage", {})
    return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def call_google(base_url: str, api_key: str, model: str, message: str):
    resp = requests.post(
        f"{base_url}/models/{model}:generateContent",
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": message}]}]},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})
    return text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)


def call_bedrock(api_key: str, model: str, message: str):
    """api_key here is 'ACCESS_KEY:SECRET_KEY:region' - see providers.py."""
    import boto3
    import json as jsonlib

    try:
        access_key, secret_key, region = api_key.split(":")
    except ValueError:
        raise ValueError(
            "Bedrock key must be formatted as ACCESS_KEY:SECRET_KEY:region"
        )
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    body = jsonlib.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": message}],
        }
    )
    response = client.invoke_model(modelId=model, body=body)
    result = jsonlib.loads(response["body"].read())
    text = "".join(block.get("text", "") for block in result.get("content", []))
    usage = result.get("usage", {})
    return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def dispatch(provider_meta: dict, api_key: str, model: str, message: str):
    """Returns (reply_text, input_tokens, output_tokens)."""
    kind = provider_meta["kind"]
    if kind == "openai_compatible":
        return call_openai_compatible(provider_meta["base_url"], api_key, model, message)
    if kind == "anthropic":
        return call_anthropic(provider_meta["base_url"], api_key, model, message)
    if kind == "google":
        return call_google(provider_meta["base_url"], api_key, model, message)
    if kind == "bedrock":
        return call_bedrock(api_key, model, message)
    raise ValueError(f"Unknown provider kind: {kind}")
