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
    "smart_picks": [],
    "macro_report": {},
    "news_sentiment": {},
    "sector_flow": [],
    "kr_last_valid_price": {},  # ★ KIS 마지막 유효 체결가 보존
    "risk_keyword_memory": {},   #
}

KR_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "005380": "현대차",
    "009830": "한화솔루션",
    "272210": "한화시스템",
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

SCREENING_UNIVERSE = {
    "NVDA": {"name": "엔비디아", "sector": "반도체"},
    "AAPL": {"name": "애플", "sector": "기술"},
    "MSFT": {"name": "마이크로소프트", "sector": "기술"},
    "GOOGL": {"name": "구글", "sector": "기술"},
    "AMZN": {"name": "아마존", "sector": "소비재"},
    "META": {"name": "메타", "sector": "기술"},
    "TSLA": {"name": "테슬라", "sector": "자동차"},
    "AMD": {"name": "AMD", "sector": "반도체"},
    "MU": {"name": "마이크론", "sector": "반도체"},
    "AMAT": {"name": "어플라이드머티리얼", "sector": "반도체장비"},
    "SNDK": {"name": "샌디스크", "sector": "반도체"},
    "GLW": {"name": "코닝", "sector": "소재"},
    "JPM": {"name": "JP모건", "sector": "금융"},
    "GS": {"name": "골드만삭스", "sector": "금융"},
    "NFLX": {"name": "넷플릭스", "sector": "미디어"},
    "005930": {"name": "삼성전자", "sector": "반도체"},
    "000660": {"name": "SK하이닉스", "sector": "반도체"},
    "035420": {"name": "NAVER", "sector": "기술"},
    "005380": {"name": "현대차", "sector": "자동차"},
    "009830": {"name": "한화솔루션", "sector": "에너지"},
    "272210": {"name": "한화시스템", "sector": "방산"},
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
    "한화시스템": "272210",
}

EXTREME_POSITIVE = {
    "record high": 10, "all-time high": 10, "최고치": 10, "역대 최고": 10,
    "breakthrough": 10, "혁신적 돌파": 10, "급등": 10, "폭등": 10,
    "surge": 10, "soar": 10, "skyrocket": 10, "moon": 8,
    "massive rally": 10, "historic rally": 10, "강세 전환": 8,
    "beat expectations": 8, "실적 서프라이즈": 10, "어닝서프라이즈": 10,
    "rally": 6, "jump": 6, "rise": 4, "gain": 4, "upgrade": 6,
    "bullish": 6, "growth": 4, "profit": 4, "recovery": 6,
    "outperform": 6, "boom": 6, "상승": 4, "강세": 6,
    "반등": 6, "수혜": 4, "호조": 6, "흑자": 6, "매수": 4,
}

EXTREME_NEGATIVE = {
    "war": 10, "전쟁": 10, "missile": 10, "미사일": 10,
    "crash": 10, "폭락": 10, "collapse": 10, "붕괴": 10,
    "bankruptcy": 10, "파산": 10, "default": 10, "디폴트": 10,
    "supply chain collapse": 10, "공급망 붕괴": 10,
    "nuclear": 10, "핵": 8, "sanctions": 8, "제재": 8,
    "recession": 10, "침체": 10, "depression": 10,
    "급락": 10, "plunge": 10, "freefall": 10,
    "circuit breaker": 10, "서킷브레이커": 10,
    "tariff war": 10, "무역전쟁": 10,
    "crisis": 6, "위기": 6, "fall": 4, "drop": 4,
    "downgrade": 6, "bearish": 6, "loss": 6, "decline": 4,
    "warning": 6, "tariff": 6, "관세": 6, "inflation": 4,
    "하락": 4, "약세": 6, "부진": 6, "적자": 6,
    "불안": 4, "경고": 6, "규제": 4,
}

def get_reddit_wsb_sentiment():
    try:
        headers = {"User-Agent": "AI-Stock-Terminal/1.0"}
        res = requests.get("https://www.reddit.com/r/wallstreetbets/hot.json?limit=15", headers=headers, timeout=6)
        data = res.json()
        posts = data.get("data", {}).get("children", [])
        if not posts: return 50, []
        pos = 0; neg = 0; found_kw = []
        for post in posts:
            title = post.get("data", {}).get("title", "").lower()
            score_val = post.get("data", {}).get("score", 0) or 0
            weight = min(max(score_val / 1000, 0.5), 3.0)
            for kw, w in EXTREME_POSITIVE.items():
                if kw.lower() in title: pos += w * weight; found_kw.append(f"WSB↑{kw}")
            for kw, w in EXTREME_NEGATIVE.items():
                if kw.lower() in title: neg += w * weight; found_kw.append(f"WSB↓{kw}")
        total = pos + neg
        if total == 0: return 50, []
        return round(pos / total * 100), found_kw[:4]
    except Exception as e:
        print(f"Reddit 감성 오류: {e}")
        return 50, []

def get_decisive_reason(news_list, pos_kw_found, neg_kw_found):
    try:
        best_headline = ""
        best_score = 0
        all_extreme = list(EXTREME_NEGATIVE.keys())[:20] + list(EXTREME_POSITIVE.keys())[:20]
        for headline in news_list[:10]:
            h_lower = headline.lower()
            score = sum(1 for kw in all_extreme if kw.lower() in h_lower)
            if score > best_score: best_score = score; best_headline = headline
        if not best_headline and news_list: best_headline = news_list[0]
        if neg_kw_found: return f"'{neg_kw_found[0]}' 관련 악재 헤드라인 감지 → 부정 심리 우세"
        elif pos_kw_found: return f"'{pos_kw_found[0]}' 관련 호재 헤드라인 감지 → 긍정 심리 우세"
        else: return best_headline[:60] if best_headline else "뉴스 분석 중"
    except: return "뉴스 분석 중"

