#!/data/data/com.termux/files/usr/bin/bash
# Keeps the bot alive on Termux: if it crashes (e.g. a network drop),
# this restarts it automatically after a short pause instead of leaving
# it dead until you notice and rerun it by hand.

cd "$(dirname "$0")"

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting bot..."
    python bot.py
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot exited (code $?). Restarting in 5s..."
    sleep 5
done
