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

@st.cache_data(ttl=60)
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

@st.cache_data(ttl=3600)
def get_chart(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", auto_adjust=True, progress=False)
        return df.dropna()
    except:
        return None

def candlestick(df, ticker):
    fig = go.Figure(go.Candlestick(
        x=df.index,
        open=df["Open"].squeeze(), high=df["High"].squeeze(),
        low=df["Low"].squeeze(), close=df["Close"].squeeze(),
        increasing_line_color="#00e676", decreasing_line_color="#ff4d6d"))
    ma = df["Close"].rolling(20).mean()
    fig.add_trace(go.Scatter(x=df.index, y=ma.squeeze(),
        line=dict(color="#00d4ff", width=1.5, dash="dot"), name="MA20"))
    fig.update_layout(paper_bgcolor="#0a0e1a", plot_bgcolor="#0f1629",
        font=dict(color="#e2e8f0"), xaxis=dict(gridcolor="#1e2a45"),
        yaxis=dict(gridcolor="#1e2a45"), xaxis_rangeslider_visible=False,
        margin=dict(l=0,r=0,t=30,b=0), height=300)
    return fig

def heatmap(flows):
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

st.title("AI STOCK TERMINAL")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
if st.button("새로 분석 실행"):
    with st.spinner("분석 중..."):
        subprocess.run(["python", "main.py"])
    st.cache_data.clear()
    st.rerun()

st.divider()
report_data, filename = load_report()
if not report_data:
    st.warning("리포트가 없어요! 새로 분석 실행 버튼을 눌러주세요.")
    st.stop()

st.subheader("주요 지수 & 자산")
snap = report_data.get("market_snapshot", {})
cols = st.columns(len(snap))
for i, (name, info) in enumerate(snap.items()):
    with cols[i]:
        st.metric(name, f"{info['price']:,.2f}", f"{info['change_pct']:+.2f}%")

st.divider()
tab0, tab1, tab2, tab3 = st.tabs(["관심 종목", "AI 추천 종목", "시장 지도", "AI 리포트"])

with tab0:
    st.subheader("관심 종목")
if st.button("실시간 새로고침", key="refresh_watch"):
    st.cache_data.clear()
    st.rerun()
    if "watch_sel" not in st.session_state:
        st.session_state.watch_sel = list(WATCHLIST.keys())[0]

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
                        st.metric(label="현재가", value=f"${price:,.2f}", delta=f"{change:+.2f}%")
                        a, b, c = st.columns(3)
                        with a:
                            st.metric("매수 범위", f"${buy_low:,.0f}~{buy_high:,.0f}")
                        with b:
                            st.metric("목표가", f"${target:,.0f}", f"+{((target-price)/price*100):.1f}%")
                        with c:
                            st.metric("손절가", f"${stop_loss:,.0f}", f"-{((price-stop_loss)/price*100):.1f}%")
                        if st.button("차트 보기", key=f"w_{ticker}", use_container_width=True):
                            st.session_state.watch_sel = ticker
                            st.rerun()
                else:
                    st.info(f"{ticker} 로딩 중...")

    st.divider()
    sel_ticker = st.session_state.watch_sel
    sel_name   = WATCHLIST.get(sel_ticker, sel_ticker)
    st.subheader(f"{sel_ticker} ({sel_name}) 3개월 차트")
    df = get_chart(sel_ticker)
    if df is not None and len(df) > 5:
        st.plotly_chart(candlestick(df, sel_ticker), use_container_width=True)

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
                badge = "매수적기" if in_range else ""
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
                st.success("매수 적기! 현재가가 매수 범위 안에 있어요!")

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
                st.plotly_chart(candlestick(df, sel["ticker"]), use_container_width=True)

            st.markdown("**선정 이유:** " + " / ".join(sel.get("reasons", [])))
            ai = sel.get("ai_analysis", "")
            if ai and "기술적 지표" not in ai:
                st.info(f"AI 분석: {ai}")
            else:
                st.info("GEMINI_API_KEY를 config.py에 입력하면 AI 분석이 표시됩니다.")

with tab2:
    st.subheader("섹터별 시장 지도")
    flows = report_data.get("etf_flows", [])
    h = heatmap(flows)
    if h:
        st.plotly_chart(h, use_container_width=True)
    if flows:
        cols = st.columns(len(flows))
        for i, e in enumerate(flows):
            with cols[i]:
                st.metric(e["섹터"], f"${e['자금(백만$)']:,.0f}M", f"{e['등락(%)']:+.1f}%")

with tab3:
    st.subheader("AI 종합 시장 분석")
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
st.caption("본 대시보드는 참고용입니다. 투자 손실에 대한 책임은 투자자 본인에게 있습니다.")