def get_news_sentiment(news_list=None):
    try:
        if news_list is None: news_list = _cache.get("news", [])
        text = " ".join(news_list).lower()

        pos_score = 0; neg_score = 0; pos_found = []; neg_found = []
        for kw, weight in EXTREME_POSITIVE.items():
            if kw.lower() in text: pos_score += weight; pos_found.append(kw)
        for kw, weight in EXTREME_NEGATIVE.items():
            if kw.lower() in text: neg_score += weight; neg_found.append(kw)

        # ★ 위험 키워드 24시간 메모리
        HIGH_RISK_KEYWORDS = ["war", "전쟁", "missile", "미사일", "nuclear", "핵", "이란", "iran", "북한", "invasion", "침공", "폭격"]
        now = datetime.now()
        risk_memory = _cache.get("risk_keyword_memory", {})

        # 현재 뉴스에서 위험 키워드 감지 → 메모리 저장
        for kw in HIGH_RISK_KEYWORDS:
            if kw.lower() in text:
                risk_memory[kw] = now.isoformat()

        # 24시간 지난 메모리 삭제
        expired = [k for k, v in risk_memory.items()
                   if (now - datetime.fromisoformat(v)).total_seconds() > 86400]
        for k in expired: del risk_memory[k]
        _cache["risk_keyword_memory"] = risk_memory

        # ★ 메모리에 위험 키워드 남아있으면 추가 패널티
        memory_penalty = 0
        active_risks = []
        for kw, ts in risk_memory.items():
            hours_ago = (now - datetime.fromisoformat(ts)).total_seconds() / 3600
            if hours_ago < 6:    penalty = 25  # 6시간 이내: 강력 패널티
            elif hours_ago < 12: penalty = 18  # 12시간 이내
            elif hours_ago < 24: penalty = 10  # 24시간 이내
            else: penalty = 0
            memory_penalty += penalty
            active_risks.append(f"{kw}({int(hours_ago)}h전)")
        memory_penalty = min(memory_penalty, 40)  # 최대 -40점

        news_total = pos_score + neg_score
        news_base = round(pos_score / news_total * 100) if news_total > 0 else 50
        reddit_score, reddit_kw = get_reddit_wsb_sentiment()
        combined = round(news_base * 0.7 + reddit_score * 0.3)

        # 위험 키워드 메모리 패널티 적용
        combined = max(0, combined - memory_penalty)

        macro = _cache.get("macro", {})
        vix = macro.get("^VIX", {}).get("price", 20)
        vix_change = macro.get("^VIX", {}).get("change_pct", 0)
        vix_penalty = 0
        if vix > 35: vix_penalty = -20
        elif vix > 25: vix_penalty = -12
        elif vix > 20: vix_penalty = -6
        if vix_change > 10: vix_penalty -= 8
        elif vix_change > 5: vix_penalty -= 4
        combined = max(0, min(100, combined + vix_penalty))

        # ★ VIX 하드 캡: VIX 20 이상이면 최대 50점(중립)
        if vix >= 20:
            combined = min(combined, 50)
            print(f"⚠️ VIX {vix:.1f} → 감성 점수 하드캡 50 적용: {combined}")

        if 45 <= combined <= 55 and vix < 20:  # VIX 낮을 때만 극단값 조정
            extreme_neg = sum(1 for kw in ["war","crash","bankruptcy","폭락","전쟁","파산","recession","침체","collapse"] if kw in text)
            extreme_pos = sum(1 for kw in ["record high","breakthrough","surge","폭등","최고치","급등","boom"] if kw in text)
            if extreme_neg > extreme_pos: combined = min(combined - 12, 42)
            elif extreme_pos > extreme_neg: combined = max(combined + 12, 58)
            elif neg_score > pos_score: combined = min(combined - 8, 44)
            elif pos_score > neg_score: combined = max(combined + 8, 56)
            elif vix > 20: combined = min(combined - 6, 44)
            else: combined = max(combined + 6, 56)

        if combined <= 30: label, color, alert_level = "극단적 공포 🚨", "#dc2626", "danger"
        elif combined <= 40: label, color, alert_level = "강한 부정 📉", "#ff3b3b", "warning"
        elif combined <= 60: label, color, alert_level = "관망 ⚠️", "#facc15", "caution"
        elif combined <= 70: label, color, alert_level = "긍정 📈", "#84cc16", "ok"
        else: label, color, alert_level = "극단적 탐욕 🤑", "#22c55e", "bull"

        neg_ratio = 100 - combined
        all_pos_kw = pos_found[:3] + [k.replace("WSB↑","") for k in reddit_kw if "↑" in k][:2]
        all_neg_kw = neg_found[:3] + [k.replace("WSB↓","") for k in reddit_kw if "↓" in k][:2]

        # 활성 위험 메모리 키워드도 부정 키워드에 표시
        if active_risks:
            all_neg_kw = list(dict.fromkeys(all_neg_kw + [r.split("(")[0] for r in active_risks]))[:5]

        decisive = get_decisive_reason(news_list, pos_found, neg_found)
        if active_risks and memory_penalty > 0:
            decisive = f"⚠️ 위험 메모리 활성: {', '.join(active_risks[:2])} → 감성 {memory_penalty}점 차감 유지"

        return {
            "score": combined, "pos_ratio": combined, "neg_ratio": neg_ratio,
            "pos_score": pos_score, "neg_score": neg_score,
            "pos_keywords": list(dict.fromkeys(all_pos_kw))[:5],
            "neg_keywords": list(dict.fromkeys(all_neg_kw))[:5],
            "label": label, "color": color, "alert_level": alert_level,
            "is_danger": neg_ratio >= 70 or combined <= 30,
            "reddit_score": reddit_score, "vix_penalty": vix_penalty,
            "memory_penalty": memory_penalty,
            "active_risks": active_risks[:3],
            "decisive_reason": decisive,
            "news_count": len(news_list), "updated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"감성 분석 오류: {e}")
        return {"score": 40, "pos_ratio": 40, "neg_ratio": 60, "label": "분석 오류", "color": "#facc15", "alert_level": "caution", "is_danger": False, "decisive_reason": "감성 분석 오류"}

def get_sector_flow():
    try:
        kr_sector_data = {}
        us_sector_data = {}
        for stock in _cache.get("kr", []):
            if not stock or "error" in stock: continue
            ticker = stock.get("ticker", "")
            info = SCREENING_UNIVERSE.get(ticker, {})
            sector = info.get("sector", "기타")
            change_pct = stock.get("change_pct", 0) or 0
            if sector not in kr_sector_data:
                kr_sector_data[sector] = {"sector": sector, "total_change": 0, "count": 0, "stocks": []}
            kr_sector_data[sector]["total_change"] += change_pct
            kr_sector_data[sector]["count"] += 1
            kr_sector_data[sector]["stocks"].append({"ticker": ticker, "name": info.get("name", ticker), "change_pct": round(change_pct, 2), "market": "KR"})
        for stock in _cache.get("us", []):
            if not stock or "error" in stock: continue
            ticker = stock.get("ticker", "")
            info = SCREENING_UNIVERSE.get(ticker, {})
            sector = info.get("sector", "기타")
            change_pct = stock.get("change_pct", 0) or 0
            if sector not in us_sector_data:
                us_sector_data[sector] = {"sector": sector, "total_change": 0, "count": 0, "stocks": []}
            us_sector_data[sector]["total_change"] += change_pct
            us_sector_data[sector]["count"] += 1
            us_sector_data[sector]["stocks"].append({"ticker": ticker, "name": info.get("name", ticker), "change_pct": round(change_pct, 2), "market": "US"})
        def build_result(sector_data, market):
            result = []
            for sector, data in sector_data.items():
                count = data["count"]
                avg_change = data["total_change"] / count if count > 0 else 0
                result.append({"sector": sector, "avg_change": round(avg_change, 2), "count": count, "stocks": sorted(data["stocks"], key=lambda x: x["change_pct"], reverse=True), "flow": "inflow" if avg_change > 0 else "outflow", "market": market})
            return sorted(result, key=lambda x: x["avg_change"], reverse=True)
        return build_result(kr_sector_data, "KR") + build_result(us_sector_data, "US")
    except Exception as e:
        print(f"섹터 수급 오류: {e}")
        return []

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
            except: pass
        print(f"✅ KRX 종목 {len(result)}개 로드 완료")
        return result
    except Exception as e:
        print(f"KRX 로드 실패: {e}")
        return {}

def calculate_rsi(prices, period=14):
    try:
        if len(prices) < period + 1: return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        recent = deltas[-period:]
        gains = [max(d, 0) for d in recent]
        losses = [abs(min(d, 0)) for d in recent]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)
    except: return 50

