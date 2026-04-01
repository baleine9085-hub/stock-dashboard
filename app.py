import streamlit as st
import json, os, subprocess
from datetime import datetime
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="AI 주식 대시보드", page_icon="📈", layout="wide")

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
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "buy_low": buy_low,
            "buy_high": buy_high,
            "target": target,
            "stop_loss": stop_loss,
        }
    except:
        return None

@st.cache_data(ttl=300)
def get_chart(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", auto_adjust=True, progress=False)
        return df.dropna()
    except:
        return None

def make_chart(df, ticker):
    fig = go.Figure(go.Candlestick(
        x=df.index,
        open=df["Open"].squeeze(), high=df["High"].squeeze(),
        low=df["Low"].squeeze(), close=df["Close"].squeeze(),
        increasing_line_color="#00e676", decreasing_line_color="#ff4d6d"))
    ma20 = df["Close"].rolling(20).mean()
    ma50 = df["Close"].rolling(50).mean()
    fig.add_trace(go.Scatter(x=df.index, y=ma20.squeeze(),
        line=dict(color="#00d4ff", width=1.5, dash="dot"), name="MA20"))
    fig.add_trace(go.Scatter(x=df.index, y=ma50.squeeze(),
        line=dict(color="#ffb300", width=1.5, dash="dot"), name="MA50"))
    fig.update_layout(
        paper_bgcolor="#0f1629", plot_bgcolor="#0a0e1a",
        font=dict(color="#e2e8f0"),
        xaxis=dict(gridcolor="#1e2a45"),
        yaxis=dict(gridcolor="#1e2a45"),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0,r=0,t=30,b=0), height=350,
        title=f"{ticker} — 3개월 캔들차트",
        legend=dict(bgcolor="#0f1629"))
    return fig

def make_heatmap(flows):
    if not flows: return None
    fig = go.Figure(go.Treemap(
        labels=[e["섹터"] for e in flows], parents=[""]*len(flows),
        values=[abs(e["등락(%)"])*10+e["자금(백만$)"]/100 for e in flows],
        customdata=[(e["등락(%)"], e["자금(백만$)"]) for e in flows],
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%",
        marker=dict(colors=[e["등락(%)"] for e in flows],
            colorscale=[[0,"#ff4d6d"],[0.5,"#1e2a45"],[1,"#00e676"]], cmid=0),
        textfont=dict(color="#fff", size=13)))
    fig.update_layout(paper_bgcolor="#0a0e1a", margin=dict(l=0,r=0,t=10,b=0), height=360)
    return fig

# ── 모달창 정의 ──────────────────────────────────────────────
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

    # 헤더
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown(f"## {ticker} ({name})")
        color = "🟢" if change >= 0 else "🔴"
        st.markdown(f"### {color} ${price:,.2f}  `{change:+.2f}%`")
    with col_b:
        if in_range:
            st.success("✅ 매수 적기!")
        else:
            st.info("📊 모니터링 중")

    st.divider()

    # 매수범위 / 목표가 / 손절가
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("📌 매수 범위", f"${buy_low:,.2f} ~ ${buy_high:,.2f}")
    with c2: st.metric("🎯 목표가", f"${target:,.2f}", f"+{((target-price)/price*100):.1f}%")
    with c3: st.metric("🛑 손절가", f"${stop_loss:,.2f}", f"-{((price-stop_loss)/price*100):.1f}%")

    st.divider()

    # 주가 차트
    st.markdown("#### 📈 주가 차트 (3개월)")
    df = get_chart(ticker)
    if df is not None and len(df) > 5:
        st.plotly_chart(make_chart(df, ticker), use_container_width=True)

    st.divider()

    # AI 분석 (추천 종목에 있는 경우)
    if stock_data:
        col_x, col_y = st.columns(2)
        with col_x:
            st.markdown("#### 🤖 AI 투자 이유")
            reasons = stock_data.get("reasons", [])
            for r in reasons:
                st.markdown(f"✅ {r}")

        with col_y:
            st.markdown("#### 📊 기술적 분석")
            rsi  = stock_data.get("rsi", 0)
            macd = stock_data.get("macd", "")
            trend = stock_data.get("ma_trend", "")

            rsi_color = "🟢" if 40 <= rsi <= 65 else "🔴"
            macd_color = "🟢" if macd == "golden" else "🔴"
            trend_color = "🟢" if trend == "bullish" else "🔴"

            st.markdown(f"{rsi_color} **RSI**: {rsi:.0f} {'(적정 구간)' if 40<=rsi<=65 else '(주의)'}")
            st.markdown(f"{macd_color} **MACD**: {macd}")
            st.markdown(f"{trend_color} **추세**: {trend}")
            st.markdown(f"**점수**: {stock_data.get('score', 0)}/100")

        ai_text = stock_data.get("ai_analysis", "")
        if ai_text and "기술적 지표" not in ai_text and "오류" not in ai_text:
            st.divider()
            st.markdown("#### 🧠 Gemini AI 분석")
            st.info(ai_text)
    else:
        st.markdown("#### 📊 기술적 분석")
        st.info("AI 추천 종목에 포함되면 상세 분석이 표시됩니다.")

