from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import asyncio
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import os
import pytz

KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.environ.get("KIS_ACCOUNT_NO", "")

_cache = {
    "kr": [], "us": [], "macro": {}, "news": [],
    "fear_greed": 50, "timestamp": None, "market_status": "정규",
    "recommendations": {},
    "price_history": {},
    "macro_history": {},
    "krx_map": {},
}

KR_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "005380": "현대차",
    "009830": "한화솔루션",
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

EMERGENCY_KEYWORDS = [
    "속보", "breaking", "폭락", "crash", "급락", "전쟁", "war",
    "금리 결정", "rate decision", "폭발", "explosion", "긴급", "emergency",
    "디폴트", "default", "파산", "bankruptcy"
]

STOCK_NAME_MAP = {
    "애플": "AAPL", "apple": "AAPL",
    "테슬라": "TSLA", "tesla": "TSLA",
    "엔비디아": "NVDA", "nvidia": "NVDA",
    "마이크로소프트": "MSFT", "microsoft": "MSFT",
    "구글": "GOOGL", "google": "GOOGL",
    "아마존": "AMZN", "amazon": "AMZN",
    "메타": "META", "meta": "META",
    "삼성전자": "005930", "삼성": "005930",
    "sk하이닉스": "000660", "하이닉스": "000660",
    "카카오": "035720",
    "네이버": "035420", "naver": "035420",
    "현대차": "005380",
    "기아": "000270",
    "한화솔루션": "009830",
}

def load_krx_stock_list():
    try:
        from pykrx import stock
        today = datetime.now().strftime("%Y%m%d")
        tickers = stock.get_market_ticker_list(today, market="ALL")
        result = {}
        for ticker in tickers:
            try:
                name = stock.get_market_ticker_name(ticker).lower()
                result[name] = ticker
            except:
                pass
        print(f"✅ KRX 종목 {len(result)}개 로드 완료")
        return result
    except Exception as e:
        print(f"KRX 로드 실패: {e}")
        return {}

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

def check_emergency_news(news_list):
    text = " ".join(news_list).lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw.lower() in text:
            return True, kw
    return False, None

def check_price_emergency(ticker, current_price):
    history = _cache["price_history"].get(ticker, [])
    if len(history) < 2:
        return False, 0
    oldest = history[0]
    if oldest == 0:
        return False, 0
    change_pct = ((current_price - oldest) / oldest) * 100
    if abs(change_pct) >= 3:
        return True, round(change_pct, 2)
    return False, round(change_pct, 2)

def check_macro_emergency():
    macro = _cache.get("macro", {})
    ixic = macro.get("^IXIC", {})
    ks11 = macro.get("^KS11", {})
    ixic_change = ixic.get("change_pct", 0)
    ks11_change = ks11.get("change_pct", 0)
    if ixic_change <= -1.0:
        return True, f"나스닥 {ixic_change}% 급락"
    if ks11_change <= -1.0:
        return True, f"코스피 {ks11_change}% 급락"
    return False, None

def update_price_history(ticker, price):
    if ticker not in _cache["price_history"]:
        _cache["price_history"][ticker] = []
    history = _cache["price_history"][ticker]
    history.append(price)
    if len(history) > 60:
        history.pop(0)

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
        update_price_history(ticker, price)
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
        update_price_history(ticker, price)
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
        update_price_history(ticker, price)
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

def get_sniper_scenario(fear_greed, discount, triggered, is_emergency=False, emergency_reason=None):
    if is_emergency and emergency_reason:
        return f"🚨 긴급 상황입니다. {emergency_reason}. 3차 벙커 타점을 즉시 하향 조정합니다. 대기하십시오."
    if fear_greed >= 70 or discount >= 0.10:
        kw = ", ".join(triggered[:3]) if triggered else "시장 공황"
        return f"지옥문이 열리기 직전입니다. 3차 지하벙커까지 전력을 분산하십시오. 감지된 악재: {kw}"
    elif fear_greed >= 50 or discount >= 0.05:
        return "전선이 흔들리고 있습니다. 1차 타점 소량 진입 후 추가 하락을 대기하십시오."
    elif fear_greed >= 30:
        return "안개가 짙습니다. 분할 매수 전략을 유지하며 신호를 기다리십시오."
    else:
        return "탐욕 구간 진입이 감지됩니다. 추격 매수는 금물. 눌림목에서 저격하십시오."