def calculate_stock_score(ticker):
    try:
        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="3mo", interval="1d")
        if df is None or len(df) < 20: return None
        prices = df["Close"].dropna().tolist()
        volumes = df["Volume"].dropna().tolist()
        current_price = prices[-1]
        score = 0
        rsi = calculate_rsi(prices[-30:] if len(prices) >= 30 else prices)
        if 30 <= rsi <= 50: rsi_score = 25
        elif rsi < 30: rsi_score = 22
        elif 50 < rsi <= 60: rsi_score = 18
        elif 60 < rsi <= 70: rsi_score = 10
        else: rsi_score = 5
        score += rsi_score
        momentum = 0
        if len(prices) >= 20:
            momentum = (current_price - prices[-20]) / prices[-20] * 100
            if -3 <= momentum <= 5: mom_score = 25
            elif -8 <= momentum < -3: mom_score = 20
            elif 5 < momentum <= 15: mom_score = 15
            elif momentum < -8: mom_score = 18
            else: mom_score = 8
        else: mom_score = 12
        score += mom_score
        ma50 = 0
        if len(prices) >= 50:
            ma50 = sum(prices[-50:]) / 50
            diff_pct = (current_price - ma50) / ma50 * 100
            if -2 <= diff_pct <= 5: ma_score = 25
            elif -5 <= diff_pct < -2: ma_score = 20
            elif 5 < diff_pct <= 10: ma_score = 15
            elif diff_pct < -5: ma_score = 18
            else: ma_score = 10
        else: ma_score = 12
        score += ma_score
        vol_ratio = 1
        if len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            recent_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else avg_vol
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1
            if 1.2 <= vol_ratio <= 2.5: vol_score = 25
            elif vol_ratio > 2.5: vol_score = 18
            elif 0.9 <= vol_ratio < 1.2: vol_score = 15
            else: vol_score = 8
        else: vol_score = 12
        score += vol_score
        final_score = min(score, 100)
        if rsi < 40 and ma50 > 0: upside = (ma50 - current_price) / current_price * 100 * 1.5
        elif rsi > 65: upside = -5.0
        else: upside = (final_score - 50) * 0.4
        return {"score": final_score, "rsi": rsi, "momentum_1m": round(momentum, 2), "vol_ratio": round(vol_ratio, 2), "current_price": round(current_price, 2), "upside": round(upside, 1), "currency": "KRW" if len(ticker) == 6 and ticker.isdigit() else "USD"}
    except Exception as e:
        print(f"점수 계산 오류 {ticker}: {e}")
        return None

def get_grade(score):
    if score >= 85: return "적극 매수"
    elif score >= 70: return "매수"
    elif score >= 55: return "관망"
    else: return "주의"

def generate_stock_analysis(ticker, score_data):
    try:
        info = SCREENING_UNIVERSE.get(ticker, {})
        name = info.get("name", ticker)
        sector = info.get("sector", "기타")
        score = score_data.get("score", 50)
        rsi = score_data.get("rsi", 50)
        momentum = score_data.get("momentum_1m", 0)
        upside = score_data.get("upside", 0)
        macro = _cache.get("macro", {})
        vix = macro.get("^VIX", {}).get("price", 20)
        fear_greed = _cache.get("fear_greed", 50)
        grade = get_grade(score)
        lines = []
        if rsi < 35: lines.append(f"{name}은(는) RSI {rsi}로 과매도 구간에 진입했습니다. 기술적 반등 가능성이 높으며 단기 저점 매수 기회로 판단됩니다.")
        elif rsi < 50: lines.append(f"{name}의 RSI {rsi}는 매수 적정 구간입니다. 추가 하락 압력이 제한적이며 분할 매수 접근이 유효합니다.")
        elif rsi < 65: lines.append(f"{name}의 RSI {rsi}는 중립 구간으로, 추세 추종 전략이 적합합니다.")
        else: lines.append(f"{name}의 RSI {rsi}는 과매수 구간으로 신규 진입보다 기존 보유자의 비중 관리가 필요합니다.")
        if momentum < -8: lines.append(f"최근 1개월간 {abs(momentum):.1f}% 조정을 받으며 가격 부담이 해소되었습니다. {sector} 섹터의 구조적 성장성을 고려하면 현 구간은 전략적 매수 타이밍입니다.")
        elif momentum < 0: lines.append(f"1개월 수익률 {momentum:.1f}%로 소폭 조정 중입니다. 지지선 확인 후 반등 시 매수 대응이 유효합니다.")
        elif momentum < 10: lines.append(f"1개월 수익률 +{momentum:.1f}%로 완만한 상승세를 유지하고 있습니다.")
        else: lines.append(f"1개월 수익률 +{momentum:.1f}%로 강한 모멘텀을 보이고 있으나 단기 과열 여부를 점검해야 합니다.")
        if vix > 25: lines.append(f"VIX {vix:.1f}로 시장 변동성이 확대된 상태입니다. 분할 매수 전략으로 리스크를 분산하며 3차 벙커까지 여유 자금을 확보하십시오.")
        elif fear_greed < 35: lines.append(f"CNN 공포지수 {fear_greed}로 극도의 공포 구간입니다. 역발상 투자 관점에서 현 구간은 중장기 저점 매수 구간으로 판단됩니다.")
        else: lines.append(f"현재 매크로 환경은 {sector} 섹터에 중립적입니다. 개별 종목 펀더멘털에 집중한 선별적 접근이 필요합니다.")
        lines.append(f"종합 AI 점수 {score}점 ({grade}). 목표 업사이드 {upside:+.1f}%.")
        return " ".join(lines)
    except: return f"{ticker} 분석 생성 중 오류가 발생했습니다."

