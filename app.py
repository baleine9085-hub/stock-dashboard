import streamlit as st
import json, os, subprocess
from datetime import datetime, timedelta
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="AI 주식 대시보드", page_icon="📈", layout="wide")

# ── 데이터 함수 ───────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_report():
    d = "reports"
    if not os.path.exists(d): return None, None
    files = sorted([f for f in os.listdir(d) if f.endswith(".json")], reverse=True)
    if not files: return None, None
    with open(os.path.join(d, files[0]), "r", encoding="utf-8") as f:
        return json.load(f), files[0]

def get_stock_info(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if len(hist) < 2: return None
        price = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2])
        change_pct = ((price - prev) / prev) * 100
        volume = int(hist["Volume"].iloc[-1])
        buy_low   = round(price * 0.97, 2)
        buy_high  = round(price * 1.02, 2)
        target    = round(price * 1.15, 2)
        stop_loss = round(price * 0.93, 2)
        return {
            "price": round(price, 2), "change_pct": round(change_pct, 2),
            "volume": volume, "buy_low": buy_low, "buy_high": buy_high,
            "target": target, "stop_loss": stop_loss,
        }
    except:
        return None

@st.cache_data(ttl=300)
def get_kr_stock_info(code):
    try:
        import FinanceDataReader as fdr
        end = datetime.today()
        start = end - timedelta(days=60)
        df = fdr.DataReader(code, start, end)
        if len(df) < 2: return None
        price = float(df["Close"].iloc[-1])
        prev  = float(df["Close"].iloc[-2])
        change_pct = ((price - prev) / prev) * 100
        volume = int(df["Volume"].iloc[-1])

        # 20일 이동평균
        ma20 = df["Close"].rolling(20).mean().iloc[-1]
        above_ma20 = price > float(ma20)

        # 매물대 (거래량 가장 많은 가격대 = 저항선)
        df["price_band"] = (df["Close"] // 1000) * 1000
        resistance = float(df.groupby("price_band")["Volume"].sum().idxmax())

        # 매수가: MA20 지지 시 MA20 근처, 아니면 현재가 -3%
        if above_ma20:
            buy_low  = round(float(ma20) * 0.99)
            buy_high = round(float(ma20) * 1.02)
        else:
            buy_low  = round(price * 0.97)
            buy_high = round(price * 1.00)

        target    = round(resistance * 0.98) if resistance > price else round(price * 1.10)
        stop_loss = round(price * 0.93)

        return {
            "price":      round(price),
            "change_pct": round(change_pct, 2),
            "volume":     volume,
            "ma20":       round(float(ma20)),
            "above_ma20": above_ma20,
            "resistance": round(resistance),
            "buy_low":    buy_low,
            "buy_high":   buy_high,
            "target":     target,
            "stop_loss":  stop_loss,
        }
    except Exception as e:
        return None

@st.cache_data(ttl=300)
def get_kr_index():
    try:
        import FinanceDataReader as fdr
        end = datetime.today()
        start = end - timedelta(days=5)
        kospi  = fdr.DataReader("KS11", start, end)
        kosdaq = fdr.DataReader("KQ11", start, end)
        result = {}
        for name, df in [("코스피", kospi), ("코스닥", kosdaq)]:
            if len(df) >= 2:
                price = float(df["Close"].iloc[-1])
                prev  = float(df["Close"].iloc[-2])
                result[name] = {
                    "price": round(price, 2),
                    "change_pct": round(((price-prev)/prev)*100, 2)
                }
        return result
    except:
        return {}

@st.cache_data(ttl=300)
def get_kr_chart(code):
    try:
        import FinanceDataReader as fdr
        end = datetime.today()
        start = end - timedelta(days=14)
        return fdr.DataReader(code, start, end)
    except:
        return None

@st.cache_data(ttl=300)
def get_chart(ticker):
    try:
        df = yf.download(ticker, period="7d", interval="1d", auto_adjust=True, progress=False)
        return df.dropna()
    except:
        return None

def make_chart(df, ticker, is_kr=False):
    if is_kr:
        open_  = df["Open"]
        high   = df["High"]
        low    = df["Low"]
        close  = df["Close"]
    else:
        open_  = df["Open"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        close  = df["Close"].squeeze()

    # 한국식: 상승=빨강, 하락=파랑
    inc_color = "#ff4d4d" if is_kr else "#00e676"
    dec_color = "#4d79ff" if is_kr else "#ff4d6d"

    fig = go.Figure(go.Candlestick(
        x=df.index, open=open_, high=high, low=low, close=close,
        increasing_line_color=inc_color, decreasing_line_color=dec_color))
    ma20 = close.rolling(20).mean()
    fig.add_trace(go.Scatter(x=df.index, y=ma20,
        line=dict(color="#00d4ff", width=1.5, dash="dot"), name="MA20"))
    fig.update_layout(
        paper_bgcolor="#0f1629", plot_bgcolor="#0a0e1a",
        font=dict(color="#e2e8f0"), xaxis=dict(gridcolor="#1e2a45"),
        yaxis=dict(gridcolor="#1e2a45"), xaxis_rangeslider_visible=False,
        margin=dict(l=0,r=0,t=30,b=0), height=350,
        title=f"{ticker} 차트")
    return fig

def make_heatmap(flows):
    if not flows: return None
    fig = go.Figure(go.Treemap(
        labels=[e["섹터"] for e in flows], parents=[""]*len(flows),
        values=[abs(e["등락(%)"])*10+e["자금(백만$)"]/100 for e in flows],
        customdata=[(e["등락(%)"], e["자금(백만$)"]) for e in flows],
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%",
        marker=dict(colors=[e["등락(%)"] for e in flows],
            colorscale=[[0,"#4d79ff"],[0.5,"#1e2a45"],[1,"#ff4d4d"]], cmid=0),
        textfont=dict(color="#fff", size=13)))
    fig.update_layout(paper_bgcolor="#0a0e1a", margin=dict(l=0,r=0,t=10,b=0), height=360)
    return fig

# ── 모달: 미국 종목 ───────────────────────────────────────────
@st.dialog("종목 상세 분석", width="large")
def show_stock_modal(ticker, name, info, stock_data=None):
    if not info:
        st.error("데이터를 불러올 수 없어요.")
        return
    price     = info["price"]
    change    = info["change_pct"]
    buy_low   = info["buy_low"]
    buy_high  = info["buy_high"]
    target    = info["target"]
    stop_loss = info["stop_loss"]
    in_range  = buy_low <= price <= buy_high

    col_a, col_b = st.columns([2,1])
    with col_a:
        st.markdown(f"## {ticker} ({name})")
        color = "🟢" if change >= 0 else "🔴"
        st.markdown(f"### {color} ${price:,.2f}  `{change:+.2f}%`")
    with col_b:
        if in_range: st.success("✅ 매수 적기!")
        else: st.info("📊 모니터링 중")

    st.divider()
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("📌 매수 범위", f"${buy_low:,.2f}~${buy_high:,.2f}")
    with c2: st.metric("🎯 목표가", f"${target:,.2f}", f"+{((target-price)/price*100):.1f}%")
    with c3: st.metric("🛑 손절가", f"${stop_loss:,.2f}", f"-{((price-stop_loss)/price*100):.1f}%")

    st.divider()
    st.markdown("#### 📈 주가 차트 (7일)")
    df = get_chart(ticker)
    if df is not None and len(df) > 2:
        st.plotly_chart(make_chart(df, ticker), use_container_width=True)

    if stock_data:
        col_x, col_y = st.columns(2)
        with col_x:
            st.markdown("#### 🤖 AI 투자 이유")
            for r in stock_data.get("reasons", []):
                st.markdown(f"✅ {r}")
        with col_y:
            st.markdown("#### 📊 기술적 분석")
            rsi   = stock_data.get("rsi", 0)
            macd  = stock_data.get("macd", "")
            trend = stock_data.get("ma_trend", "")
            st.markdown(f"{'🟢' if 40<=rsi<=65 else '🔴'} **RSI**: {rsi:.0f}")
            st.markdown(f"{'🟢' if macd=='golden' else '🔴'} **MACD**: {macd}")
            st.markdown(f"{'🟢' if trend=='bullish' else '🔴'} **추세**: {trend}")
            st.markdown(f"**점수**: {stock_data.get('score',0)}/100")
        ai_text = stock_data.get("ai_analysis","")
        if ai_text and "기술적 지표" not in ai_text:
            st.divider()
            st.markdown("#### 🧠 Gemini AI 분석")
            st.info(ai_text)

# ── 모달: 한국 종목 ───────────────────────────────────────────
@st.dialog("국내 종목 상세 분석", width="large")
def show_kr_modal(code, name, info):
    if not info:
        st.error("데이터를 불러올 수 없어요.")
        return
    price     = info["price"]
    change    = info["change_pct"]
    buy_low   = info["buy_low"]
    buy_high  = info["buy_high"]
    target    = info["target"]
    stop_loss = info["stop_loss"]
    in_range  = buy_low <= price <= buy_high

    # 한국식 색상 (상승=빨강, 하락=파랑)
    change_color = "🔴" if change >= 0 else "🔵"
    col_a, col_b = st.columns([2,1])
    with col_a:
        st.markdown(f"## {name} ({code})")
        st.markdown(f"### {change_color} ₩{price:,}  `{change:+.2f}%`")
    with col_b:
        if in_range: st.success("✅ 매수 적기!")
        else: st.info("📊 모니터링 중")

    st.divider()
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("📌 매수 범위", f"₩{buy_low:,}~{buy_high:,}")
    with c2: st.metric("🎯 목표가(저항선)", f"₩{target:,}", f"+{((target-price)/price*100):.1f}%")
    with c3: st.metric("🛑 손절가", f"₩{stop_loss:,}", f"-{((price-stop_loss)/price*100):.1f}%")

    st.divider()
    ma20 = info.get("ma20", 0)
    c4, c5 = st.columns(2)
    with c4:
        st.metric("20일 이동평균", f"₩{ma20:,}",
            "✅ 위에서 지지 중" if info.get("above_ma20") else "⚠️ 아래에 있음")
    with c5:
        st.metric("매물대 저항선", f"₩{info.get('resistance',0):,}")

    st.divider()
    st.markdown("#### 📈 주가 차트 (14일)")
    df = get_kr_chart(code)
    if df is not None and len(df) > 2:
        st.plotly_chart(make_chart(df, name, is_kr=True), use_container_width=True)

# ── 관심 종목 설정 ────────────────────────────────────────────
US_WATCHLIST = {
    "NVDA": "엔비디아", "SNDK": "샌디스크", "MU": "마이크론",
    "GLW":  "코닝",     "TSLA": "테슬라",   "AAPL": "애플",
    "AMD":  "AMD",      "AVGO": "브로드컴",
}

KR_WATCHLIST = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "005380": "현대차",
    "000270": "기아",
    "068270": "셀트리온",
    "035720": "카카오",
    "051910": "LG화학",
}

# ── 헤더 ──────────────────────────────────────────────────────
st.title("⚡ AI STOCK TERMINAL")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
if st.button("🔄 새로 분석 실행"):
    with st.spinner("분석 중..."):
        subprocess.run(["python", "main.py"])
    st.cache_data.clear()
    st.rerun()

st.divider()

# ── 메인 탭: 국내/해외 분리 ──────────────────────────────────
main_tab1, main_tab2 = st.tabs(["🇰🇷 국내 시장", "🇺🇸 해외 시장"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇰🇷 국내 시장 탭
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with main_tab1:
    # 코스피/코스닥 지수
    st.subheader("📊 국내 주요 지수")
    kr_index = get_kr_index()
    if kr_index:
        idx_cols = st.columns(len(kr_index))
        for i, (name, info) in enumerate(kr_index.items()):
            with idx_cols[i]:
                change = info["change_pct"]
                # 한국식: 상승=빨강, 하락=파랑
                delta_str = f"{change:+.2f}%"
                st.metric(name, f"{info['price']:,.2f}", delta_str)
    else:
        st.info("지수 데이터 로딩 중...")

    st.divider()

    # 국내 관심 종목
    st.subheader("⭐ 국내 관심 종목")
    if st.button("🔄 새로고침", key="kr_refresh"):
        st.cache_data.clear()
        st.rerun()

    kr_tickers = list(KR_WATCHLIST.items())
    for row in range(0, len(kr_tickers), 2):
        c1, c2 = st.columns(2)
        for col, (code, name) in zip([c1, c2], kr_tickers[row:row+2]):
            with col:
                info = get_kr_stock_info(code)
                if info:
                    price     = info["price"]
                    change    = info["change_pct"]
                    buy_low   = info["buy_low"]
                    buy_high  = info["buy_high"]
                    target    = info["target"]
                    stop_loss = info["stop_loss"]
                    in_range  = buy_low <= price <= buy_high

                    # 한국식 색상
                    change_icon = "🔴" if change >= 0 else "🔵"

                    with st.container(border=True):
                        h1, h2 = st.columns([3,1])
                        with h1:
                            st.markdown(f"**{name}** `{code}`")
                        with h2:
                            if in_range: st.success("매수 적기")

                        st.metric("현재가", f"₩{price:,}", f"{change:+.2f}%")

                        a, b, c = st.columns(3)
                        with a: st.metric("매수 범위", f"₩{buy_low:,}~{buy_high:,}")
                        with b: st.metric("목표가", f"₩{target:,}", f"+{((target-price)/price*100):.1f}%")
                        with c: st.metric("손절가", f"₩{stop_loss:,}", f"-{((price-stop_loss)/price*100):.1f}%")

                        if st.button("🔍 상세 분석", key=f"kr_{code}", use_container_width=True):
                            show_kr_modal(code, name, info)
                else:
                    with st.container(border=True):
                        st.markdown(f"**{name}** `{code}`")
                        st.info("데이터 로딩 중...")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇺🇸 해외 시장 탭
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with main_tab2:
    report_data, filename = load_report()

    # 주요 지수
    st.subheader("📊 주요 지수 & 자산")
    if report_data:
        snap = report_data.get("market_snapshot", {})
        cols = st.columns(len(snap))
        for i, (name, info) in enumerate(snap.items()):
            with cols[i]:
                st.metric(name, f"{info['price']:,.2f}", f"{info['change_pct']:+.2f}%")
    st.divider()

    if not report_data:
        st.warning("리포트가 없어요! 새로 분석 실행 버튼을 눌러주세요.")
    else:
        tab0, tab1, tab2, tab3 = st.tabs(["⭐ 관심 종목", "🏆 AI 추천 종목", "🗺 시장 지도", "🤖 AI 리포트"])

        # 관심 종목
        with tab0:
            st.subheader("⭐ 미국 관심 종목")
            if st.button("🔄 새로고침", key="us_refresh"):
                st.cache_data.clear()
                st.rerun()

            recs = report_data.get("recommendations", [])
            rec_map = {s["ticker"]: s for s in recs}
            tickers = list(US_WATCHLIST.items())
            for row in range(0, len(tickers), 2):
                c1, c2 = st.columns(2)
                for col, (ticker, name) in zip([c1, c2], tickers[row:row+2]):
                    with col:
                        info = get_stock_info(ticker)
                        if info:
                            price     = info["price"]
                            change    = info["change_pct"]
                            buy_low   = info["buy_low"]
                            buy_high  = info["buy_high"]
                            target    = info["target"]
                            stop_loss = info["stop_loss"]
                            in_range  = buy_low <= price <= buy_high
                            with st.container(border=True):
                                h1, h2 = st.columns([3,1])
                                with h1: st.markdown(f"**{ticker}** ({name})")
                                with h2:
                                    if in_range: st.success("매수 적기")
                                st.metric("현재가", f"${price:,.2f}", f"{change:+.2f}%")
                                a,b,c = st.columns(3)
                                with a: st.metric("매수 범위", f"${buy_low:,.0f}~{buy_high:,.0f}")
                                with b: st.metric("목표가", f"${target:,.0f}", f"+{((target-price)/price*100):.1f}%")
                                with c: st.metric("손절가", f"${stop_loss:,.0f}", f"-{((price-stop_loss)/price*100):.1f}%")
                                if st.button("🔍 상세 분석", key=f"us_{ticker}", use_container_width=True):
                                    show_stock_modal(ticker, name, info, rec_map.get(ticker))
                        else:
                            st.info(f"{ticker} 로딩 중...")

        # AI 추천 종목
        with tab1:
            recs = report_data.get("recommendations", [])
            if not recs:
                st.info("데이터 없음")
            else:
                if "sel" not in st.session_state:
                    st.session_state.sel = recs[0]["ticker"]
                L, R = st.columns([1,2])
                with L:
                    st.markdown("#### 종목 리스트")
                    for i, s in enumerate(recs):
                        buy_low  = s.get("buy_low",  s["price"]*0.97)
                        buy_high = s.get("buy_high", s["price"]*1.01)
                        in_range = buy_low <= s["price"] <= buy_high
                        st.write(f"#{i+1} **{s['ticker']}** {'🟢' if in_range else ''}")
                        st.write(f"${s['price']:,.2f} | {s['ret_5d']:+.1f}% | 점수:{s['score']}")
                        if st.button("선택", key=f"b_{s['ticker']}", use_container_width=True):
                            st.session_state.sel = s["ticker"]
                            st.rerun()
                with R:
                    sel = next((s for s in recs if s["ticker"]==st.session_state.sel), recs[0])
                    price     = sel["price"]
                    buy_low   = sel.get("buy_low",   round(price*0.97,2))
                    buy_high  = sel.get("buy_high",  round(price*1.01,2))
                    target    = sel.get("target",    round(price*1.15,2))
                    stop_loss = sel.get("stop_loss", round(price*0.93,2))
                    in_range  = buy_low <= price <= buy_high
                    st.markdown(f"### {sel['ticker']} — ${price:,.2f}")
                    if in_range: st.success("🟢 매수 적기!")
                    c1,c2,c3 = st.columns(3)
                    with c1: st.metric("RSI", f"{sel['rsi']:.0f}")
                    with c2: st.metric("MACD", sel["macd"])
                    with c3: st.metric("추세", sel["ma_trend"])
                    ca,cb,cc = st.columns(3)
                    with ca: st.metric("매수 범위", f"${buy_low:,.2f}~${buy_high:,.2f}")
                    with cb: st.metric("목표가", f"${target:,.2f}", f"+{((target-price)/price*100):.1f}%")
                    with cc: st.metric("손절가", f"${stop_loss:,.2f}", f"-{((price-stop_loss)/price*100):.1f}%")
                    df = get_chart(sel["ticker"])
                    if df is not None and len(df) > 2:
                        st.plotly_chart(make_chart(df, sel["ticker"]), use_container_width=True)
                    st.markdown("**선정 이유:** "+" / ".join(sel.get("reasons",[])))
                    ai = sel.get("ai_analysis","")
                    if ai and "기술적 지표" not in ai:
                        st.info(f"🤖 {ai}")

        # 시장 지도
        with tab2:
            st.subheader("섹터별 시장 지도")
            flows = report_data.get("etf_flows",[])
            h = make_heatmap(flows)
            if h: st.plotly_chart(h, use_container_width=True)
            if flows:
                cols = st.columns(len(flows))
                for i,e in enumerate(flows):
                    with cols[i]:
                        st.metric(e["섹터"], f"${e['자금(백만$)']:,.0f}M", f"{e['등락(%)']:+.1f}%")

        # AI 리포트
        with tab3:
            st.subheader("🤖 AI 종합 시장 분석")
            fred = report_data.get("fred_indicators",{})
            if fred:
                cols = st.columns(len(fred))
                for i,(n,v) in enumerate(fred.items()):
                    with cols[i]: st.metric(n, str(v["value"]))
                st.divider()
            ai = report_data.get("ai_market_analysis","")
            if ai and "건너뜀" not in ai: st.markdown(ai)
            else: st.info("config.py에 GEMINI_API_KEY를 입력하면 AI 분석이 표시됩니다.")

st.divider()
st.caption("⚠ 본 대시보드는 참고용입니다. 투자 손실에 대한 책임은 투자자 본인에게 있습니다.")