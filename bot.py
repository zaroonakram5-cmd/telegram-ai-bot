"""
Telegram bot: user picks a provider from an inline keyboard, pastes their
own API key in a DM, then every message they send gets forwarded to that
provider and the reply is sent back.

Run:
    python bot.py

Requires TELEGRAM_BOT_TOKEN and STORAGE_SECRET in your environment (see .env.example).
"""

import base64
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import storage
from clients import dispatch
from pricing import estimate_cost
from providers import PROVIDERS, provider_choices

FREE_TRIAL_DAILY_LIMIT = int(os.environ.get("FREE_TRIAL_DAILY_LIMIT", "20"))


class _PingHandler(BaseHTTPRequestHandler):
    """Bare-minimum HTTP responder so Render's free Web Service tier sees
    this as a live service. An external pinger (e.g. UptimeRobot) hitting
    this URL every few minutes keeps Render from spinning it down."""

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # keep the bot's own logs uncluttered


def _start_ping_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _PingHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"Ping server listening on port {port}")

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Users land here after tapping a provider button, while we wait for them
# to paste their key. Cleared once the key is saved.
AWAITING_KEY: set[int] = set()


def provider_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"provider:{pid}")]
        for pid, label in provider_choices()
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Pick an AI provider to use. You'll paste your own API key for it next.",
        reply_markup=provider_keyboard(),
    )


async def provider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose a provider:", reply_markup=provider_keyboard())


async def on_provider_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # Retry the Telegram calls a few times - on a flaky mobile connection,
    # a single timeout here is what causes the button to spin forever.
    for attempt in range(3):
        try:
            await query.answer()
            break
        except Exception as e:
            logger.warning(f"query.answer() failed (attempt {attempt + 1}/3): {e}")
            if attempt == 2:
                return  # give up quietly rather than raising

    provider_id = query.data.split(":", 1)[1]
    user_id = query.from_user.id

    storage.set_provider(user_id, provider_id)
    meta = PROVIDERS[provider_id]

    if not meta["requires_key"]:
        text = (
            f"Selected: {meta['label']}\n\n"
            f"You're ready to go — no key needed. Limited to "
            f"{FREE_TRIAL_DAILY_LIMIT} messages/day. Just send me a message.\n\n"
            "Want a stronger model or no daily limit? Use /provider to pick "
            "one and paste your own API key instead."
        )
    else:
        AWAITING_KEY.add(user_id)
        text = (
            f"Selected: {meta['label']}\n\n"
            f"Now send me your API key for {meta['label']} as a message "
            f"(format: {meta['key_hint']}).\n\n"
            "I'll delete your message right after reading it, and it's stored encrypted."
        )

    for attempt in range(3):
        try:
            await query.edit_message_text(text)
            return
        except Exception as e:
            logger.warning(f"edit_message_text failed (attempt {attempt + 1}/3): {e}")
            if attempt == 2:
                # Last resort: send as a new message instead of editing.
                try:
                    await context.bot.send_message(chat_id=user_id, text=text)
                except Exception:
                    logger.exception("Failed to deliver provider-selection message")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler - logs failures without crashing the polling loop."""
    logger.error(f"Update {update} caused error: {context.error}")


async def _resolve_call_key(update: Update, provider_id: str, api_key: str, meta: dict):
    """Returns the API key to use for this call, or None (and replies with
    an explanation) if the user can't chat right now."""
    user_id = update.effective_user.id
    if meta["requires_key"]:
        if not api_key:
            await update.message.reply_text(
                f"You picked {meta['label']} but haven't sent a key yet. "
                "Use /provider to try again."
            )
            return None
        return api_key

    used_today = storage.get_free_trial_count_today(user_id)
    if used_today >= FREE_TRIAL_DAILY_LIMIT:
        await update.message.reply_text(
            f"You've used today's {FREE_TRIAL_DAILY_LIMIT} free messages. "
            "Come back tomorrow, or use /provider to add your own API key "
            "for unlimited use."
        )
        return None
    call_key = os.environ.get("FREE_TRIAL_API_KEY")
    if not call_key:
        await update.message.reply_text(
            "Free trial isn't configured on this bot right now. "
            "Use /provider to add your own API key instead."
        )
        return None
    return call_key