def generate_macro_report():
    try:
        macro = _cache.get("macro", {})
        fear_greed = _cache.get("fear_greed", 50)
        vix = macro.get("^VIX", {})
        ixic = macro.get("^IXIC", {})
        ks11 = macro.get("^KS11", {})
        gold = macro.get("GC=F", {})
        oil = macro.get("CL=F", {})
        dollar = macro.get("DX-Y.NYB", {})
        vix_price = vix.get("price", 20); vix_change = vix.get("change_pct", 0)
        gold_change = gold.get("change_pct", 0); oil_change = oil.get("change_pct", 0)
        dollar_change = dollar.get("change_pct", 0); ixic_change = ixic.get("change_pct", 0); ks11_change = ks11.get("change_pct", 0)
        if vix_price > 30: market_phase = "고변동성 공포 장세"; summary = f"VIX {vix_price:.1f}로 시장 변동성이 극도로 높은 상태입니다. 역사적으로 VIX 30+ 구간은 중기 저점 형성 구간과 일치합니다."
        elif vix_price > 20: market_phase = "변동성 확대 구간"; summary = f"VIX {vix_price:.1f}로 평균 이상의 변동성이 지속되고 있습니다. 중장기 분할 매수 기회가 형성되는 구간입니다."
        elif vix_price > 15: market_phase = "정상 변동성 구간"; summary = f"VIX {vix_price:.1f}로 시장이 안정적인 흐름을 보이고 있습니다. 모멘텀 종목 중심의 접근이 적합합니다."
        else: market_phase = "저변동성 강세장"; summary = f"VIX {vix_price:.1f}로 시장 변동성이 매우 낮습니다. 과도한 레버리지는 주의가 필요합니다."
        if vix_price > 30 and fear_greed < 25: pattern = "2020년 3월 COVID 저점"; pattern_desc = "현재 공포지수와 VIX 수준은 2020년 3월 코로나 저점과 유사합니다. 당시 S&P500은 6개월 내 50% 이상 반등했습니다."
        elif vix_price > 25 and ixic_change < -3: pattern = "2022년 금리 인상 사이클"; pattern_desc = "현재 패턴은 2022년 연준의 공격적 금리 인상 초기와 유사합니다. 반도체·AI 중심의 단계적 분할 매수가 유효했습니다."
        elif vix_price < 15 and fear_greed > 70: pattern = "2021년 유동성 장세"; pattern_desc = "현재 저변동성 고탐욕 환경은 2021년 유동성 장세와 유사합니다. 고평가 종목의 급락 리스크에 대비하여 분산 투자가 필요합니다."
        else: pattern = "2019년 금리 인하 사이클"; pattern_desc = "현재 시장은 2019년 연준 금리 인하 시점과 유사한 흐름을 보입니다. 선별적 접근이 중요합니다."
        opportunities = []; risks = []
        if gold_change > 0.5: opportunities.append(f"금 (GC=F +{gold_change:.1f}%): 안전자산 수요 증가. 달러 약세와 지정학적 리스크 헤지 수단으로 유효.")
        if vix_price > 25: opportunities.append("고변동성 역발상 매수: VIX 25+ 구간은 역사적으로 중기 저점 형성 구간. 우량주 분할 매수 기회.")
        if dollar_change < -0.5: opportunities.append(f"달러 약세 ({dollar_change:+.1f}%): 원자재·신흥국 강세 환경. 반도체, 소재 섹터 수혜 예상.")
        if ixic_change > 1: opportunities.append(f"나스닥 강세 (+{ixic_change:.1f}%): 기술주 모멘텀 유지 중. AI·반도체 관련주 추세 추종 유효.")
        if ks11_change > 1: opportunities.append(f"코스피 강세 (+{ks11_change:.1f}%): 국내 대형주 모멘텀 회복. 삼성전자, SK하이닉스 수혜.")
        if vix_change > 10: risks.append(f"VIX 급등 (+{vix_change:.1f}%): 단기 시장 충격 가능성. 레버리지 축소 및 현금 비중 확대 권고.")
        if oil_change > 3: risks.append(f"유가 급등 (WTI +{oil_change:.1f}%): 인플레이션 재점화 우려. 성장주 밸류에이션 압박 가능.")
        if fear_greed > 75: risks.append(f"과도한 탐욕 (공포지수 {fear_greed}): 시장 과열 신호. 포지션 비중 점검 필요.")
        if ixic_change < -2: risks.append(f"나스닥 하락 ({ixic_change:.1f}%): 기술주 조정 진행 중. 추격 매수 자제.")
        if not opportunities: opportunities.append("현재 특정 섹터의 명확한 기회 신호 없음. 관망 후 신호 확인 대기.")
        if not risks: risks.append("현재 시장 환경 안정적. 특별한 위험 요인 감지되지 않음.")
        return {"market_phase": market_phase, "summary": summary, "pattern": pattern, "pattern_desc": pattern_desc, "opportunities": opportunities[:4], "risks": risks[:4], "generated_at": datetime.now().isoformat(), "vix": vix_price, "fear_greed": fear_greed}
    except Exception as e:
        print(f"매크로 리포트 생성 오류: {e}")
        return {}

def get_smart_money_picks():
    try:
        results = []
        for ticker, info in SCREENING_UNIVERSE.items():
            score_data = calculate_stock_score(ticker)
            if not score_data: continue
            rec = _cache["recommendations"].get(ticker)
            buy_price = rec.get("buy1") if rec else None
            results.append({"ticker": ticker, "name": info["name"], "sector": info["sector"], "score": score_data["score"], "grade": get_grade(score_data["score"]), "current_price": score_data["current_price"], "buy_price": buy_price, "upside": score_data["upside"], "rsi": score_data["rsi"], "momentum_1m": score_data["momentum_1m"], "currency": score_data["currency"]})
        results.sort(key=lambda x: x["score"], reverse=True)
        print(f"✅ 스마트픽 {len(results[:10])}개 계산 완료")
        return results[:10]
    except Exception as e:
        print(f"스마트픽 오류: {e}")
        return []

def get_kr_market_status():
    try:
        kr_tz = pytz.timezone('Asia/Seoul')
        now = datetime.now(kr_tz)
        t = now.hour * 60 + now.minute
        weekday = now.weekday()
        if weekday >= 5: return "휴장"
        elif 8*60 <= t < 8*60+30:      return "호가접수"
        elif 8*60+30 <= t < 9*60:      return "장전시간외"
        elif 9*60 <= t < 15*60+30:     return "정규"
        elif 15*60+30 <= t < 15*60+40: return "장마감"
        elif 15*60+40 <= t < 16*60:    return "장후시간외"
        elif 16*60 <= t < 18*60:       return "시간외단일가"
        else: return "장외"
    except: return "정규"

def get_us_market_status():
    try:
        us_tz = pytz.timezone('America/New_York')
        now = datetime.now(us_tz)
        t = now.hour * 60 + now.minute
        weekday = now.weekday()
        if weekday >= 5: return "휴장"
        elif 4*60 <= t < 9*60+30: return "프리마켓"
        elif 9*60+30 <= t < 16*60: return "정규"
        elif 16*60 <= t < 20*60: return "애프터마켓"
        else: return "휴장"
    except: return "정규"

def get_macro():
    result = {}
    for ticker, name in MACRO_TICKERS.items():
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = info.last_price
            prev = info.previous_close
            change_pct = ((price - prev) / prev) * 100 if prev and prev != 0 else 0
            result[ticker] = {"name": name, "price": round(price, 2), "change_pct": round(change_pct, 2)}
        except Exception as e:
            print(f"매크로 오류 {ticker}: {e}")
    return result

def get_fear_greed():
    try:
        res = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = res.json()
        return int(float(data["fear_and_greed"]["score"]))
    except: return 50

