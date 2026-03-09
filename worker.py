from js import fetch, Headers
from pyodide.ffi import to_js
from workers import Response, WorkerEntrypoint
import json

# ─── Preconfigured screeners ───
SCREENERS = [
    {
        "id": "goat1",
        "name": "GOAT1 — Monthly Long Holdings",
        "url": "https://www.screener.in/screens/3525076/goat1/",
        "query": """Is not SME AND
Market Capitalization > 200 AND
Return on equity > 12 AND
Return on capital employed > 12 AND
Debt to equity < 1 AND
Pledged percentage < 15 AND
Cash from operations last year > 0 AND
Sales growth 3Years > 8 AND
Profit growth 3Years > 10 AND
YOY Quarterly sales growth > 8 AND
YOY Quarterly profit growth > 10 AND
OPM > 10 AND
OPM latest quarter > OPM preceding year quarter AND
Piotroski score > 5 AND
Price to Earning < Industry PE AND
Promoter holding > 35 AND
(Change in FII holding > 0 OR Change in DII holding > 0) AND
Current price > DMA 50 AND
Current price > DMA 200 AND
RSI > 45 AND
RSI < 78 AND
MACD > MACD Signal AND
Volume > Volume 1month average""",
        "enabled": True,
        "interval_minutes": 5,
        "start_time": "09:15",
        "end_time": "15:30",
        "start_date": "",
        "end_date": "",
        "last_run_epoch": 0,
    },
    {
        "id": "opus-tele",
        "name": "Opus-Tele — Momentum Screen",
        "url": "https://www.screener.in/screens/3535927/opus-tele/",
        "query": """Is not SME AND
Return over 1month > 0 AND
Return over 1week > 0 AND
Return over 1day > 0 AND
Return over 3months > 0 AND
Current price > DMA 50 AND
Current price > DMA 200 AND
DMA 50 > DMA 200 AND
DMA 50 > DMA 50 previous day AND
DMA 200 > DMA 200 previous day AND
RSI > 52 AND
RSI < 68 AND
MACD > MACD Signal AND
MACD > 0 AND
MACD > MACD Previous Day AND
MACD Signal > MACD Signal Previous Day AND
Volume > Volume 1month average AND
Current price > High price * 0.85 AND
Profit after tax > 0 AND
Return on capital employed > 15 AND
Return on equity > 12 AND
Debt to equity < 1 AND
Piotroski score > 5 AND
Sales growth 3Years > 8 AND
Profit growth 3Years > 5 AND
Cash from operations last year > 0 AND
Free cash flow last year > 0 AND
Pledged percentage < 10 AND
Promoter holding > 30 AND
Quick ratio > 0.8 AND
Price to Earning < 80 AND
YOY Quarterly sales growth > 10 AND
YOY Quarterly profit growth > 10""",
        "enabled": True,
        "interval_minutes": 5,
        "start_time": "09:15",
        "end_time": "15:30",
        "start_date": "",
        "end_date": "",
        "last_run_epoch": 0,
    },
]

DEFAULT_SETTINGS = {
    "enabled": True,
    "schedule_mode": "global",
    "interval_minutes": 5,
    "start_time": "09:15",
    "end_time": "15:30",
    "start_date": "",
    "end_date": "",
    "last_run": "",
    "last_run_epoch": 0,
    "total_runs": 0,
}