def calculate_recommendation(ticker, is_emergency=False, emergency_reason=None):
    try:
        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="1mo", interval="1d")
        if df is None or len(df) == 0:
            return None
        price = float(df["Close"].dropna().iloc[-1])
        if price != price:
            return None
        news_list = _cache.get("news", [])
        fear_greed_score = _cache.get("fear_greed", 50)
        macro = _cache.get("macro", {})
        vix = macro.get("^VIX", {}).get("price", 0)
        discount, triggered = analyze_news_keywords(news_list)
        if is_emergency:
            discount = min(discount + 0.05, 0.20)
        if vix > 30:
            discount = min(discount + 0.05, 0.20)
        elif vix > 20:
            discount = min(discount + 0.02, 0.20)
        scenario = get_sniper_scenario(fear_greed_score, discount, triggered, is_emergency, emergency_reason)
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
            "is_emergency": is_emergency,
            "emergency_reason": emergency_reason,
            "currency": "KRW" if len(ticker) == 6 and ticker.isdigit() else "USD",
            "updated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"추천 계산 오류 {ticker}: {e}")
        return None

_last_strategy_update = None

async def background_updater():
    global _last_strategy_update
    while True:
        try:
            _cache["market_status"] = get_kr_market_status()
            _cache["kr"] = [get_kr_stock_kis(t) for t in KR_STOCKS]
            _cache["us"] = [get_us_stock(t) for t in US_STOCKS]
            _cache["macro"] = get_macro()
            _cache["news"] = get_news()
            _cache["fear_greed"] = get_fear_greed()
            _cache["timestamp"] = datetime.now().isoformat()

            is_emergency = False
            emergency_reason = None

            news_emergency, news_kw = check_emergency_news(_cache["news"])
            if news_emergency:
                is_emergency = True
                emergency_reason = f"긴급 뉴스 감지: {news_kw}"

            macro_emergency, macro_reason = check_macro_emergency()
            if macro_emergency:
                is_emergency = True
                emergency_reason = macro_reason

            all_stocks = _cache["kr"] + _cache["us"]
            for stock in all_stocks:
                if not stock or "error" in stock:
                    continue
                ticker = stock.get("ticker")
                price = stock.get("price", 0)
                if price:
                    price_emergency, price_change = check_price_emergency(ticker, price)
                    if price_emergency:
                        is_emergency = True
                        emergency_reason = f"{stock.get('name', ticker)} {price_change:+.1f}% 급변"

            now = datetime.now()
            should_update = (
                is_emergency or
                _last_strategy_update is None or
                (now - _last_strategy_update).seconds >= 3600
            )

            if should_update:
                all_tickers = list(KR_STOCKS.keys()) + list(US_STOCKS.keys())
                for ticker in all_tickers:
                    rec = calculate_recommendation(ticker, is_emergency, emergency_reason)
                    if rec:
                        _cache["recommendations"][ticker] = rec
                _last_strategy_update = now
                update_type = "🚨 긴급" if is_emergency else "📊 정기"
                print(f"{update_type} 전략 업데이트 완료: {now.isoformat()}")

            _cache["is_emergency"] = is_emergency
            _cache["emergency_reason"] = emergency_reason
            print(f"✅ {_cache['timestamp']} | 시장: {_cache['market_status']}")
        except Exception as e:
            print(f"업데이트 오류: {e}")
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    _cache["krx_map"] = load_krx_stock_list()
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
        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
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
    if ticker in _cache["recommendations"]:
        return _cache["recommendations"][ticker]
    rec = calculate_recommendation(ticker)
    if rec:
        _cache["recommendations"][ticker] = rec
        return rec
    return {"error": "계산 실패"}

@app.get("/api/search/{query}")
def search_stock(query: str):
    try:
        q = query.strip().lower()
        if q in STOCK_NAME_MAP:
            ticker = STOCK_NAME_MAP[q]
        elif q in _cache["krx_map"]:
            ticker = _cache["krx_map"][q]
        else:
            ticker = query.upper().strip()

        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
        stock = yf.Ticker(yf_ticker)

        try:
            info = stock.fast_info
            price = float(info.last_price) if info.last_price else 0
            prev = float(info.previous_close) if info.previous_close else 0
        except:
            df = stock.history(period="5d", interval="1d")
            if df is None or len(df) == 0:
                return {"error": f"'{query}' 종목을 찾을 수 없습니다"}
            price = float(df["Close"].dropna().iloc[-1])
            prev = float(df["Close"].dropna().iloc[-2]) if len(df) > 1 else price

        change = price - prev
        change_pct = (change / prev) * 100 if prev else 0
        rec = calculate_recommendation(ticker)
        return {
            "ticker": ticker,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": "KRW" if len(ticker) == 6 and ticker.isdigit() else "USD",
            "recommendation": rec,
        }
    except Exception as e:
        return {"error": f"검색 실패: {str(e)}"}

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
                "is_emergency": _cache.get("is_emergency", False),
                "emergency_reason": _cache.get("emergency_reason", None),
                "recommendations": _cache["recommendations"],
                "timestamp": datetime.now().isoformat(),
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("클라이언트 연결 종료")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)