async def _handle_chat_turn(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    image_base64: str = None,
    image_mime: str = None,
):
    """Shared path for text messages, photos, and documents: builds the
    conversation history, calls the provider, stores the turn, replies."""
    user_id = update.effective_user.id

    provider_id, api_key, model = storage.get_config(user_id)
    if not provider_id:
        await update.message.reply_text(
            "You haven't set up a provider yet. Use /provider to pick one."
        )
        return

    meta = PROVIDERS[provider_id]
    call_key = await _resolve_call_key(update, provider_id, api_key, meta)
    if not call_key:
        return

    model = model or meta["default_model"]

    # Prior turns give the model conversation context; only the newest
    # message carries an image, matching how the providers expect it.
    history = storage.get_history(user_id)
    messages = [{"role": h["role"], "text": h["text"]} for h in history]
    messages.append(
        {
            "role": "user",
            "text": text,
            "image_base64": image_base64,
            "image_mime": image_mime,
        }
    )

    await context.bot.send_chat_action(chat_id=user_id, action="typing")
    try:
        reply, input_tokens, output_tokens = dispatch(meta, call_key, model, messages)
    except Exception as e:
        logger.exception("Provider call failed")
        await update.message.reply_text(f"Error from {meta['label']}: {e}")
        return

    storage.log_usage(user_id, provider_id, model, input_tokens, output_tokens)
    if not meta["requires_key"]:
        storage.increment_free_trial_count(user_id)

    # Store the turn (image itself isn't kept in history - only its text -
    # so old images don't get re-sent to the provider on every later turn).
    storage.add_message(user_id, "user", text)
    storage.add_message(user_id, "assistant", reply)

    await update.message.reply_text(reply)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    if user_id in AWAITING_KEY:
        provider_id, _, _ = storage.get_config(user_id)
        storage.set_api_key(user_id, text.strip())
        AWAITING_KEY.discard(user_id)
        try:
            await update.message.delete()  # scrub the key from chat history
        except Exception:
            pass
        meta = PROVIDERS[provider_id]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Key saved for {meta['label']}. Send me a message, photo, or text file any time to chat.\n"
            f"Use /provider to switch, /model to set a model, /usage for token cost, /clear to forget the conversation so far.",
        )
        return

    await _handle_chat_turn(update, context, text)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]  # largest available size
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    image_base64 = base64.b64encode(photo_bytes).decode()
    caption = update.message.caption or "Describe this image."
    await _handle_chat_turn(update, context, caption, image_base64=image_base64, image_mime="image/jpeg")


# Document types we can read as plain text and hand to the model as context.
TEXT_MIME_PREFIXES = ("text/",)
TEXT_MIME_EXACT = {"application/json", "application/xml", "application/x-yaml"}


async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    mime = doc.mime_type or ""
    is_text = mime.startswith(TEXT_MIME_PREFIXES) or mime in TEXT_MIME_EXACT

    if not is_text:
        await update.message.reply_text(
            f"I can read plain text files (.txt, .md, .json, .csv, etc.) but not "
            f"{mime or 'this file type'} yet - PDFs and other binary formats aren't "
            f"supported. Try pasting the relevant text directly instead."
        )
        return

    file = await doc.get_file()
    file_bytes = await file.download_as_bytearray()
    try:
        file_text = file_bytes.decode("utf-8", errors="replace")
    except Exception:
        await update.message.reply_text("Couldn't read that file as text.")
        return

    # Cap how much of a huge file we forward, to avoid blowing the context
    # window and running up cost on one message.
    MAX_CHARS = 8000
    if len(file_text) > MAX_CHARS:
        file_text = file_text[:MAX_CHARS] + "\n\n[...truncated...]"

    caption = update.message.caption or "Here's a document. Take a look."
    combined = f"{caption}\n\n--- File: {doc.file_name} ---\n{file_text}"
    await _handle_chat_turn(update, context, combined)


async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    provider_id, _, _ = storage.get_config(user_id)
    if not provider_id:
        await update.message.reply_text("Pick a provider first with /provider.")
        return
    if not context.args:
        meta = PROVIDERS[provider_id]
        await update.message.reply_text(
            f"Current default model: {meta['default_model']}\n"
            f"Set one with: /model <model-name>"
        )
        return
    storage.set_model(user_id, context.args[0])
    await update.message.reply_text(f"Model set to {context.args[0]}")


async def usage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = storage.get_usage_summary(user_id)
    if not rows:
        await update.message.reply_text("No usage yet — send a message first.")
        return

    lines = ["Your usage so far:\n"]
    total_cost = 0.0
    any_unknown = False
    for provider_id, model, in_tok, out_tok, count in rows:
        label = PROVIDERS.get(provider_id, {}).get("label", provider_id)
        cost = estimate_cost(provider_id, model, in_tok, out_tok)
        if cost is None:
            cost_str = "cost unknown"
            any_unknown = True
        else:
            cost_str = f"~${cost:.4f}"
            total_cost += cost
        lines.append(
            f"• {label} ({model}): {count} messages, "
            f"{in_tok:,} in / {out_tok:,} out tokens — {cost_str}"
        )

    lines.append(f"\nEstimated total: ~${total_cost:.4f}")
    if any_unknown:
        lines.append("(some models aren't in the pricing table, so totals may be incomplete)")
    else:
        lines.append("(rough estimate based on approximate public pricing — not a bill)")

    await update.message.reply_text("\n".join(lines))


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_user(update.effective_user.id)
    await update.message.reply_text("Cleared your provider and API key.")


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.clear_history(update.effective_user.id)
    await update.message.reply_text("Conversation memory cleared - starting fresh.")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your environment or .env file")

    storage.init_db()
    _start_ping_server()

    # Force IPv4: many mobile/carrier networks (common on Android/Termux)
    # have broken or unroutable IPv6, which makes httpx hang trying the
    # IPv6 address before falling back — this skips that entirely.
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        httpx_kwargs={"transport": httpx.AsyncHTTPTransport(local_address="0.0.0.0")},
    )

    app = Application.builder().token(token).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("provider", provider_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("usage", usage_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CallbackQueryHandler(on_provider_chosen, pattern=r"^provider:"))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
    
