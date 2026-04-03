from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import asyncio
import json
import requests
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import os
import pytz

KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.environ.get("KIS_ACCOUNT_NO", "")

_cache = {
    "kr": [], "us": [], "macro": {}, "news": [],
    "fear_greed": 50, "timestamp": None, "market_status": "정규"
}

KR_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "005380": "현대차",
    "009830": "한화솔루션",
    "461030": "뉴로메카",
}

US_STOCKS = {
    "NVDA": "엔비디아",
    "SNDK": "샌디스크",
    "MU": "마이크론",
    "INTC": "인텔",
    "AMD": "AMD",
    "TSLA": "테슬라",
    "GLW": "코닝",
    "AMAT": "어플라이드머티리얼",
}

MACRO_TICKERS = {
    "^IXIC": "나스닥",
    "^KS11": "코스피",
    "^KQ11": "코스닥",
    "GC=F": "금",
    "SI=F": "은",
    "CL=F": "WTI유",
    "^VIX": "VIX",
    "DX-Y.NYB": "달러인덱스",
}

def get_kr_market_status():
    try:
        kr_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(kr_tz)
        t = now.hour * 60 + now.minute
        weekday = now.weekday()
        if weekday >= 5:
            return "휴장"
        elif 8*60+30 <= t < 9*60:
            return "장전시간외"
        elif 9*60 <= t < 15*60+30:
            return "정규"
        elif 15*60+30 <= t < 15*60+40:
            return "장마감"
        elif 15*60+40 <= t < 16*60:
            return "장후시간외"
        elif 16*60 <= t < 18*60:
            return "시간외단일가"
        else:
            return "장외"
    except:
        return "정규"

def get_us_market_status():
    try:
        us_tz = pytz.timezone('America/New_York')
        now = datetime.now(us_tz)
        t = now.hour * 60 + now.minute
        weekday = now.weekday()
        if weekday >= 5:
            return "휴장"
        elif 4*60 <= t < 9*60+30:
            return "프리마켓"
        elif 9*60+30 <= t < 16*60:
            return "정규"
        elif 16*60 <= t < 20*60:
            return "애프터마켓"
        else:
            return "휴장"
    except:
        return "정규"

def get_macro():
    result = {}
    for ticker, name in MACRO_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = info.last_price
            prev = info.previous_close
            change_pct = ((price - prev) / prev) * 100 if prev and prev != 0 else 0
            result[ticker] = {
                "name": name,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
            }
        except Exception as e:
            print(f"매크로 오류 {ticker}: {e}")
    return result

def get_fear_greed():
    try:
        res = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        data = res.json()
        return int(float(data["fear_and_greed"]["score"]))
    except:
        return 50

def get_news():
    try:
        res = requests.get(
            "https://feeds.bbci.co.uk/news/business/rss.xml",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        news = []
        for item in items[:10]:
            title = item.find("title")
            if title is not None:
                news.append(title.text)
        return news if news else ["글로벌 시장 모니터링 중..."]
    except Exception as e:
        print(f"뉴스 오류: {e}")
        return ["뉴스 연결 중...", "잠시 후 자동 업데이트됩니다"]

_kis_token = None
_kis_token_expires = None

def get_kis_token():
    global _kis_token, _kis_token_expires
    if _kis_token and _kis_token_expires and datetime.now() < _kis_token_expires:
        return _kis_token
    if not KIS_APP_KEY or not KIS_APP_SECRET:
        return None
    try:
        url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
        }
        res = requests.post(url, json=body)
        data = res.json()
        _kis_token = data.get("access_token")
        _kis_token_expires = datetime.now() + timedelta(hours=23)
        return _kis_token
    except Exception as e:
        print(f"KIS 토큰 오류: {e}")
        return None

def get_kr_stock_kis(ticker):
    market_status = get_kr_market_status()
    try:
        token = get_kis_token()
        if not token:
            result = get_kr_stock_yf(ticker)
            if result:
                result["market_status"] = market_status
            return result
        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
            "tr_id": "FHKST01010100",
        }
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}
        res = requests.get(url, headers=headers, params=params)
        data = res.json().get("output", {})
        price = float(data.get("stck_prpr", 0))
        change = float(data.get("prdy_vrss", 0))
        change_pct = float(data.get("prdy_ctrt", 0))
        if market_status == "시간외단일가":
            try:
                headers2 = {**headers, "tr_id": "FHKST01010400"}
                res2 = requests.get(url, headers=headers2, params=params)
                data2 = res2.json().get("output", {})
                ot_price = float(data2.get("ovtm_untp_prpr", 0) or 0)
                if ot_price > 0:
                    price = ot_price
                    change = float(data2.get("ovtm_untp_prdy_vrss", 0) or 0)
                    change_pct = float(data2.get("ovtm_untp_prdy_ctrt", 0) or 0)
            except:
                pass
        return {
            "ticker": ticker,
            "name": KR_STOCKS.get(ticker, ticker),
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "currency": "KRW",
            "source": "KIS실시간",
            "market_status": market_status,
            "updated": datetime.now().isoformat(),
        }
    except:
        result = get_kr_stock_yf(ticker)
        if result:
            result["market_status"] = market_status
        return result

