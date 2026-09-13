"""
One function per provider "kind" that takes (api_key, model, messages) and
returns (reply_text, input_tokens, output_tokens).

`messages` is a provider-agnostic list, oldest first:
    [{"role": "user"|"assistant", "text": "...",
      "image_base64": "..." (optional), "image_mime": "..." (optional)}, ...]

Each call_* function converts that generic shape into its own API's format,
so bot.py never needs to know the differences between providers. Only the
final message in the list should carry an image - that's how a user
attaches a photo to their current question while still getting prior
turns as context.
"""

import requests

TIMEOUT = 60


def _openai_content(msg: dict):
    if msg.get("image_base64"):
        return [
            {"type": "text", "text": msg["text"]},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{msg['image_mime']};base64,{msg['image_base64']}"},
            },
        ]
    return msg["text"]


def call_openai_compatible(base_url: str, api_key: str, model: str, messages: list):
    payload_messages = [{"role": m["role"], "content": _openai_content(m)} for m in messages]
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": payload_messages},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _anthropic_content(msg: dict):
    if msg.get("image_base64"):
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": msg["image_mime"],
                    "data": msg["image_base64"],
                },
            },
            {"type": "text", "text": msg["text"]},
        ]
    return msg["text"]


def call_anthropic(base_url: str, api_key: str, model: str, messages: list):
    payload_messages = [{"role": m["role"], "content": _anthropic_content(m)} for m in messages]
    resp = requests.post(
        f"{base_url}/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={"model": model, "max_tokens": 1024, "messages": payload_messages},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []))
    usage = data.get("usage", {})
    return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def _google_parts(msg: dict):
    parts = []
    if msg.get("image_base64"):
        parts.append({"inline_data": {"mime_type": msg["image_mime"], "data": msg["image_base64"]}})
    parts.append({"text": msg["text"]})
    return parts


def call_google(base_url: str, api_key: str, model: str, messages: list):
    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": _google_parts(m)}
        for m in messages
    ]
    resp = requests.post(
        f"{base_url}/models/{model}:generateContent",
        params={"key": api_key},
        json={"contents": contents},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})
    return text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)


def call_bedrock(api_key: str, model: str, messages: list):
    """api_key here is 'ACCESS_KEY:SECRET_KEY:region' - see providers.py."""
    import boto3
    import json as jsonlib

    try:
        access_key, secret_key, region = api_key.split(":")
    except ValueError:
        raise ValueError("Bedrock key must be formatted as ACCESS_KEY:SECRET_KEY:region")
    client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    payload_messages = [{"role": m["role"], "content": _anthropic_content(m)} for m in messages]
    body = jsonlib.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": payload_messages,
        }
    )
    response = client.invoke_model(modelId=model, body=body)
    result = jsonlib.loads(response["body"].read())
    text = "".join(block.get("text", "") for block in result.get("content", []))
    usage = result.get("usage", {})
    return text, usage.get("input_tokens", 0), usage.get("output_tokens", 0)


def dispatch(provider_meta: dict, api_key: str, model: str, messages: list):
    """Returns (reply_text, input_tokens, output_tokens)."""
    kind = provider_meta["kind"]
    if kind == "openai_compatible":
        return call_openai_compatible(provider_meta["base_url"], api_key, model, messages)
    if kind == "anthropic":
        return call_anthropic(provider_meta["base_url"], api_key, model, messages)
    if kind == "google":
        return call_google(provider_meta["base_url"], api_key, model, messages)
    if kind == "bedrock":
        return call_bedrock(api_key, model, messages)
    raise ValueError(f"Unknown provider kind: {kind}")
    
