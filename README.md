# Multi-Provider AI Telegram Bot

Users pick an AI provider (OpenAI, Anthropic, Google Gemini, Mistral,
OpenRouter, Together AI, NVIDIA NIM, Ollama Cloud, TokenRouter, several
"coding" providers, Amazon Bedrock, etc.) and paste their own API key.
The bot then routes their chat messages to that provider.

## How it works

- `providers.py` — registry of every supported provider: label, endpoint,
  default model. Most providers are OpenAI-compatible, so adding a new one
  is usually just a new entry here.
- `clients.py` — the actual HTTP calls, one function per API "shape"
  (OpenAI-compatible, Anthropic, Google, Bedrock).
- `storage.py` — SQLite table of `user_id -> provider, encrypted API key,
  model`. Keys are encrypted with Fernet using `STORAGE_SECRET`.
- `bot.py` — Telegram handlers: `/provider` shows the picker, the next
  text message from that user is treated as the API key, everything after
  that is forwarded to the chosen provider.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and
   copy the token it gives you.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN` from BotFather
   - `STORAGE_SECRET` — generate with:
     ```
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
4. `python bot.py`

## Bot commands

- `/start` or `/provider` — show the provider picker
- `/model <name>` — override the default model for your chosen provider
- `/usage` — see your token usage and an estimated cost per provider
- `/reset` — forget your saved provider and key

## Free trial (optional)

The picker includes "✨ Try free (no key needed)," which uses a free
OpenRouter model under **your** API key (set `FREE_TRIAL_API_KEY` in
`.env`, get one at openrouter.ai/keys) instead of asking the user for
one. Since it's your key being shared across everyone who picks this
option, `FREE_TRIAL_DAILY_LIMIT` (default 20 messages/user/day) caps
how much any one user can run up. Leave `FREE_TRIAL_API_KEY` unset to
disable the option entirely — the bot will tell users it's not
configured if they pick it.

## Usage tracking

Every reply logs input/output token counts per user in SQLite.
`/usage` sums them up and estimates a dollar cost using the small
pricing table in `pricing.py`. Those prices are hand-maintained and
will drift out of date — treat the number as a ballpark, and check
your provider's dashboard for the real bill. Free-trial usage always
shows as $0 since it's on the bot owner's tab, not the user's.

## Notes on specific providers

- **Amazon Bedrock** doesn't use a single API key — it needs an AWS access
  key, secret key, and region. When prompted for the "key," send it as
  `ACCESS_KEY:SECRET_KEY:region` (e.g. `AKIA...:wJalr...:us-east-1`).
- **OpenAI-compatible providers** (Mistral, OpenRouter, Together AI,
  NVIDIA NIM, Ollama Cloud, TokenRouter, Alibaba/Kimi/MiniMax/Zai Coding,
  Chutes) all just need a plain API key from that provider's dashboard.
- This bot intentionally does **not** support logging in with a ChatGPT
  Plus/Pro subscription (the "device code" OAuth flow used by OpenAI's
  Codex CLI). That flow authenticates a subscription for Codex
  specifically, not for third-party API access, so it isn't wired up
  here — use a real OpenAI API key instead (from platform.openai.com,
  billed separately from ChatGPT).

## Security notes

- API keys are encrypted at rest with Fernet (`STORAGE_SECRET`). Keep that
  secret safe — anyone with it can decrypt all stored keys.
- The bot deletes the user's message containing the pasted key immediately
  after reading it, so it doesn't sit in Telegram chat history.
- Consider running this bot yourself (not as a shared public bot) since
  every user is trusting you with their API key.
