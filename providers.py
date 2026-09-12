"""
Provider registry.

Most providers on this list expose an OpenAI-compatible /chat/completions
endpoint - only the base_url and model name differ. Those all share the
"openai_compatible" kind below. Anthropic and Google Gemini use their own
request formats, and Amazon Bedrock authenticates with AWS credentials
instead of a single bearer token, so each of those gets its own kind.

To add a new OpenAI-compatible provider, just add one entry - no code changes.
"""

PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "kind": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "key_hint": "sk-...",
    },
    "anthropic": {
        "label": "Anthropic",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-5",
        "key_hint": "sk-ant-...",
    },
    "google": {
        "label": "Google Gemini",
        "kind": "google",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.0-flash",
        "key_hint": "AIza...",
    },
    "mistral": {
        "label": "Mistral",
        "kind": "openai_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "key_hint": "your Mistral API key",
    },
    "nvidia": {
        "label": "NVIDIA NIM",
        "kind": "openai_compatible",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.1-8b-instruct",
        "key_hint": "nvapi-...",
    },
    "ollama_cloud": {
        "label": "Ollama Cloud",
        "kind": "openai_compatible",
        "base_url": "https://ollama.com/v1",
        "default_model": "llama3.1",
        "key_hint": "your Ollama Cloud API key",
    },
    "openrouter": {
        "label": "OpenRouter",
        "kind": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "key_hint": "sk-or-...",
    },
    "together": {
        "label": "Together AI",
        "kind": "openai_compatible",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "key_hint": "your Together API key",
    },
    "tokenrouter": {
        "label": "TokenRouter",
        "kind": "openai_compatible",
        "base_url": "https://api.tokenrouter.io/v1",
        "default_model": "gpt-4o-mini",
        "key_hint": "your TokenRouter API key",
    },
    "alibaba": {
        "label": "Alibaba Coding (Qwen)",
        "kind": "openai_compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "key_hint": "sk-...",
    },
    "kimi": {
        "label": "Kimi for Coding",
        "kind": "openai_compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "key_hint": "sk-...",
    },
    "minimax": {
        "label": "MiniMax Coding",
        "kind": "openai_compatible",
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5s-chat",
        "key_hint": "your MiniMax API key",
    },
    "zai": {
        "label": "Zai Coding",
        "kind": "openai_compatible",
        "base_url": "https://api.z.ai/v1",
        "default_model": "glm-4",
        "key_hint": "your Zai API key",
    },
    "chutes": {
        "label": "Chutes",
        "kind": "openai_compatible",
        "base_url": "https://llm.chutes.ai/v1",
        "default_model": "default",
        "key_hint": "your Chutes API key",
    },
    "bedrock": {
        "label": "Amazon Bedrock",
        "kind": "bedrock",
        "default_model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "key_hint": "AWS_ACCESS_KEY_ID:AWS_SECRET_ACCESS_KEY:region (colon separated)",
    },
    "free_trial": {
        "label": "✨ Try free (no key needed)",
        "kind": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.2-3b-instruct:free",
        "requires_key": False,
    },
}

# Providers where requires_key isn't set default to True (normal case: user
# must paste their own key). Only free_trial uses a bot-owned key.
for _pid, _meta in PROVIDERS.items():
    _meta.setdefault("requires_key", True)


def provider_choices():
    """Return [(id, label), ...] for building the picker keyboard."""
    return [(pid, meta["label"]) for pid, meta in PROVIDERS.items()]
