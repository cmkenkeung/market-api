from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/vix")
def get_vix():
    vix = yf.Ticker("^VIX")
    hist = vix.history(period="1mo")
    current = float(hist["Close"].iloc[-1])
    change  = float(hist["Close"].iloc[-1] - hist["Close"].iloc[-2])
    history = [
        {"date": str(d.date()), "close": float(v)}
        for d, v in zip(hist.index, hist["Close"])
    ]
    return {"current": current, "change": change, "history": history}

@app.get("/fear-greed")
def get_fear_greed():
    # Replace with real API call when available
    return {"value": 32, "label": "Fear"}

@app.get("/news")
def get_news():
    return {"items": [
        {"title": "Geopolitical pressure", "body": "Middle East tensions drive oil volatility."},
        {"title": "Bond market", "body": "US 10Y yield holds near 4.28%."},
    ]}