class Default(WorkerEntrypoint):

    async def fetch(self, request):
        url = str(request.url)
        method = str(request.method)

        # ── API: Global Settings ──
        if "/api/settings" in url and method == "GET":
            return self._json(await self._get_settings())

        if "/api/settings" in url and method == "POST":
            body = json.loads(str(await request.text()))
            cur = await self._get_settings()
            cur.update(body)
            await self.env.KV.put("settings", json.dumps(cur))
            return self._json({"ok": True, "settings": cur})

        # ── API: Screener routes (specific first) ──
        if "/api/screeners" in url and method == "GET":
            return self._json(await self._get_screeners())

        if "/api/screeners/delete" in url and method == "POST":
            body = json.loads(str(await request.text()))
            del_id = body.get("id", "")
            screeners = await self._get_screeners()
            screeners = [s for s in screeners if s["id"] != del_id]
            await self.env.KV.put("screeners", json.dumps(screeners))
            return self._json({"ok": True, "screeners": screeners})

        if "/api/screeners/toggle" in url and method == "POST":
            body = json.loads(str(await request.text()))
            toggle_id = body.get("id", "")
            screeners = await self._get_screeners()
            for s in screeners:
                if s["id"] == toggle_id:
                    s["enabled"] = not s.get("enabled", True)
                    break
            await self.env.KV.put("screeners", json.dumps(screeners))
            return self._json({"ok": True, "screeners": screeners})

        if "/api/screeners" in url and method == "POST":
            body = json.loads(str(await request.text()))
            screeners = await self._get_screeners()
            found = False
            for i, s in enumerate(screeners):
                if s["id"] == body.get("id"):
                    screeners[i].update(body)
                    found = True
                    break
            if not found:
                screeners.append(body)
            await self.env.KV.put("screeners", json.dumps(screeners))
            return self._json({"ok": True, "screeners": screeners})

        # ── API: Telegram Accounts ──
        if "/api/telegram/delete" in url and method == "POST":
            body = json.loads(str(await request.text()))
            del_idx = int(body.get("index", -1))
            accts = await self._get_telegram_accounts()
            if 0 <= del_idx < len(accts):
                accts.pop(del_idx)
            await self.env.KV.put("telegram_accounts", json.dumps(accts))
            return self._json({"ok": True, "accounts": accts})

        if "/api/telegram" in url and method == "GET":
            return self._json(await self._get_telegram_accounts())

        if "/api/telegram" in url and method == "POST":
            body = json.loads(str(await request.text()))
            accts = await self._get_telegram_accounts()
            accts.append({"name": body.get("name", ""), "token": body.get("token", ""), "chat_id": body.get("chat_id", "")})
            await self.env.KV.put("telegram_accounts", json.dumps(accts))
            return self._json({"ok": True, "accounts": accts})

        # ── API: Manual Trigger ──
        if "/api/trigger" in url and method == "POST":
            screeners = await self._get_screeners()
            count = 0
            for s in screeners:
                if s.get("enabled", True):
                    await self._run_single(s)
                    count += 1
            return self._json({"ok": True, "triggered": count})

        # CORS preflight
        if method == "OPTIONS":
            return Response("", headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            })

        return Response(DASHBOARD_HTML, headers={"Content-Type": "text/html"})

    async def scheduled(self, event, env, ctx):
        settings = await self._get_settings()
        if not settings.get("enabled", True):
            return

        from datetime import datetime, timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)
        now_epoch = int(now.timestamp())
        today = now.strftime("%Y-%m-%d")
        now_m = now.hour * 60 + now.minute

        mode = settings.get("schedule_mode", "global")
        screeners = await self._get_screeners()

        if mode == "global":
            # ── Global schedule: single gate for all ──
            interval = int(settings.get("interval_minutes", 1))
            last_epoch = int(settings.get("last_run_epoch", 0))
            if last_epoch and interval > 1:
                if (now_epoch - last_epoch) / 60 < interval:
                    return

            if not self._in_time_window(settings, now_m, today):
                return

            for s in screeners:
                if s.get("enabled", True):
                    await self._run_single(s)

            fresh = await self._get_settings()
            fresh["last_run"] = now.isoformat()
            fresh["last_run_epoch"] = now_epoch
            fresh["total_runs"] = fresh.get("total_runs", 0) + 1
            await self.env.KV.put("settings", json.dumps(fresh))

        else:
            # ── Individual schedule: per-screener gates ──
            ran_any = False
            for s in screeners:
                if not s.get("enabled", True):
                    continue

                s_interval = int(s.get("interval_minutes", 5))
                s_last = int(s.get("last_run_epoch", 0))
                if s_last and s_interval > 1:
                    if (now_epoch - s_last) / 60 < s_interval:
                        continue

                if not self._in_time_window(s, now_m, today):
                    continue

                await self._run_single(s)
                s["last_run_epoch"] = now_epoch
                ran_any = True

            if ran_any:
                await self.env.KV.put("screeners", json.dumps(screeners))
                fresh = await self._get_settings()
                fresh["last_run"] = now.isoformat()
                fresh["total_runs"] = fresh.get("total_runs", 0) + 1
                await self.env.KV.put("settings", json.dumps(fresh))

    # ─── Helpers ───

    def _in_time_window(self, cfg, now_m, today):
        try:
            sh, sm = map(int, cfg.get("start_time", "09:15").split(":"))
            eh, em = map(int, cfg.get("end_time", "15:30").split(":"))
            if now_m < sh * 60 + sm or now_m > eh * 60 + em:
                return False
        except:
            pass
        sd = cfg.get("start_date", "")
        ed = cfg.get("end_date", "")
        if sd and today < sd:
            return False
        if ed and today > ed:
            return False
        return True

    def _json(self, data):
        return Response(json.dumps(data), headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        })

    async def _get_settings(self):
        raw = await self.env.KV.get("settings")
        if raw:
            saved = json.loads(str(raw))
            m = dict(DEFAULT_SETTINGS)
            m.update(saved)
            return m
        return dict(DEFAULT_SETTINGS)

    async def _get_screeners(self):
        raw = await self.env.KV.get("screeners")
        if raw:
            return json.loads(str(raw))
        await self.env.KV.put("screeners", json.dumps(SCREENERS))
        return list(SCREENERS)

    async def _get_telegram_accounts(self):
        raw = await self.env.KV.get("telegram_accounts")
        if raw:
            return json.loads(str(raw))
        # Seed with both accounts on first run
        seed = [
            {"name": "Account 1", "token": str(self.env.TELEGRAM_TOKEN), "chat_id": str(self.env.TELEGRAM_CHAT_ID)},
        ]
        await self.env.KV.put("telegram_accounts", json.dumps(seed))
        return seed

    async def _send_all(self, text):
        accts = await self._get_telegram_accounts()
        for a in accts:
            await send_telegram(a["token"], a["chat_id"], text)

    async def _run_single(self, screener):
        sid = screener["id"]
        scr_url = screener["url"]
        scr_query = screener["query"]
        scr_name = screener.get("name", sid)
        try:
            get_headers = Headers.new(to_js({
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }))
            get_resp = await fetch(scr_url, method="GET", headers=get_headers)
            html = await get_resp.text()
            csrf_token = extract_csrf(str(html))

            set_cookie = str(get_resp.headers.get("set-cookie") or "")
            csrf_cookie = ""
            for part in set_cookie.split(";"):
                part = part.strip()
                if part.startswith("csrftoken="):
                    csrf_cookie = part
                    break

            body = f"csrfmiddlewaretoken={csrf_token}&query={url_encode(scr_query)}&order="
            post_headers = Headers.new(to_js({
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": scr_url,
                "Origin": "https://www.screener.in",
                "X-Requested-With": "XMLHttpRequest",
                "Cookie": csrf_cookie,
            }))
            post_resp = await fetch(scr_url, method="POST", body=body, headers=post_headers)
            result_html = str(await post_resp.text())

            headers_row, rows = parse_table(result_html)

            prev_key = f"prev_names_{sid}"
            prev_json = await self.env.KV.get(prev_key)
            prev_names = json.loads(str(prev_json)) if prev_json else []
            curr_names = [dict(zip(headers_row, r)).get("Name", "") for r in rows]

            msg = format_message(scr_name, headers_row, rows, curr_names, prev_names)
            await self._send_all(msg)

            await self.env.KV.put(prev_key, json.dumps(curr_names))

        except Exception as e:
            await self._send_all(f"❌ <b>[{scr_name}] Error:</b> {str(e)}")