def get_kr_stock_yf(ticker):
    try:
        stock = yf.Ticker(f"{ticker}.KS")
        info = stock.fast_info
        price = info.last_price
        prev = info.previous_close
        change = price - prev
        change_pct = (change / prev) * 100 if prev else 0
        return {
            "ticker": ticker,
            "name": KR_STOCKS.get(ticker, ticker),
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": "KRW",
            "source": "yfinance",
            "market_status": get_kr_market_status(),
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"ticker": ticker, "name": KR_STOCKS.get(ticker, ticker), "error": str(e)}

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
            "market_status": get_us_market_status(),
            "updated": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"ticker": ticker, "name": US_STOCKS.get(ticker, ticker), "error": str(e)}

def analyze_news_keywords(news_list):
    text = " ".join(news_list).lower()
    bad_keywords = {
        "war": 0.05, "전쟁": 0.05,
        "sanction": 0.04, "제재": 0.04,
        "ban": 0.03, "규제": 0.03,
        "crash": 0.04, "crisis": 0.03,
        "rate hike": 0.03, "금리": 0.02,
        "tariff": 0.04, "관세": 0.04,
        "recession": 0.04, "침체": 0.04,
        "default": 0.05, "파산": 0.05,
        "inflation": 0.02, "인플레": 0.02,
    }
    discount = 0.0
    triggered = []
    for keyword, weight in bad_keywords.items():
        if keyword in text:
            discount += weight
            triggered.append(keyword)
    return min(discount, 0.15), triggered

def get_sniper_scenario(fear_greed, discount, triggered):
    if fear_greed >= 70 or discount >= 0.10:
        kw = ", ".join(triggered[:3]) if triggered else "시장 공황"
        return f"지옥문이 열리기 직전입니다. 3차 지하벙커까지 전력을 분산하십시오. 감지된 악재: {kw}"
    elif fear_greed >= 50 or discount >= 0.05:
        return "전선이 흔들리고 있습니다. 1차 타점 소량 진입 후 추가 하락을 대기하십시오."
    elif fear_greed >= 30:
        return "안개가 짙습니다. 분할 매수 전략을 유지하며 신호를 기다리십시오."
    else:
        return "탐욕 구간 진입이 감지됩니다. 추격 매수는 금물. 눌림목에서 저격하십시오."

async def background_updater():
    while True:
        try:
            _cache["market_status"] = get_kr_market_status()
            _cache["kr"] = [get_kr_stock_kis(t) for t in KR_STOCKS]
            _cache["us"] = [get_us_stock(t) for t in US_STOCKS]
            _cache["macro"] = get_macro()
            _cache["news"] = get_news()
            _cache["fear_greed"] = get_fear_greed()
            _cache["timestamp"] = datetime.now().isoformat()
            print(f"✅ {_cache['timestamp']} | 시장: {_cache['market_status']}")
        except Exception as e:
            print(f"업데이트 오류: {e}")
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

@app.get("/")
def root():
    return {"status": "AI Stock Terminal API 🚀", "timestamp": datetime.now().isoformat()}

@app.get("/api/kr-stocks")
def kr_stocks():
    return _cache["kr"] if _cache["kr"] else [get_kr_stock_kis(t) for t in KR_STOCKS]

@app.get("/api/us-stocks")
def us_stocks():
    return _cache["us"] if _cache["us"] else [get_us_stock(t) for t in US_STOCKS]

@app.get("/api/macro")
def macro():
    return _cache["macro"] if _cache["macro"] else get_macro()

@app.get("/api/news")
def news():
    return _cache["news"] if _cache["news"] else get_news()

@app.get("/api/fear-greed")
def fear_greed():
    return {"score": _cache["fear_greed"]}

@app.get("/api/market-status")
def market_status():
    return {"status": _cache["market_status"]}

@app.get("/api/chart/{ticker}")
def get_chart(ticker: str):
    try:
        yf_ticker = f"{ticker}.KS" if ticker in KR_STOCKS else ticker
        stock = yf.Ticker(yf_ticker)
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
        yf_ticker = f"{ticker}.KS" if ticker in KR_STOCKS else ticker
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="5d", interval="1d")
        price = float(df["Close"].iloc[-1])
        news_list = _cache.get("news", [])
        fear_greed_score = _cache.get("fear_greed", 50)
        macro = _cache.get("macro", {})
        vix = macro.get("^VIX", {}).get("price", 0)
        discount, triggered = analyze_news_keywords(news_list)
        if vix > 30:
            discount = min(discount + 0.05, 0.15)
        elif vix > 20:
            discount = min(discount + 0.02, 0.15)
        scenario = get_sniper_scenario(fear_greed_score, discount, triggered)
        return {
            "ticker": ticker,
            "current": price,
            "buy1": round(price * (0.97 - discount), 2),
            "buy2": round(price * (0.93 - discount), 2),
            "buy3": round(price * (0.88 - discount), 2),
            "sell": round(price * 1.08, 2),
            "stop_loss": round(price * 0.85, 2),
            "is_bad_news": discount > 0.02,
            "discount_pct": round(discount * 100, 1),
            "triggered_keywords": triggered[:5],
            "scenario": scenario,
            "currency": "KRW" if ticker in KR_STOCKS else "USD",
        }
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws/stocks")
async def websocket_stocks(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = {
                "kr": _cache["kr"],
                "us": _cache["us"],
                "macro": _cache["macro"],
                "news": _cache["news"],
                "fear_greed": _cache["fear_greed"],
                "market_status": _cache["market_status"],
                "timestamp": datetime.now().isoformat(),
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("클라이언트 연결 종료")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)