def get_news():
    try:
        res = requests.get("https://feeds.bbci.co.uk/news/business/rss.xml", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        news = []
        for item in items[:10]:
            title = item.find("title")
            if title is not None: news.append(title.text)
        return news if news else ["글로벌 시장 모니터링 중..."]
    except Exception as e:
        print(f"뉴스 오류: {e}")
        return ["뉴스 연결 중...", "잠시 후 자동 업데이트됩니다"]

def check_emergency_news(news_list):
    text = " ".join(news_list).lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw.lower() in text: return True, kw
    return False, None

def check_price_emergency(ticker, current_price):
    history = _cache["price_history"].get(ticker, [])
    if len(history) < 2: return False, 0
    oldest = history[0]
    if oldest == 0: return False, 0
    change_pct = ((current_price - oldest) / oldest) * 100
    if abs(change_pct) >= 3: return True, round(change_pct, 2)
    return False, round(change_pct, 2)

def check_macro_emergency():
    macro = _cache.get("macro", {})
    ixic_change = macro.get("^IXIC", {}).get("change_pct", 0)
    ks11_change = macro.get("^KS11", {}).get("change_pct", 0)
    if ixic_change <= -1.0: return True, f"나스닥 {ixic_change}% 급락"
    if ks11_change <= -1.0: return True, f"코스피 {ks11_change}% 급락"
    return False, None

def update_price_history(ticker, price):
    if ticker not in _cache["price_history"]:
        _cache["price_history"][ticker] = []
    history = _cache["price_history"][ticker]
    history.append(price)
    if len(history) > 60: history.pop(0)

_kis_token = None
_kis_token_expires = None

# ★ KIS 토큰 — 만료 30분 전 자동 갱신 + 강제 갱신 옵션
def get_kis_token(force_refresh=False):
    global _kis_token, _kis_token_expires
    if not force_refresh and _kis_token and _kis_token_expires:
        if datetime.now() < _kis_token_expires - timedelta(minutes=30):
            return _kis_token
    if not KIS_APP_KEY or not KIS_APP_SECRET:
        return None
    try:
        url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
        body = {"grant_type": "client_credentials", "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET}
        res = requests.post(url, json=body, timeout=10)
        data = res.json()
        _kis_token = data.get("access_token")
        _kis_token_expires = datetime.now() + timedelta(hours=23)
        print(f"✅ KIS 토큰 갱신 완료: {datetime.now().isoformat()}")
        return _kis_token
    except Exception as e:
        print(f"KIS 토큰 오류: {e}")
        return None

# ★ KIS 우선 데이터 + 시간외 캐시 보존
def get_kr_stock_kis(ticker):
    market_status = get_kr_market_status()
    kr_tz = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kr_tz)
    t_min = now_kst.hour * 60 + now_kst.minute

    try:
        token = get_kis_token()
        if not token:
            result = get_kr_stock_yf(ticker)
            # 캐시된 유효 가격이 있으면 우선 사용
            if ticker in _cache["kr_last_valid_price"] and result:
                cached = _cache["kr_last_valid_price"][ticker]
                result["price"] = cached["price"]
                result["change"] = cached["change"]
                result["change_pct"] = cached["change_pct"]
                result["source"] = f"{cached['source']}(캐시)"
            if result: result["market_status"] = market_status
            return result

        url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": KIS_APP_KEY,
            "appsecret": KIS_APP_SECRET,
            "tr_id": "FHKST01010100",
        }
        params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": ticker}
        res = requests.get(url, headers=headers, params=params, timeout=5)
        data = res.json().get("output", {})
        price = float(data.get("stck_prpr", 0))
        change = float(data.get("prdy_vrss", 0))
        change_pct = float(data.get("prdy_ctrt", 0))
        source = "KIS실시간"

        # 호가접수 / 장전시간외: 예상 체결가 조회
        if market_status in ("호가접수", "장전시간외"):
            try:
                headers2 = {**headers, "tr_id": "FHKST01010400"}
                res2 = requests.get(url, headers=headers2, params=params, timeout=5)
                data2 = res2.json().get("output", {})
                pre_price = float(data2.get("ovtm_untp_prpr", 0) or 0)
                if pre_price > 0:
                    price = pre_price
                    change = float(data2.get("ovtm_untp_prdy_vrss", 0) or 0)
                    change_pct = float(data2.get("ovtm_untp_prdy_ctrt", 0) or 0)
                    source = "KIS장전"
            except: pass

        # ★ 시간외단일가(16~18시) + 장후(18~20시): 시간외 가격 조회
        if market_status in ("시간외단일가", "장후시간외") or (18*60 <= t_min < 20*60):
            try:
                headers2 = {**headers, "tr_id": "FHKST01010400"}
                res2 = requests.get(url, headers=headers2, params=params, timeout=5)
                data2 = res2.json().get("output", {})
                ot_price = float(data2.get("ovtm_untp_prpr", 0) or 0)
                if ot_price > 0:
                    price = ot_price
                    change = float(data2.get("ovtm_untp_prdy_vrss", 0) or 0)
                    change_pct = float(data2.get("ovtm_untp_prdy_ctrt", 0) or 0)
                    source = "KIS시간외"
            except: pass

        # ★ 유효한 가격이면 캐시 저장 (장외에서도 마지막 유효가 보존)
        if price > 0:
            _cache["kr_last_valid_price"][ticker] = {
                "price": price, "change": change,
                "change_pct": change_pct, "source": source,
                "saved_at": datetime.now().isoformat(),
            }
            update_price_history(ticker, price)
            return {
                "ticker": ticker, "name": KR_STOCKS.get(ticker, ticker),
                "price": price, "change": change, "change_pct": change_pct,
                "currency": "KRW", "source": source,
                "market_status": market_status, "updated": datetime.now().isoformat(),
            }
        else:
            # KIS가 0 반환 → 캐시된 마지막 유효가 사용
            if ticker in _cache["kr_last_valid_price"]:
                cached = _cache["kr_last_valid_price"][ticker]
                print(f"⚠️ {ticker} KIS 0반환 → 캐시 사용: {cached['price']}")
                return {
                    "ticker": ticker, "name": KR_STOCKS.get(ticker, ticker),
                    "price": cached["price"], "change": cached["change"],
                    "change_pct": cached["change_pct"], "currency": "KRW",
                    "source": f"{cached['source']}(캐시)",
                    "market_status": market_status, "updated": datetime.now().isoformat(),
                }
            result = get_kr_stock_yf(ticker)
            if result: result["market_status"] = market_status
            return result

    except Exception as e:
        print(f"KIS 오류 {ticker}: {e}")
        # 오류 시에도 캐시된 유효가 우선
        if ticker in _cache["kr_last_valid_price"]:
            cached = _cache["kr_last_valid_price"][ticker]
            return {
                "ticker": ticker, "name": KR_STOCKS.get(ticker, ticker),
                "price": cached["price"], "change": cached["change"],
                "change_pct": cached["change_pct"], "currency": "KRW",
                "source": f"{cached['source']}(캐시)",
                "market_status": market_status, "updated": datetime.now().isoformat(),
            }
        result = get_kr_stock_yf(ticker)
        if result: result["market_status"] = market_status
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
        return {"ticker": ticker, "name": KR_STOCKS.get(ticker, ticker), "price": round(price, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "currency": "KRW", "source": "yfinance", "market_status": get_kr_market_status(), "updated": datetime.now().isoformat()}
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
        return {"ticker": ticker, "name": US_STOCKS.get(ticker, ticker), "price": round(price, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "currency": "USD", "source": "yfinance", "market_status": get_us_market_status(), "updated": datetime.now().isoformat()}
    except Exception as e:
        return {"ticker": ticker, "name": US_STOCKS.get(ticker, ticker), "error": str(e)}

def analyze_news_keywords(news_list):
    text = " ".join(news_list).lower()
    bad_keywords = {"war": 0.05, "전쟁": 0.05, "sanction": 0.04, "제재": 0.04, "ban": 0.03, "규제": 0.03, "crash": 0.04, "crisis": 0.03, "rate hike": 0.03, "금리": 0.02, "tariff": 0.04, "관세": 0.04, "recession": 0.04, "침체": 0.04, "default": 0.05, "파산": 0.05, "inflation": 0.02, "인플레": 0.02}
    discount = 0.0; triggered = []
    for keyword, weight in bad_keywords.items():
        if keyword in text: discount += weight; triggered.append(keyword)
    return min(discount, 0.15), triggered

def get_sniper_scenario(fear_greed, discount, triggered, is_emergency=False, emergency_reason=None):
    if is_emergency and emergency_reason:
        return f"🚨 긴급 상황입니다. {emergency_reason}. 3차 벙커 타점을 즉시 하향 조정합니다. 대기하십시오."
    if fear_greed >= 70 or discount >= 0.10:
        kw = ", ".join(triggered[:3]) if triggered else "시장 공황"
        return f"지옥문이 열리기 직전입니다. 3차 지하벙커까지 전력을 분산하십시오. 감지된 악재: {kw}"
    elif fear_greed >= 50 or discount >= 0.05: return "전선이 흔들리고 있습니다. 1차 타점 소량 진입 후 추가 하락을 대기하십시오."
    elif fear_greed >= 30: return "안개가 짙습니다. 분할 매수 전략을 유지하며 신호를 기다리십시오."
    else: return "탐욕 구간 진입이 감지됩니다. 추격 매수는 금물. 눌림목에서 저격하십시오."

def calculate_recommendation(ticker, is_emergency=False, emergency_reason=None):
    try:
        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="6mo", interval="1d")
        if df is None or len(df) == 0: return None
        prices = df["Close"].dropna().tolist()
        if len(prices) == 0: return None

        # ★ 현재가: KIS 캐시 우선
        if ticker in _cache["kr_last_valid_price"]:
            price = _cache["kr_last_valid_price"][ticker]["price"]
        else:
            price = prices[-1]

        # ★ 이동평균선 계산
        ma20  = sum(prices[-20:])  / min(20,  len(prices))
        ma60  = sum(prices[-60:])  / min(60,  len(prices))
        ma120 = sum(prices[-120:]) / min(120, len(prices)) if len(prices) >= 60 else ma60

        # ★ 2주 박스권 하단 (14일 최저)
        box_low = min(prices[-14:]) if len(prices) >= 14 else price * 0.93

        # ★ RSI
        rsi = calculate_rsi(prices[-30:] if len(prices) >= 30 else prices)

        # ★ VIX 변동성 가중치
        macro = _cache.get("macro", {})
        vix = macro.get("^VIX", {}).get("price", 20)
        vix_multiplier = 1.0
        if vix > 40:   vix_multiplier = 1.30  # 극단적 공포
        elif vix > 30: vix_multiplier = 1.20
        elif vix > 25: vix_multiplier = 1.12
        elif vix > 20: vix_multiplier = 1.06
        else:          vix_multiplier = 1.00

        # ★ 뉴스 심리 가중치
        news_list = _cache.get("news", [])
        discount, triggered = analyze_news_keywords(news_list)

        # ★ 위험 키워드 메모리 추가 패널티
        risk_memory = _cache.get("risk_keyword_memory", {})
        now = datetime.now()
        extra_discount = 0.0
        for kw, ts in risk_memory.items():
            hours_ago = (now - datetime.fromisoformat(ts)).total_seconds() / 3600
            if hours_ago < 6:    extra_discount += 0.06
            elif hours_ago < 12: extra_discount += 0.04
            elif hours_ago < 24: extra_discount += 0.02
        extra_discount = min(extra_discount, 0.15)
        discount = min(discount + extra_discount, 0.20)

        if is_emergency: discount = min(discount + 0.05, 0.25)

        # ★ 동적 타점 계산
        # 1차: 2주 박스권 하단 or MA20 중 낮은 값 → -7~10% 수준
        buy1_base = min(box_low, ma20) * 0.98
        buy1 = round(buy1_base * (1 - discount * 0.3), 2)

        # 2차: MA60~MA120 구간 → -15~20% 수준
        buy2_base = min(ma60, ma120) * 0.97
        buy2 = round(buy2_base * (1 - discount * 0.5) * vix_multiplier * 0.97, 2)

        # 3차: 역사적 저점 or 극단 공포 구간 → -30% 이하
        hist_low = min(prices) if prices else price * 0.60
        buy3_base = max(hist_low * 1.02, price * 0.65)  # 역사적 저점 or 현재가 35% 아래
        buy3 = round(buy3_base * (1 - discount * 0.7) * vix_multiplier * 0.94, 2)

        # 타점 역전 방지
        buy1 = min(buy1, price * 0.93)
        buy2 = min(buy2, buy1 * 0.88)
        buy3 = min(buy3, buy2 * 0.82)

        # 매도/손절
        sell = round(price * (1.10 + rsi * 0.0005), 2)  # RSI 반영 목표가
        stop_loss = round(buy3 * 0.93, 2)

        # ★ 시나리오 문구
        fear_greed_score = _cache.get("fear_greed", 50)
        scenario = get_sniper_scenario(fear_greed_score, discount, triggered, is_emergency, emergency_reason)

        # ★ 전략적 근거 한 줄
        strategic_brief = ""
        if risk_memory:
            top_risk = list(risk_memory.keys())[0]
            strategic_brief = f"⚠️ {top_risk} 리스크 메모리 활성 — 벙커 타점 {round(extra_discount*100)}% 추가 하향 적용"
        elif vix > 30:
            strategic_brief = f"VIX {vix:.0f} 극단 공포 — 2·3차 벙커 중심 분할 매집 구간"
        elif discount > 0.08:
            strategic_brief = f"악재 가중치 {round(discount*100)}% 적용 — 타점 보수적 조정 완료"
        elif rsi < 35:
            strategic_brief = f"RSI {rsi} 과매도 — 1차 정찰대 타점 근접, 기술적 반등 기대"
        else:
            strategic_brief = f"MA60({round(ma60):,}) 지지 확인 중 — 분할 매수 대기"

        return {
            "ticker": ticker, "current": price,
            "buy1": buy1, "buy2": buy2, "buy3": buy3,
            "sell": sell, "stop_loss": stop_loss,
            "is_bad_news": discount > 0.03,
            "discount_pct": round(discount * 100, 1),
            "triggered_keywords": triggered[:5],
            "scenario": scenario,
            "strategic_brief": strategic_brief,
            "is_emergency": is_emergency,
            "emergency_reason": emergency_reason,
            "currency": "KRW" if len(ticker) == 6 and ticker.isdigit() else "USD",
            "updated_at": datetime.now().isoformat(),
            "indicators": {
                "rsi": rsi, "ma20": round(ma20, 2),
                "ma60": round(ma60, 2), "ma120": round(ma120, 2),
                "box_low": round(box_low, 2), "vix_mult": round(vix_multiplier, 2),
            }
        }
    except Exception as e:
        print(f"추천 계산 오류 {ticker}: {e}")
        return None

_last_strategy_update = None
_last_morning_wake = None

async def background_updater():
    global _last_strategy_update, _last_morning_wake
    while True:
        try:
            kr_tz = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(kr_tz)
            t_min = now_kst.hour * 60 + now_kst.minute
            weekday = now_kst.weekday()

            # ★ 매시 정각 KIS 토큰 자동 갱신
            now_check = datetime.now()
            if now_check.minute == 0 and now_check.second < 10:
                get_kis_token(force_refresh=True)

            # 아침 8시 강제 깨우기
            is_morning_open = (weekday < 5 and 8*60 <= t_min < 8*60+5)
            morning_date = now_kst.date()
            if is_morning_open and _last_morning_wake != morning_date:
                print("🌅 08:00 장 개장 준비 — 전략/감성 강제 재계산")
                _last_strategy_update = None
                _last_morning_wake = morning_date
                get_kis_token(force_refresh=True)  # ★ 장 시작 시 토큰 강제 갱신

            _cache["market_status"] = get_kr_market_status()
            _cache["kr"] = [get_kr_stock_kis(t) for t in KR_STOCKS]
            _cache["us"] = [get_us_stock(t) for t in US_STOCKS]
            _cache["macro"] = get_macro()
            _cache["news"] = get_news()
            _cache["fear_greed"] = get_fear_greed()
            _cache["timestamp"] = datetime.now().isoformat()
            _cache["news_sentiment"] = get_news_sentiment(_cache["news"])
            _cache["sector_flow"] = get_sector_flow()

            is_emergency = False; emergency_reason = None
            news_emergency, news_kw = check_emergency_news(_cache["news"])
            if news_emergency: is_emergency = True; emergency_reason = f"긴급 뉴스 감지: {news_kw}"
            macro_emergency, macro_reason = check_macro_emergency()
            if macro_emergency: is_emergency = True; emergency_reason = macro_reason
            for stock in _cache["kr"] + _cache["us"]:
                if not stock or "error" in stock: continue
                ticker = stock.get("ticker"); price = stock.get("price", 0)
                if price:
                    price_emergency, price_change = check_price_emergency(ticker, price)
                    if price_emergency: is_emergency = True; emergency_reason = f"{stock.get('name', ticker)} {price_change:+.1f}% 급변"

            now = datetime.now()
            should_update = (is_emergency or _last_strategy_update is None or (now - _last_strategy_update).seconds >= 3600)
            if should_update:
                for ticker in list(KR_STOCKS.keys()) + list(US_STOCKS.keys()):
                    rec = calculate_recommendation(ticker, is_emergency, emergency_reason)
                    if rec: _cache["recommendations"][ticker] = rec
                _cache["smart_picks"] = get_smart_money_picks()
                _cache["macro_report"] = generate_macro_report()
                _last_strategy_update = now
                print(f"{'🚨 긴급' if is_emergency else '📊 정기'} 전략 업데이트 완료: {now.isoformat()}")

            _cache["is_emergency"] = is_emergency
            _cache["emergency_reason"] = emergency_reason
            s = _cache["news_sentiment"]
            # 캐시 상태 로그
            cached_count = len(_cache["kr_last_valid_price"])
            print(f"✅ {_cache['timestamp']} | {_cache['market_status']} | 심리:{s.get('score','?')} | KIS캐시:{cached_count}종목")
        except Exception as e:
            print(f"업데이트 오류: {e}")
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    _cache["krx_map"] = load_krx_stock_list()
    # ★ 앱 시작 시 KIS 토큰 즉시 발급
    token = get_kis_token(force_refresh=True)
    print(f"🚀 앱 시작 | KIS토큰: {'✅' if token else '❌'}")
    asyncio.create_task(background_updater())
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    cached_prices = {k: v["price"] for k, v in _cache["kr_last_valid_price"].items()}
    return {"status": "AI Stock Terminal API 🚀", "timestamp": datetime.now().isoformat(), "kis_token": "✅ 활성" if _kis_token else "❌ 없음", "cached_prices": cached_prices}

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

@app.get("/api/smart-picks")
def smart_picks():
    return _cache["smart_picks"] if _cache["smart_picks"] else []

@app.get("/api/macro-report")
def macro_report():
    return _cache["macro_report"] if _cache["macro_report"] else generate_macro_report()

@app.get("/api/stock-analysis/{ticker}")
def stock_analysis(ticker: str):
    score_data = calculate_stock_score(ticker)
    if not score_data: return {"error": "분석 실패"}
    return {"ticker": ticker, "analysis": generate_stock_analysis(ticker, score_data), "score": score_data}

@app.get("/api/chart/{ticker}")
def get_chart(ticker: str, interval: str = "5m", period: str = "5d"):
    try:
        VALID_INTERVALS = {"1m", "5m", "60m", "1d"}
        VALID_PERIODS   = {"1d", "5d", "1mo", "1y"}
        if interval not in VALID_INTERVALS: interval = "5m"
        if period not in VALID_PERIODS: period = "5d"

        is_kr = len(ticker) == 6 and ticker.isdigit()
        yf_ticker = f"{ticker}.KS" if is_kr else ticker
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period=period, interval=interval)
        if df is None or len(df) == 0: return []

        is_intraday = interval in ("1m", "5m", "60m")
        kr_tz = pytz.timezone('Asia/Seoul')
        et_tz = pytz.timezone('America/New_York')

        result = []
        for idx, row in df.iterrows():
            try:
                if idx.tzinfo is None:
                    local_tz = kr_tz if is_kr else et_tz
                    idx = idx.tz_localize(local_tz)
                ts = int(idx.timestamp())
                label = idx.strftime("%H:%M") if is_intraday else idx.strftime("%Y-%m-%d")
                result.append({
                    "timestamp": ts, "time": label,
                    "open":   round(float(row["Open"]),  2),
                    "high":   round(float(row["High"]),  2),
                    "low":    round(float(row["Low"]),   2),
                    "close":  round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })
            except: continue

        result.sort(key=lambda x: x["timestamp"])

        # ★ 캐시된 KIS 실시간 가격으로 마지막 캔들 덮어쓰기
        if is_kr and ticker in _cache["kr_last_valid_price"] and result:
            cached = _cache["kr_last_valid_price"][ticker]
            live_price = cached["price"]
            last = result[-1]
            result[-1] = {
                **last,
                "close": live_price,
                "high":  max(last["high"], live_price),
                "low":   min(last["low"],  live_price),
            }

        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/recommend/{ticker}")