# ─── Pure functions ───

def extract_csrf(html):
    for line in html.split("\n"):
        if "csrfmiddlewaretoken" in line:
            try: return line.split('value="')[1].split('"')[0]
            except: pass
    return ""

def url_encode(text):
    result = ""
    safe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~ "
    for ch in text:
        if ch in safe:
            result += "+" if ch == " " else ch
        else:
            result += "".join(f"%{b:02X}" for b in ch.encode())
    return result

def parse_table(html):
    headers, rows = [], []
    for part in html.split("<th")[1:]:
        cell = extract_between(part, ">", "</th>")
        while "<" in cell and ">" in cell:
            cell = cell[:cell.find("<")] + cell[cell.find(">")+1:]
        clean = " ".join(cell.split())
        if clean:
            headers.append(clean)
    tbody = extract_between(html, "<tbody>", "</tbody>")
    for tr in tbody.split("<tr")[1:]:
        cells = []
        for td in tr.split("<td")[1:]:
            inner = extract_between(td, ">", "</td>")
            if "<a" in inner:
                inner = extract_between(inner, ">", "</a>")
            while "<" in inner and ">" in inner:
                inner = inner[:inner.find("<")] + inner[inner.find(">")+1:]
            cells.append(" ".join(inner.split()))
        if cells:
            rows.append(cells)
    return headers, rows

def extract_between(s, start, end):
    i = s.find(start)
    if i == -1: return ""
    i += len(start)
    j = s.find(end, i)
    if j == -1: return ""
    return s[i:j]

def sign(val):
    try: return "🟢" if float(val) >= 0 else "🔴"
    except: return "⚪"

def format_message(screen_name, headers, rows, curr_names, prev_names):
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST).strftime("%d %b %Y, %I:%M:%S %p IST")
    entered = [n for n in curr_names if n not in prev_names]
    exited  = [n for n in prev_names if n not in curr_names]
    lines = [f"📊 <b>{screen_name}</b>", f"🕐 {now}", "━━━━━━━━━━━━━━━━"]
    if entered: lines.append(f"🆕 <b>NEW:</b> {', '.join(entered)}")
    if exited:  lines.append(f"🚪 <b>EXITED:</b> {', '.join(exited)}")
    if entered or exited: lines.append("━━━━━━━━━━━━━━━━")
    if not rows:
        lines.append("⚠️ <b>No stocks passed filters</b>")
        return "\n".join(lines)
    lines.append(f"✅ <b>{len(rows)} stock(s) passed</b>\n")
    skip = {"S.No.", "Is not SME"}
    for row in rows:
        d = dict(zip(headers, row))
        name = d.get("Name", "?")
        t = name.replace(" ","").replace(".","").replace("Inds","").upper()
        tag = "🆕 " if name in entered else ""
        block = f"{tag}🏢 <b>{name}</b>\n"
        items = []
        for h in headers:
            if h in skip or h == "Name":
                continue
            val = d.get(h, "")
            if not val:
                continue
            if "CMP" in h:
                items.append(f"💰 CMP: <b>₹{val}</b>")
            elif "return" in h.lower():
                items.append(f"{sign(val)} {h.replace(' %','')}: {val}%")
            elif "ROCE" in h:
                items.append(f"📈 ROCE: {val}%")
            elif "P/E" in h:
                items.append(f"P/E: {val}")
            elif "Mar Cap" in h:
                items.append(f"Mkt Cap: ₹{val} Cr")
            elif "NP Qtr" in h:
                items.append(f"💹 NP Qtr: ₹{val} Cr")
            elif "Profit Var" in h:
                items.append(f"Profit Var: {sign(val)}{val}%")
            elif "Sales Qtr" in h:
                items.append(f"Sales Qtr: ₹{val} Cr")
            elif "Sales Var" in h or "sales growth" in h.lower():
                items.append(f"Sales Var: {sign(val)}{val}%")
            elif "Div Yld" in h:
                items.append(f"Div: {val}%")
            elif "OPM" in h:
                items.append(f"OPM: {val}%")
            elif "%" in h:
                items.append(f"{h.replace(' %','')}: {val}%")
            else:
                items.append(f"{h}: {val}")
        for i in range(0, len(items), 2):
            pair = items[i:i+2]
            block += "   " + "  |  ".join(pair) + "\n"
        block += f"   🔗 <a href='https://www.screener.in/company/{t}/'>View</a>"
        lines.append(block)
        lines.append("─────────────────")
    return "\n".join(lines)

