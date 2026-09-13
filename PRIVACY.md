# Privacy Policy

_Last updated: [fill in date when you publish this]_

This bot lets you chat with AI providers of your choice (OpenAI, Anthropic,
Google Gemini, Mistral, and others) through Telegram. This policy explains
what data the bot stores, why, and how to remove it.

## Who operates this bot

This bot is operated by **[your name / handle]**. It is not affiliated
with Telegram, OpenAI, Anthropic, Google, or any of the AI providers it
connects to.

## What the bot stores

| Data | Stored how | Why |
|---|---|---|
| Your Telegram user ID | Plain SQLite | To know which settings/history belong to you |
| Your chosen AI provider | Plain SQLite | So the bot knows where to send your messages |
| Your API key (if you provide one) | **Encrypted** (Fernet) | To make requests to your chosen provider on your behalf |
| Conversation history | **Plain, unencrypted** SQLite | So the bot can remember context across messages |
| Token usage counts | Plain SQLite | To show you `/usage` estimates |
| Images/documents you send | Not stored — sent to the AI provider for that one reply, then discarded | Only your conversation history keeps the *text* of what was discussed, not the image/file itself |

**Your conversation history is not encrypted.** Don't send anything in
chat you wouldn't want readable by anyone with access to the server or
the database file (including the bot operator).

## Where your messages actually go

When you chat with the bot, your message (and recent conversation
history, if using unlimited memory) is sent directly to **the AI
provider you selected** — e.g. OpenAI, Anthropic, Google — using the API
key you supplied (or the bot operator's key, if you used the free trial
option). That provider's own privacy policy and data-handling practices
apply to that message once it's sent. This bot does not control or see
what those providers do with your data beyond returning a reply.

The bot operator can technically read anything in the bot's database,
including your conversation history and (if they chose to look) your
decrypted API key, since they control the encryption secret. This bot
is only as private as you trust its operator to be.

## Data retention

- Your provider choice, API key, and conversation history are kept
  until you delete them (see below) or the operator wipes the database.
- There is no automatic expiration.

## How to delete your data

- `/clear` — deletes your conversation history
- `/reset` — deletes your saved provider and API key
- To remove everything (including usage logs), contact the bot operator
  directly and ask them to delete your user ID from the database, or
  ask them to give you a `/deleteme` command if you're running your own
  copy of this bot's code (not included by default).

## Free trial usage

If you use the "✨ Try free" option, your messages are sent using the
**bot operator's** API key, not your own. The operator can see how many
free-trial messages you've sent (for rate-limiting) but not the content
beyond what's already in your conversation history as described above.

## Children's privacy

This bot is not directed at children and does not knowingly collect
data from anyone who does not meet Telegram's own minimum age
requirements.

## Changes to this policy

If how the bot stores or handles data changes, this document should be
updated accordingly. Since this is a self-hosted bot, the operator is
responsible for keeping this notice accurate to what the code actually
does.

## Contact

Questions about your data? Contact **[your contact info]**.