def get_recommend(ticker: str):
    if ticker in _cache["recommendations"]: return _cache["recommendations"][ticker]
    rec = calculate_recommendation(ticker)
    if rec: _cache["recommendations"][ticker] = rec; return rec
    return {"error": "계산 실패"}

@app.get("/api/search/{query}")
def search_stock(query: str):
    try:
        q = query.strip().lower()
        if q in STOCK_NAME_MAP: ticker = STOCK_NAME_MAP[q]
        elif q in _cache["krx_map"]: ticker = _cache["krx_map"][q]
        elif any('\uac00' <= c <= '\ud7a3' for c in q):
            return {"error": f"'{query}' 검색 실패. 국내주식은 종목코드(예: 272210)로 검색해주세요."}
        else: ticker = query.upper().strip()
        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
        stock = yf.Ticker(yf_ticker)
        try:
            info = stock.fast_info
            price = float(info.last_price) if info.last_price else 0
            prev  = float(info.previous_close) if info.previous_close else 0
        except:
            df = stock.history(period="5d", interval="1d")
            if df is None or len(df) == 0: return {"error": f"'{query}' 종목을 찾을 수 없습니다"}
            price = float(df["Close"].dropna().iloc[-1])
            prev  = float(df["Close"].dropna().iloc[-2]) if len(df) > 1 else price
        # ★ KIS 캐시 가격 우선
        is_kr = len(ticker) == 6 and ticker.isdigit()
        if is_kr and ticker in _cache["kr_last_valid_price"]:
            cached = _cache["kr_last_valid_price"][ticker]
            price = cached["price"]
            change = cached["change"]
            change_pct = cached["change_pct"]
        else:
            change = price - prev
            change_pct = (change / prev) * 100 if prev else 0
        rec = calculate_recommendation(ticker)
        return {"ticker": ticker, "price": round(price, 2), "change": round(change, 2), "change_pct": round(change_pct, 2), "currency": "KRW" if is_kr else "USD", "recommendation": rec}
    except Exception as e:
        return {"error": f"검색 실패: {str(e)}"}