async def send_telegram(token, chat_id, text):
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text,
                       "parse_mode": "HTML", "disable_web_page_preview": True})
    hdrs = Headers.new(to_js({"Content-Type": "application/json"}))
    await fetch(url, method="POST", body=body, headers=hdrs)


# ─── Dashboard HTML ───

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Screener Alerts — Multi</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0a0f;--s1:#12121a;--s2:#1a1a26;--s3:#22222f;
  --bdr:#2a2a3a;--t1:#e4e4ed;--t2:#9494a8;--t3:#6a6a80;
  --acc:#6c5ce7;--acc2:#a29bfe;--accg:rgba(108,92,231,.15);
  --grn:#00d68f;--grng:rgba(0,214,143,.12);
  --red:#ff6b6b;--redg:rgba(255,107,107,.12);
  --r:12px;--rl:16px;
}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--t1);min-height:100vh}
.c{max-width:760px;margin:0 auto;padding:24px 16px}
.hdr{text-align:center;margin-bottom:28px;padding:28px 0 20px}
.hdr h1{font-size:22px;font-weight:700;letter-spacing:-.5px}
.hdr h1 span{color:var(--acc2)}
.hdr p{color:var(--t3);font-size:13px;margin-top:4px}

.sbar{display:flex;align-items:center;gap:10px;padding:14px 18px;background:var(--s1);border:1px solid var(--bdr);border-radius:var(--r);margin-bottom:16px}
.sdot{width:10px;height:10px;border-radius:50%;flex-shrink:0;animation:pulse 2s ease-in-out infinite}
.sdot.on{background:var(--grn);box-shadow:0 0 8px var(--grn)}.sdot.off{background:var(--red);box-shadow:0 0 8px var(--red);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.stxt{font-size:13px;color:var(--t2);flex:1}.stxt b{color:var(--t1);font-weight:600}
.sruns{font-size:12px;color:var(--t3)}

.cd{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--rl);padding:20px;margin-bottom:14px;transition:border-color .2s}
.cd:hover{border-color:var(--s3)}
.ct{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1.2px;color:var(--t3);margin-bottom:14px}

.trow{display:flex;align-items:center;justify-content:space-between;gap:16px}
.tlbl{font-size:15px;font-weight:500}.tsub{font-size:12px;color:var(--t3);margin-top:2px}
.tgl{position:relative;width:52px;height:28px;flex-shrink:0}
.tgl input{opacity:0;width:0;height:0}
.tgl .sl{position:absolute;inset:0;background:var(--s3);border-radius:14px;cursor:pointer;transition:.3s}
.tgl .sl:before{content:'';position:absolute;width:22px;height:22px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}
.tgl input:checked+.sl{background:var(--grn)}.tgl input:checked+.sl:before{transform:translateX(24px)}

