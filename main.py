from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import httpx
import xml.etree.ElementTree as ET
import fear_and_greed

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── VIX ──────────────────────────────────────────────────────────────────────

@app.get("/vix")
def get_vix():
    vix = yf.Ticker("^VIX")
    hist = vix.history(period="1mo")
    current = float(hist["Close"].iloc[-1])
    prev    = float(hist["Close"].iloc[-2])
    change  = current - prev
    history = [
        {"date": str(d.date()), "close": float(v)}
        for d, v in zip(hist.index, hist["Close"])
    ]
    return {"current": current, "prev": prev, "change": change, "history": history}

# ── Fear & Greed ──────────────────────────────────────────────────────────────

@app.get("/fear-greed")
async def get_fear_greed():
    url = "https://production.dataviz.cnn.io/index/feargreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.cnn.com",
        "Referer": "https://www.cnn.com/markets/fear-and-greed"
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # The API returns a "fear_and_greed" object with current and historical data
            current_data = data.get("fear_and_greed", {})
            current_val = round(current_data.get("score", 0))
            current_label = current_data.get("rating", "Unknown").capitalize()

            # Get historical for "previous value" (yesterday's close)
            # The "fear_and_greed_historical" list contains past data points
            hist_list = data.get("fear_and_greed_historical", {}).get("data", [])
            prev_val = round(hist_list[-2]["y"]) if len(hist_list) >= 2 else current_val

            return {
                "value": current_val,
                "prev_value": prev_val,
                "label": current_label,
            }
    except Exception as e:
        return {
            "value": None,
            "prev_value": None,
            "label": "Unavailable",
            "error": f"CNN API Error: {str(e)}",
        }

# ── CNBC Live News (RSS) ──────────────────────────────────────────────────────

CNBC_RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
]

@app.get("/news")
async def get_news():
    items = []
    async with httpx.AsyncClient(timeout=10) as client:
        for feed_url in CNBC_RSS_FEEDS:
            try:
                resp = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:5]:
                    title   = item.findtext("title") or ""
                    desc    = item.findtext("description") or ""
                    link    = item.findtext("link") or ""
                    pub     = item.findtext("pubDate") or ""
                    if title:
                        items.append({
                            "title":   title.strip(),
                            "body":    desc.strip()[:200],
                            "link":    link.strip(),
                            "pubDate": pub.strip(),
                            "source":  "CNBC"
                        })
            except Exception as e:
                items.append({
                    "title": f"Feed error: {str(e)}",
                    "body": "", "link": "", "pubDate": "", "source": "error"
                })

    seen, unique = set(), []
    for it in items:
        if it["title"] not in seen:
            seen.add(it["title"])
            unique.append(it)

    return {"items": unique[:15], "count": len(unique)}

# ── Sentiment Summary ─────────────────────────────────────────────────────────

@app.get("/sentiment")
def get_sentiment():
    try:
        vix_data = get_vix()
        fg_data  = get_fear_greed()
        vix_val  = vix_data["current"]
        fg_val   = fg_data["value"]
        fg_label = fg_data["label"]

        if vix_val < 15:
            vix_sentiment = "extremely calm"
        elif vix_val < 20:
            vix_sentiment = "low volatility"
        elif vix_val < 25:
            vix_sentiment = "moderate volatility"
        elif vix_val < 30:
            vix_sentiment = "elevated volatility"
        else:
            vix_sentiment = "high fear / crisis-level volatility"

        if fg_val <= 25:
            fg_advice = "historically a contrarian buy signal, but caution is warranted"
        elif fg_val <= 45:
            fg_advice = "investors are risk-averse; defensive positioning is common"
        elif fg_val <= 55:
            fg_advice = "market is balanced with no clear directional bias"
        elif fg_val <= 75:
            fg_advice = "bullish momentum; watch for potential overextension"
        else:
            fg_advice = "market may be overheated; increased correction risk"

        if vix_val >= 25 and fg_val <= 35:
            overall = "BEARISH"
            color   = "#f87171"
            icon    = "🔴"
            summary = (
                f"Market conditions are stressed. VIX at {vix_val:.1f} signals {vix_sentiment}, "
                f"while Fear & Greed at {fg_val} reflects extreme fear. "
                f"Risk assets face headwinds — consider reducing exposure or hedging positions."
            )
        elif vix_val < 18 and fg_val >= 60:
            overall = "BULLISH"
            color   = "#4ade80"
            icon    = "🟢"
            summary = (
                f"Market conditions are constructive. VIX at {vix_val:.1f} indicates {vix_sentiment} "
                f"and Fear & Greed at {fg_val} shows greed. "
                f"Momentum favours risk-on positioning, though profit-taking zones may be near."
            )
        elif vix_val >= 20 or fg_val <= 45:
            overall = "CAUTIOUS"
            color   = "#fb923c"
            icon    = "🟠"
            summary = (
                f"Mixed signals. VIX at {vix_val:.1f} shows {vix_sentiment} "
                f"with sentiment at {fg_label} ({fg_val}/100). "
                f"A selective, risk-managed approach is advisable."
            )
        else:
            overall = "NEUTRAL"
            color   = "#facc15"
            icon    = "🟡"
            summary = (
                f"Markets appear balanced. VIX at {vix_val:.1f} reflects {vix_sentiment} "
                f"with sentiment at {fg_label} ({fg_val}/100). "
                f"No strong directional bias — wait for clearer catalysts."
            )

        return {
            "overall": overall,
            "color":   color,
            "icon":    icon,
            "summary": summary,
            "vix":     vix_val,
            "fg":      fg_val,
        }

    except Exception as e:
        return {
            "overall": "UNAVAILABLE",
            "color":   "#6b7280",
            "icon":    "⚫",
            "summary": f"Could not generate sentiment: {str(e)}",
            "vix": None,
            "fg":  None,
        }