# ── 관심 종목 설정 ────────────────────────────────────────────
WATCHLIST = {
    "NVDA": "엔비디아",
    "SNDK": "샌디스크",
    "MU":   "마이크론",
    "GLW":  "코닝",
    "TSLA": "테슬라",
    "AAPL": "애플",
    "AMD":  "AMD",
    "AVGO": "브로드컴",
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
report_data, filename = load_report()
if not report_data:
    st.warning("리포트가 없어요! 새로 분석 실행 버튼을 눌러주세요.")
    st.stop()

# ── 주요 지수 ─────────────────────────────────────────────────
st.subheader("📊 주요 지수 & 자산")
snap = report_data.get("market_snapshot", {})
cols = st.columns(len(snap))
for i, (name, info) in enumerate(snap.items()):
    with cols[i]:
        st.metric(name, f"{info['price']:,.2f}", f"{info['change_pct']:+.2f}%")

st.divider()
tab0, tab1, tab2, tab3 = st.tabs(["⭐ 관심 종목", "🏆 AI 추천 종목", "🗺 시장 지도", "🤖 AI 리포트"])

# ── 탭0: 관심 종목 ────────────────────────────────────────────
with tab0:
    st.subheader("⭐ 관심 종목")
    if st.button("🔄 실시간 새로고침", key="refresh_watch"):
        st.cache_data.clear()
        st.rerun()

    recs = report_data.get("recommendations", [])
    rec_map = {s["ticker"]: s for s in recs}

    tickers = list(WATCHLIST.items())
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
                        h1, h2 = st.columns([3, 1])
                        with h1:
                            st.markdown(f"**{ticker}** ({name})")
                        with h2:
                            if in_range:
                                st.success("매수 적기")
                        st.metric("현재가", f"${price:,.2f}", f"{change:+.2f}%")
                        a, b, c = st.columns(3)
                        with a: st.metric("매수 범위", f"${buy_low:,.0f}~{buy_high:,.0f}")
                        with b: st.metric("목표가", f"${target:,.0f}", f"+{((target-price)/price*100):.1f}%")
                        with c: st.metric("손절가", f"${stop_loss:,.0f}", f"-{((price-stop_loss)/price*100):.1f}%")

                        if st.button(f"🔍 상세 분석 보기", key=f"modal_{ticker}", use_container_width=True):
                            show_stock_modal(ticker, name, info, rec_map.get(ticker))
                else:
                    st.info(f"{ticker} 로딩 중...")

# ── 탭1: AI 추천 종목 ─────────────────────────────────────────
with tab1:
    recs = report_data.get("recommendations", [])
    if not recs:
        st.info("데이터 없음")
    else:
        if "sel" not in st.session_state:
            st.session_state.sel = recs[0]["ticker"]
        L, R = st.columns([1, 2])
        with L:
            st.markdown("#### 종목 리스트")
            for i, s in enumerate(recs):
                buy_low  = s.get("buy_low",  s["price"] * 0.97)
                buy_high = s.get("buy_high", s["price"] * 1.01)
                in_range = buy_low <= s["price"] <= buy_high
                badge = "🟢" if in_range else ""
                st.write(f"#{i+1} **{s['ticker']}** {badge}")
                st.write(f"${s['price']:,.2f} | {s['ret_5d']:+.1f}% | 점수:{s['score']}")
                if st.button("선택", key=f"b_{s['ticker']}", use_container_width=True):
                    st.session_state.sel = s["ticker"]
                    st.rerun()
        with R:
            sel = next((s for s in recs if s["ticker"] == st.session_state.sel), recs[0])
            price     = sel["price"]
            buy_low   = sel.get("buy_low",   round(price * 0.97, 2))
            buy_high  = sel.get("buy_high",  round(price * 1.01, 2))
            target    = sel.get("target",    round(price * 1.15, 2))
            stop_loss = sel.get("stop_loss", round(price * 0.93, 2))
            in_range  = buy_low <= price <= buy_high

            st.markdown(f"### {sel['ticker']} — ${price:,.2f}")
            if in_range:
                st.success("🟢 매수 적기!")

            c1, c2, c3 = st.columns(3)
            with c1: st.metric("RSI", f"{sel['rsi']:.0f}")
            with c2: st.metric("MACD", sel["macd"])
            with c3: st.metric("추세", sel["ma_trend"])

            ca, cb, cc = st.columns(3)
            with ca: st.metric("매수 범위", f"${buy_low:,.2f}~${buy_high:,.2f}")
            with cb: st.metric("목표가", f"${target:,.2f}", f"+{((target-price)/price*100):.1f}%")
            with cc: st.metric("손절가", f"${stop_loss:,.2f}", f"-{((price-stop_loss)/price*100):.1f}%")

            df = get_chart(sel["ticker"])
            if df is not None and len(df) > 5:
                st.plotly_chart(make_chart(df, sel["ticker"]), use_container_width=True)

            st.markdown("**선정 이유:** " + " / ".join(sel.get("reasons", [])))
            ai = sel.get("ai_analysis", "")
            if ai and "기술적 지표" not in ai:
                st.info(f"🤖 {ai}")

# ── 탭2: 시장 지도 ────────────────────────────────────────────
with tab2:
    st.subheader("섹터별 시장 지도")
    flows = report_data.get("etf_flows", [])
    h = make_heatmap(flows)
    if h:
        st.plotly_chart(h, use_container_width=True)
    if flows:
        cols = st.columns(len(flows))
        for i, e in enumerate(flows):
            with cols[i]:
                st.metric(e["섹터"], f"${e['자금(백만$)']:,.0f}M", f"{e['등락(%)']:+.1f}%")

# ── 탭3: AI 리포트 ────────────────────────────────────────────
with tab3:
    st.subheader("🤖 AI 종합 시장 분석")
    fred = report_data.get("fred_indicators", {})
    if fred:
        cols = st.columns(len(fred))
        for i, (n, v) in enumerate(fred.items()):
            with cols[i]:
                st.metric(n, str(v["value"]))
        st.divider()
    ai = report_data.get("ai_market_analysis", "")
    if ai and "건너뜀" not in ai:
        st.markdown(ai)
    else:
        st.info("config.py에 GEMINI_API_KEY를 입력하면 AI 분석이 표시됩니다.")

st.divider()
st.caption("⚠ 본 대시보드는 참고용입니다. 투자 손실에 대한 책임은 투자자 본인에게 있습니다.")