.fg{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
.f{display:flex;flex-direction:column;gap:4px}
.f label{font-size:11px;font-weight:500;color:var(--t3);text-transform:uppercase;letter-spacing:.8px}
.f select,.f input{background:var(--s2);border:1px solid var(--bdr);border-radius:8px;padding:10px 12px;color:var(--t1);font-family:inherit;font-size:14px;outline:none;transition:.2s;width:100%}
.f select:focus,.f input:focus{border-color:var(--acc);box-shadow:0 0 0 3px var(--accg)}
.f select{cursor:pointer;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%236a6a80'%3E%3Cpath d='M6 8L1 3h10z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center}

.brow{display:flex;gap:10px;margin-top:16px}
.btn{flex:1;padding:12px;border:none;border-radius:var(--r);font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;transition:.2s;display:flex;align-items:center;justify-content:center;gap:6px}
.bp{background:var(--acc);color:#fff}.bp:hover{background:#5b4bd5;box-shadow:0 4px 16px var(--accg)}.bp:active{transform:scale(.97)}
.bs{background:var(--s2);color:var(--t1);border:1px solid var(--bdr)}.bs:hover{background:var(--s3)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-sm{padding:8px 14px;font-size:12px;flex:0}

/* Mode selector */
.mode-sel{display:flex;gap:0;border-radius:8px;overflow:hidden;border:1px solid var(--bdr);margin-bottom:16px}
.mode-btn{flex:1;padding:10px;text-align:center;font-size:13px;font-weight:600;cursor:pointer;background:var(--s2);color:var(--t3);border:none;font-family:inherit;transition:.2s}
.mode-btn.active{background:var(--acc);color:#fff}
.mode-btn:hover:not(.active){background:var(--s3);color:var(--t2)}

/* Disabled card */
.cd.disabled{opacity:.4;pointer-events:none}

/* Screener list */
.scr-item{background:var(--s2);border:1px solid var(--bdr);border-radius:var(--r);padding:14px 16px;margin-bottom:10px;transition:border-color .2s}
.scr-item:hover{border-color:var(--t3)}
.scr-top{display:flex;align-items:center;gap:12px}
.scr-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.scr-dot.on{background:var(--grn)}.scr-dot.off{background:var(--red)}
.scr-info{flex:1;min-width:0}
.scr-name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.scr-url{font-size:11px;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.scr-actions{display:flex;gap:6px;flex-shrink:0}
.scr-btn{background:var(--s3);border:1px solid var(--bdr);border-radius:6px;padding:6px 10px;font-size:11px;color:var(--t2);cursor:pointer;transition:.2s;font-family:inherit}
.scr-btn:hover{border-color:var(--t3);color:var(--t1)}
.scr-btn.del{color:var(--red);border-color:transparent}.scr-btn.del:hover{border-color:var(--red);background:var(--redg)}

/* Per-screener schedule (shown in individual mode) */
.scr-sched{margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr)}
.scr-sched .fg{margin-top:6px}

/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(4px);display:none;z-index:50;justify-content:center;align-items:center}
.modal-bg.show{display:flex}
.modal{background:var(--s1);border:1px solid var(--bdr);border-radius:var(--rl);padding:24px;width:90%;max-width:520px;max-height:80vh;overflow-y:auto}
.modal h2{font-size:16px;font-weight:700;margin-bottom:16px}
.modal .f{margin-bottom:12px}
.modal .f textarea{background:var(--s2);border:1px solid var(--bdr);border-radius:8px;padding:10px 12px;color:var(--t1);font-family:'Courier New',monospace;font-size:12px;outline:none;width:100%;min-height:120px;resize:vertical;transition:.2s}
.modal .f textarea:focus{border-color:var(--acc);box-shadow:0 0 0 3px var(--accg)}

.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(80px);padding:12px 24px;border-radius:var(--r);font-size:13px;font-weight:500;background:var(--s2);border:1px solid var(--bdr);color:var(--t1);box-shadow:0 8px 32px rgba(0,0,0,.4);transition:.4s cubic-bezier(.4,0,.2,1);z-index:100;white-space:nowrap}
.toast.show{transform:translateX(-50%) translateY(0)}
.toast.ok{border-color:var(--grn);background:linear-gradient(135deg,var(--s2),rgba(0,214,143,.08))}
.toast.err{border-color:var(--red);background:linear-gradient(135deg,var(--s2),rgba(255,107,107,.08))}

.spinner{width:16px;height:16px;border:2px solid transparent;border-top:2px solid currentColor;border-radius:50%;animation:spin .6s linear infinite;display:none}
@keyframes spin{to{transform:rotate(360deg)}}
.footer{text-align:center;padding:20px 0;font-size:11px;color:var(--t3)}.footer a{color:var(--acc2);text-decoration:none}
</style>
</head>
<body>
<div class="c">
  <div class="hdr">
    <h1>📊 <span>Screener Alerts</span> Multi</h1>
    <p>Cloudflare Worker • Multiple Screeners → Telegram</p>
  </div>

  <div class="sbar">
    <div class="sdot" id="dot"></div>
    <div class="stxt" id="stxt">Loading...</div>
    <div class="sruns" id="sruns"></div>
  </div>

  <!-- Power -->
  <div class="cd">
    <div class="ct">Global Power</div>
    <div class="trow">
      <div><div class="tlbl" id="pLbl">Cron Enabled</div><div class="tsub" id="pSub">All screeners</div></div>
      <label class="tgl"><input type="checkbox" id="enTgl" onchange="saveSets()"><span class="sl"></span></label>
    </div>
  </div>

  <!-- Schedule Mode Selector -->
  <div class="cd">
    <div class="ct">Schedule Mode</div>
    <div class="mode-sel">
      <button class="mode-btn" id="modeGlobal" onclick="setMode('global')">🌐 Global Schedule</button>
      <button class="mode-btn" id="modeIndiv" onclick="setMode('individual')">🎯 Per-Screener</button>
    </div>
    <div class="tsub" id="modeSub" style="text-align:center"></div>
  </div>

  <!-- Global Schedule (shown when mode=global) -->
  <div class="cd" id="globalSched">
    <div class="ct">Global Schedule (IST)</div>
    <div class="fg">
      <div class="f"><label>Interval</label>
        <select id="intSel" onchange="saveSets()">
          <option value="1">Every 1 min</option><option value="2">Every 2 min</option>
          <option value="3">Every 3 min</option><option value="5">Every 5 min</option>
          <option value="10">Every 10 min</option><option value="15">Every 15 min</option>
          <option value="30">Every 30 min</option><option value="60">Every 1 hour</option>
        </select>
      </div>
      <div class="f"><label>Last Run</label><input id="lrDisp" readonly style="color:var(--t3);cursor:default"></div>
    </div>
    <div class="fg" style="margin-top:12px">
      <div class="f"><label>Start Time</label><input type="time" id="sTime" onchange="saveSets()"></div>
      <div class="f"><label>End Time</label><input type="time" id="eTime" onchange="saveSets()"></div>
    </div>
    <div class="fg" style="margin-top:12px">
      <div class="f"><label>Start Date</label><input type="date" id="sDate" onchange="saveSets()"></div>
      <div class="f"><label>End Date</label><input type="date" id="eDate" onchange="saveSets()"></div>
    </div>
  </div>

  <!-- Screeners -->
  <div class="cd">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="ct" style="margin:0">Screeners</div>
      <button class="btn bp btn-sm" onclick="openModal()">+ Add</button>
    </div>
    <div id="scrList"></div>
  </div>

  <!-- Telegram Accounts -->
  <div class="cd">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
      <div class="ct" style="margin:0">Telegram Accounts</div>
      <button class="btn bp btn-sm" onclick="openTgModal()">+ Add</button>
    </div>
    <div id="tgList"></div>
  </div>

  <!-- Actions -->
  <div class="brow">
    <button class="btn bp" id="trigBtn" onclick="trigNow()">⚡ Run All Now <div class="spinner" id="trigSp"></div></button>
    <button class="btn bs" onclick="load()">🔄 Refresh</button>
  </div>

  <div class="footer"><a href="https://www.screener.in" target="_blank">screener.in ↗</a></div>
</div>

<!-- Add/Edit Modal -->
<div class="modal-bg" id="modalBg" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <h2 id="modalTitle">Add Screener</h2>
    <div class="f"><label>ID (slug, no spaces)</label><input id="mId" placeholder="my-screen"></div>
    <div class="f"><label>Name</label><input id="mName" placeholder="My Screen — Description"></div>
    <div class="f"><label>Screener.in URL</label><input id="mUrl" placeholder="https://www.screener.in/screens/..."></div>
    <div class="f"><label>Query</label><textarea id="mQuery" placeholder="Is not SME AND&#10;Market Capitalization > 200 AND&#10;..."></textarea></div>
    <div id="modalSchedSection">
      <div class="ct" style="margin-top:16px">Individual Schedule</div>
      <div class="fg">
        <div class="f"><label>Interval</label>
          <select id="mInterval">
            <option value="1">Every 1 min</option><option value="2">Every 2 min</option>
            <option value="3">Every 3 min</option><option value="5" selected>Every 5 min</option>
            <option value="10">Every 10 min</option><option value="15">Every 15 min</option>
            <option value="30">Every 30 min</option><option value="60">Every 1 hour</option>
          </select>
        </div>
        <div class="f"><label>&nbsp;</label></div>
      </div>
      <div class="fg">
        <div class="f"><label>Start Time</label><input type="time" id="mSTime" value="09:15"></div>
        <div class="f"><label>End Time</label><input type="time" id="mETime" value="15:30"></div>
      </div>
      <div class="fg">
        <div class="f"><label>Start Date</label><input type="date" id="mSDate"></div>
        <div class="f"><label>End Date</label><input type="date" id="mEDate"></div>
      </div>
    </div>
    <div class="brow">
      <button class="btn bp" onclick="saveScr()">💾 Save</button>
      <button class="btn bs" onclick="closeModal()">Cancel</button>
    </div>
  </div>
</div>

<!-- Telegram Modal -->
<div class="modal-bg" id="tgModalBg" onclick="if(event.target===this)closeTgModal()">
  <div class="modal">
    <h2>Add Telegram Account</h2>
    <div class="f"><label>Name (label)</label><input id="tgName" placeholder="My Account"></div>
    <div class="f"><label>Bot Token</label><input id="tgToken" placeholder="1234567890:AABBC..."></div>
    <div class="f"><label>Chat ID</label><input id="tgChatId" placeholder="1234567890"></div>
    <div class="brow">
      <button class="btn bp" onclick="saveTg()">💾 Save</button>
      <button class="btn bs" onclick="closeTgModal()">Cancel</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const A=location.origin;
let _sets={},_scrs=[],_mode='global',_tg=[];

const INTERVAL_OPTS = {'1':'1 min','2':'2 min','3':'3 min','5':'5 min','10':'10 min','15':'15 min','30':'30 min','60':'1 hr'};

async function load(){
  try{
    const[sr,sc,tg]=await Promise.all([fetch(A+'/api/settings').then(r=>r.json()),fetch(A+'/api/screeners').then(r=>r.json()),fetch(A+'/api/telegram').then(r=>r.json())]);
    _sets=sr;_scrs=sc;_tg=tg;_mode=sr.schedule_mode||'global';
    document.getElementById('enTgl').checked=sr.enabled;
    document.getElementById('intSel').value=String(sr.interval_minutes||5);
    document.getElementById('sTime').value=sr.start_time||'09:15';
    document.getElementById('eTime').value=sr.end_time||'15:30';
    document.getElementById('sDate').value=sr.start_date||'';
    document.getElementById('eDate').value=sr.end_date||'';
    updMode();updStatus(sr);renderScrs(sc);renderTg(tg);
  }catch(e){toast('Failed to load','err')}
}

function updMode(){
  document.getElementById('modeGlobal').className='mode-btn'+(_mode==='global'?' active':'');
  document.getElementById('modeIndiv').className='mode-btn'+(_mode==='individual'?' active':'');
  const gs=document.getElementById('globalSched');
  if(_mode==='global'){
    gs.classList.remove('disabled');
    document.getElementById('modeSub').textContent='One schedule controls all screeners';
  }else{
    gs.classList.add('disabled');
    document.getElementById('modeSub').textContent='Each screener has its own schedule';
  }
  renderScrs(_scrs);
}

function setMode(m){
  _mode=m;updMode();
  saveSets();
}

function updStatus(s){
  const d=document.getElementById('dot'),t=document.getElementById('stxt'),r=document.getElementById('sruns');
  const en=_scrs.filter(x=>x.enabled!==false).length;
  if(s.enabled){
    d.className='sdot on';
    const modeStr=_mode==='global'?'Global':'Individual';
    t.innerHTML=`<b>Active</b> · ${modeStr} · ${en} screener(s)`;
  }else{
    d.className='sdot off';t.innerHTML='<b>Paused</b> · All cron triggers skipped';
  }
  r.innerHTML=s.total_runs?'🔢 '+s.total_runs+' runs':'';
  const lr=document.getElementById('lrDisp');
  if(s.last_run){try{lr.value=new Date(s.last_run).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',second:'2-digit',day:'2-digit',month:'short',year:'numeric',hour12:true})}catch(e){lr.value=s.last_run}}
  else lr.value='Never';
}

function renderScrs(list){
  const el=document.getElementById('scrList');
  if(!list.length){el.innerHTML='<div style="text-align:center;padding:24px;color:var(--t3)">No screeners. Click + Add.</div>';return}
  el.innerHTML=list.map(s=>{
    let schedHtml='';
    if(_mode==='individual'){
      const iv=s.interval_minutes||5;
      const st=s.start_time||'09:15';
      const et=s.end_time||'15:30';
      schedHtml=`<div class="scr-sched">
        <div class="fg">
          <div class="f"><label>Interval</label>
            <select onchange="updScrSched('${s.id}','interval_minutes',parseInt(this.value))">
              ${Object.entries(INTERVAL_OPTS).map(([v,l])=>`<option value="${v}"${parseInt(v)===iv?' selected':''}>${l}</option>`).join('')}
            </select>
          </div>
          <div class="f"><label>Window</label>
            <input type="text" value="${st} – ${et}" readonly style="color:var(--t3);cursor:default;font-size:12px">
          </div>
        </div>
        <div class="fg">
          <div class="f"><label>Start Time</label><input type="time" value="${st}" onchange="updScrSched('${s.id}','start_time',this.value)"></div>
          <div class="f"><label>End Time</label><input type="time" value="${et}" onchange="updScrSched('${s.id}','end_time',this.value)"></div>
        </div>
        <div class="fg">
          <div class="f"><label>Start Date</label><input type="date" value="${s.start_date||''}" onchange="updScrSched('${s.id}','start_date',this.value)"></div>
          <div class="f"><label>End Date</label><input type="date" value="${s.end_date||''}" onchange="updScrSched('${s.id}','end_date',this.value)"></div>
        </div>
      </div>`;
    }
    return `<div class="scr-item">
      <div class="scr-top">
        <div class="scr-dot ${s.enabled!==false?'on':'off'}"></div>
        <div class="scr-info">
          <div class="scr-name">${esc(s.name||s.id)}</div>
          <div class="scr-url">${esc(s.url||'')}${_mode==='individual'?' · every '+(s.interval_minutes||5)+'m':''}</div>
        </div>
        <div class="scr-actions">
          <button class="scr-btn" onclick="toggleScr('${s.id}')">${s.enabled!==false?'⏸ Pause':'▶ Resume'}</button>
          <button class="scr-btn" onclick="editScr('${s.id}')">✏️</button>
          <button class="scr-btn del" onclick="delScr('${s.id}')">🗑</button>
        </div>
      </div>
      ${schedHtml}
    </div>`;
  }).join('');
}

let _timer;
async function saveSets(){
  clearTimeout(_timer);_timer=setTimeout(async()=>{
    try{
      const p={enabled:document.getElementById('enTgl').checked,
        schedule_mode:_mode,
        interval_minutes:parseInt(document.getElementById('intSel').value),
        start_time:document.getElementById('sTime').value,end_time:document.getElementById('eTime').value,
        start_date:document.getElementById('sDate').value,end_date:document.getElementById('eDate').value};
      const r=await fetch(A+'/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
      const d=await r.json();if(d.ok){_sets=d.settings;updStatus(d.settings);toast('Settings saved ✓','ok')}
    }catch(e){toast('Save failed','err')}
  },300);
}

async function updScrSched(id,field,val){
  const s=_scrs.find(x=>x.id===id);
  if(!s)return;
  s[field]=val;
  try{
    const r=await fetch(A+'/api/screeners',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)});
    const d=await r.json();
    if(d.ok){_scrs=d.screeners;toast('Schedule saved ✓','ok')}
  }catch(e){toast('Failed','err')}
}

async function toggleScr(id){
  try{const r=await fetch(A+'/api/screeners/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const d=await r.json();if(d.ok){_scrs=d.screeners;renderScrs(_scrs);updStatus(_sets);toast('Toggled ✓','ok')}}catch(e){toast('Failed','err')}
}
async function delScr(id){
  if(!confirm('Delete this screener?'))return;
  try{const r=await fetch(A+'/api/screeners/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  const d=await r.json();if(d.ok){_scrs=d.screeners;renderScrs(_scrs);updStatus(_sets);toast('Deleted ✓','ok')}}catch(e){toast('Failed','err')}
}

function openModal(s){
  document.getElementById('modalTitle').textContent=s?'Edit Screener':'Add Screener';
  document.getElementById('mId').value=s?s.id:'';document.getElementById('mId').readOnly=!!s;
  document.getElementById('mName').value=s?s.name:'';
  document.getElementById('mUrl').value=s?s.url:'';
  document.getElementById('mQuery').value=s?s.query:'';
  document.getElementById('mInterval').value=String(s?s.interval_minutes||5:5);
  document.getElementById('mSTime').value=s?s.start_time||'09:15':'09:15';
  document.getElementById('mETime').value=s?s.end_time||'15:30':'15:30';
  document.getElementById('mSDate').value=s?s.start_date||'':'';
  document.getElementById('mEDate').value=s?s.end_date||'':'';
  document.getElementById('modalBg').classList.add('show');
}
function closeModal(){document.getElementById('modalBg').classList.remove('show')}
function editScr(id){const s=_scrs.find(x=>x.id===id);if(s)openModal(s)}

async function saveScr(){
  const o={id:document.getElementById('mId').value.trim(),name:document.getElementById('mName').value.trim(),
    url:document.getElementById('mUrl').value.trim(),query:document.getElementById('mQuery').value.trim(),enabled:true,
    interval_minutes:parseInt(document.getElementById('mInterval').value),
    start_time:document.getElementById('mSTime').value,end_time:document.getElementById('mETime').value,
    start_date:document.getElementById('mSDate').value,end_date:document.getElementById('mEDate').value,
    last_run_epoch:0};
  if(!o.id||!o.url||!o.query){toast('Fill all fields','err');return}
  // Preserve last_run_epoch if editing
  const existing=_scrs.find(x=>x.id===o.id);
  if(existing)o.last_run_epoch=existing.last_run_epoch||0;
  try{const r=await fetch(A+'/api/screeners',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});
  const d=await r.json();if(d.ok){_scrs=d.screeners;renderScrs(_scrs);closeModal();toast('Saved ✓','ok')}}catch(e){toast('Failed','err')}
}

async function trigNow(){
  const b=document.getElementById('trigBtn'),sp=document.getElementById('trigSp');b.disabled=true;sp.style.display='inline-block';
  try{const r=await fetch(A+'/api/trigger',{method:'POST'});const d=await r.json();toast('⚡ Triggered '+d.triggered+' screener(s)!','ok');setTimeout(load,2000)}
  catch(e){toast('Failed','err')}finally{b.disabled=false;sp.style.display='none'}
}

// ── Telegram accounts ──
function renderTg(list){
  const el=document.getElementById('tgList');
  if(!list.length){el.innerHTML='<div style="text-align:center;padding:24px;color:var(--t3)">No accounts. Click + Add.</div>';return}
  el.innerHTML=list.map((a,i)=>`
    <div class="scr-item">
      <div class="scr-top">
        <div class="scr-dot on"></div>
        <div class="scr-info">
          <div class="scr-name">📱 ${esc(a.name||'Account '+(i+1))}</div>
          <div class="scr-url">Chat: ${esc(a.chat_id)} · Bot: ${esc(a.token.substring(0,12))}...</div>
        </div>
        <div class="scr-actions">
          <button class="scr-btn del" onclick="delTg(${i})">🗑</button>
        </div>
      </div>
    </div>`).join('');
}
function openTgModal(){document.getElementById('tgName').value='';document.getElementById('tgToken').value='';document.getElementById('tgChatId').value='';document.getElementById('tgModalBg').classList.add('show')}
function closeTgModal(){document.getElementById('tgModalBg').classList.remove('show')}
async function saveTg(){
  const o={name:document.getElementById('tgName').value.trim(),token:document.getElementById('tgToken').value.trim(),chat_id:document.getElementById('tgChatId').value.trim()};
  if(!o.token||!o.chat_id){toast('Fill token and chat ID','err');return}
  try{const r=await fetch(A+'/api/telegram',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});
  const d=await r.json();if(d.ok){_tg=d.accounts;renderTg(_tg);closeTgModal();toast('Account added ✓','ok')}}catch(e){toast('Failed','err')}
}
async function delTg(idx){
  if(!confirm('Remove this Telegram account?'))return;
  try{const r=await fetch(A+'/api/telegram/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:idx})});
  const d=await r.json();if(d.ok){_tg=d.accounts;renderTg(_tg);toast('Removed ✓','ok')}}catch(e){toast('Failed','err')}
}

function toast(m,t){const e=document.getElementById('toast');e.textContent=m;e.className='toast '+t+' show';setTimeout(()=>e.className='toast',2500)}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

load();
</script>
</body>
</html>"""