@app.get("/api/news-sentiment")
def news_sentiment():
    return _cache["news_sentiment"] if _cache["news_sentiment"] else get_news_sentiment()

@app.get("/api/sector-flow")
def sector_flow():
    return _cache["sector_flow"] if _cache["sector_flow"] else get_sector_flow()
# ★ GPT 스타일 — 순수 기술적 지표 중심 타점
def calculate_recommendation_tech(ticker):
    try:
        yf_ticker = f"{ticker}.KS" if len(ticker) == 6 and ticker.isdigit() else ticker
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period="3mo", interval="1d")
        if df is None or len(df) < 20: return None
        prices = df["Close"].dropna().tolist()

        # KIS 캐시 가격 우선
        if ticker in _cache["kr_last_valid_price"]:
            price = _cache["kr_last_valid_price"][ticker]["price"]
        else:
            price = prices[-1]

        ma5  = sum(prices[-5:])  / 5  if len(prices) >= 5  else price
        ma20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else price
        ma60 = sum(prices[-60:]) / 60 if len(prices) >= 60 else price

        rsi = calculate_rsi(prices[-30:] if len(prices) >= 30 else prices)

        if len(prices) >= 20:
            std20    = (sum((p - ma20)**2 for p in prices[-20:]) / 20) ** 0.5
            bb_lower = ma20 - 2 * std20
            bb_upper = ma20 + 2 * std20
        else:
            bb_lower = price * 0.95
            bb_upper = price * 1.05

        macro = _cache.get("macro", {})
        vix   = macro.get("^VIX", {}).get("price", 20)

        # ★ 핵심: 현재가보다 높은 지표는 타점으로 사용 안 함
        candidates = []
        if ma20 < price:    candidates.append(ma20 * 0.995)
        if bb_lower < price: candidates.append(bb_lower * 0.995)
        if ma60 < price:    candidates.append(ma60 * 0.985)

        # 60일 저점
        hist_low = min(prices[-60:]) if len(prices) >= 60 else price * 0.75
        if hist_low < price: candidates.append(hist_low * 1.01)

        # 후보가 없으면 현재가 기준 % 할인으로 생성
        if len(candidates) == 0:
            candidates = [price * 0.93, price * 0.87, price * 0.75]
        elif len(candidates) == 1:
            candidates.append(candidates[0] * 0.90)
            candidates.append(candidates[0] * 0.80)
        elif len(candidates) == 2:
            candidates.append(min(candidates) * 0.88)

        # ★ 내림차순 정렬 후 3개 선택
        candidates = sorted(set([round(c, 2) for c in candidates]), reverse=True)

        support1 = candidates[0]
        support2 = candidates[1]
        support3 = candidates[2] if len(candidates) > 2 else candidates[1] * 0.88

        # ★ VIX 가중치
        if vix > 30:
            support1 *= 0.97; support2 *= 0.96; support3 *= 0.95

        # ★ 타점 역전 방지 (안전장치)
        support1 = min(support1, price * 0.97)   # 반드시 현재가 아래
        support2 = min(support2, support1 * 0.90) # 1차보다 아래
        support3 = min(support3, support2 * 0.88) # 2차보다 아래

        target = max(bb_upper, ma20 * 1.05) if bb_upper > price else price * 1.08
        stop   = round(support3 * 0.93, 2)

        if rsi < 35:
            scenario = f"RSI {rsi} 과매도 + 볼린저 하단 이탈 — 기술적 반등 구간. MA20({round(ma20):,}) 회복 시 추세 전환 신호."
        elif price < ma20:
            scenario = f"현재가 MA20({round(ma20):,}) 하회 중 — 이평선 저항 구간. MA20 돌파 확인 후 분할 진입 권장."
        elif price > bb_upper:
            scenario = f"볼린저 상단 돌파 — 단기 과열 구간. 눌림목({round(ma20):,}) 대기 후 재진입."
        else:
            scenario = f"MA5({round(ma5):,}) 기준 추세 추종 구간. 분할 매수 유효."

        return {
            "ticker": ticker, "current": price,
            "buy1": round(support1, 2),
            "buy2": round(support2, 2),
            "buy3": round(support3, 2),
            "sell": round(target, 2),
            "stop_loss": stop,
            "scenario": scenario,
            "is_bad_news": False, "discount_pct": 0, "is_emergency": False,
            "currency": "KRW" if len(ticker) == 6 and ticker.isdigit() else "USD",
            "updated_at": datetime.now().isoformat(),
            "model": "GPT",
            "indicators": {
                "rsi": rsi, "ma5": round(ma5, 2),
                "ma20": round(ma20, 2), "ma60": round(ma60, 2),
                "bb_upper": round(bb_upper, 2), "bb_lower": round(bb_lower, 2),
            }
        }
    except Exception as e:
        print(f"기술적 추천 오류 {ticker}: {e}")
        return None

@app.get("/api/recommend-tech/{ticker}")
def get_recommend_tech(ticker: str):
    rec = calculate_recommendation_tech(ticker)
    if rec: return rec
    return {"error": "기술적 분석 실패"}

@app.websocket("/ws/stocks")
async def websocket_stocks(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = {
                "kr": _cache["kr"], "us": _cache["us"],
                "macro": _cache["macro"], "news": _cache["news"],
                "fear_greed": _cache["fear_greed"],
                "market_status": _cache["market_status"],
                "is_emergency": _cache.get("is_emergency", False),
                "emergency_reason": _cache.get("emergency_reason", None),
                "recommendations": _cache["recommendations"],
                "smart_picks": _cache["smart_picks"],
                "macro_report": _cache["macro_report"],
                "news_sentiment": _cache["news_sentiment"],
                "sector_flow": _cache["sector_flow"],
                "timestamp": datetime.now().isoformat(),
            }
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("클라이언트 연결 종료")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)