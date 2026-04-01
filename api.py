from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import FinanceDataReader as fdr
import asyncio
import json
import requests
from datetime import datetime, timedelta
import sys
sys.path.append(r'C:\Users\woofe\Desktop\stock-dashboard')
import config

# 캐시 저장소
_cache = {"kr": [], "us": [], "timestamp": None}

async def background_updater():
    while True:
        try:
            _cache["kr"] = [get_kr_stock_kis(t) for t in KR_STOCKS]
            _cache["us"] = [get_us_stock(t) for t in US_STOCKS]
            _cache["timestamp"] = datetime.now().isoformat()
        except Exception as e:
            print(f"캐시 업데이트 오류: {e}")
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(background_updater())
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

KR_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "005380": "현대차",
    "000270": "기아",
}

US_STOCKS = {
    "NVDA": "엔비디아",
    "SNDK": "샌디스크",
    "MU": "마이크론",
    "GLW": "코닝",
    "AMAT": "어플라이드머티리얼",
}

# KIS API 토큰 캐시
_kis_token = None
_kis_token_expires = None

def get_kis_token():
    global _kis_token, _kis_token_expires
    if _kis_token and _kis_token_expires and datetime.now() < _kis_token_expires:
        return _kis_token
    try:
        url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": config.KIS_APP_KEY,
            "appsecret": config.KIS_APP_SECRET,
        }
        res = requests.post(url, json=body)
        data = res.json()
        _kis_token = data.get("access_token")
        _kis_token_expires = datetime.now() + timedelta(hours=23)
        return _kis_token
    except Exception as e:
        print(f"KIS 토큰 발급 실패: {e}")
        return None

def get_kr_stock_kis(ticker):
    try:
        token = get_kis_token()
        if not token:
            return get_kr_stock_fdr(ticker)
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": config.KIS_APP_KEY,
            "appsecret": config.KIS_APP_SECRET,
            "tr_id": "FHKST01010100",
        }
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}
        res = requests.get(url, headers=headers, params=params)
        data = res.json().get("output", {})
        price = float(data.get("stck_prpr", 0))
        prev_close = float(data.get("stck_sdpr", 0))
        change = float(data.get("prdy_vrss", 0))
        change_pct = float(data.get("prdy_ctrt", 0))
        return {
            "ticker": ticker,
            "name": KR_STOCKS.get(ticker, ticker),
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "prev_close": prev_close,
            "currency": "KRW",
            "source": "KIS실시간",
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return get_kr_stock_fdr(ticker)

def get_kr_stock_fdr(ticker):
    try:
        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=5)).strftime('%Y-%m-%d')
        df = fdr.DataReader(ticker, start, end)
        if df is None or len(df) == 0:
            return None
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        price = float(latest['Close'])
        prev_price = float(prev['Close'])
        change = price - prev_price
        change_pct = (change / prev_price) * 100
        return {
            "ticker": ticker,
            "name": KR_STOCKS.get(ticker, ticker),
            "price": price,
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": "KRW",
            "source": "FDR지연",
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def get_us_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        price = info.last_price
        prev_close = info.previous_close
        change = price - prev_close
        change_pct = (change / prev_close) * 100
        return {
            "ticker": ticker,
            "name": US_STOCKS.get(ticker, ticker),
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": "USD",
            "source": "yfinance",
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

@app.get("/api/kr-stocks")
def kr_stocks():
    return _cache["kr"] if _cache["kr"] else [get_kr_stock_kis(t) for t in KR_STOCKS]

@app.get("/api/us-stocks")
def us_stocks():
    return _cache["us"] if _cache["us"] else [get_us_stock(t) for t in US_STOCKS]

@app.websocket("/ws/stocks")
async def websocket_stocks(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = {
                "kr": [get_kr_stock_kis(t) for t in KR_STOCKS],
                "us": [get_us_stock(t) for t in US_STOCKS],
                "timestamp": datetime.now().isoformat(),
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("클라이언트 연결 종료")

@app.get("/api/chart/{ticker}")
def get_chart(ticker: str):
    try:
        # 한국 주식은 .KS 붙여야 yfinance에서 인식
        yfTicker = f"{ticker}.KS" if ticker in KR_STOCKS else ticker
        stock = yf.Ticker(yfTicker)
        df = stock.history(period="1d", interval="5m")
        if df is None or len(df) == 0:
            return []
        result = []
        for idx, row in df.iterrows():
            result.append({
                "time": idx.strftime("%H:%M"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/recommend/{ticker}")
def get_recommend(ticker: str):
    try:
        yfTicker = f"{ticker}.KS" if ticker in KR_STOCKS else ticker
        stock = yf.Ticker(yfTicker)
        df = stock.history(period="5d", interval="1d")
        price = float(df["Close"].iloc[-1])
        low5 = float(df["Low"].min())
        high5 = float(df["High"].max())
        # 단순 추천 로직
        buy = round(price * 0.97, 2)
        sell = round(price * 1.05, 2)
        stop = round(price * 0.93, 2)
        return {
            "ticker": ticker,
            "current": price,
            "buy": buy,
            "sell": sell,
            "stop_loss": stop,
            "low5": low5,
            "high5": high5,
        }
    except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)