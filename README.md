# Screener Alerts Multi

A Cloudflare Worker-based application that automatically runs multiple stock screeners on Screener.in and sends localized Telegram alerts.

## Architecture

This project consists of two Cloudflare Workers that work together to bypass a known bug in Cloudflare's Python runtime (`NoGilError` during cron triggers):

1. **`screener-alerts-multi` (Python Worker - `worker.py`)**
   - The main application logic.
   - Hosts the Dashboard UI (HTML/JS/CSS).
   - Manages KV storage (Screeners, Settings, Telegram accounts, Previous results).
   - Exposes HTTP endpoints for the UI (`/api/settings`, `/api/screeners`, `/api/telegram`).
   - Handles the actual web scraping (Screener.in) and Telegram notification sending via `POST /api/trigger` (manual) and `POST /api/cron` (scheduled evaluation).

2. **`screener-alerts-multi-cron` (JS Worker - `wrapper.js`)**
   - A lightweight JavaScript worker designed purely as a timer.
   - Has a `* * * * *` (every 1 minute) cron trigger.
   - Pings the Python worker's `/api/cron` endpoint every 60 seconds.
   - **Why?** Cloudflare Python workers (Pyodide) currently crash with a `NoGilError` when their `scheduled` handlers are invoked natively. By moving the cron trigger to JS and pinging Python via HTTP, the Python worker executes safely.

## Setup & Deployment

1. **Deploy Main Python Worker**
   ```bash
   npx wrangler deploy
   ```

2. **Add Telegram Secrets**
   ```bash
   npx wrangler secret put TELEGRAM_TOKEN
   npx wrangler secret put TELEGRAM_CHAT_ID
   ```
   *Note: Additional Telegram accounts can be managed dynamically via the dashboard.*

3. **Deploy JS Cron Wrapper**
   ```bash
   npx wrangler deploy -c wrangler-cron.toml
   ```

## Troubleshooting

### NoGilError on Cron Triggers
**Issue:** If the Python worker (`worker.py`) is given a cron trigger directly in `wrangler.toml`, it will crash with `NoGilError: Attempted to use PyProxy when Python GIL not held` when the cron fires.
**Cause:** A bug in the Pyodide/workerd runtime regarding Global Interpreter Lock state during native `scheduled` events.
**Fix (Implemented):** The cron trigger was removed from `wrangler.toml`. A separate JS worker (`wrapper.js`) was deployed via `wrangler-cron.toml` to handle the `* * * * *` schedule, which simply POSTs to the Python `/api/cron` HTTP endpoint safely.

### Cloudflare Cron Trigger Limit
**Issue:** "You have exceeded the limit of 5 cron triggers."
**Fix:** The free tier of Cloudflare limits you to 5 cron triggers across your entire account. If you hit this deploying `wrangler-cron.toml`, you must delete an unused worker project on your Cloudflare dashboard (or remove its cron triggers) to free up a slot.

### Dashboard Settings Ignored
**Issue:** All screeners run every minute despite longer intervals configured in the dashboard UI.
**Cause:** The JS Wrapper might be pinging `/api/trigger` (manual override) instead of `/api/cron` (schedule evaluation).
**Fix:** Ensure `wrapper.js` hits the `/api/cron` endpoint, which parses KV settings and applies Global/Individual interval logic and time-of-day windows before running screeners.
