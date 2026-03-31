pythoncode = '''import streamlit as st
import json, os, subprocess
from datetime import datetime
import plotly.graph_objects as go
import yfinance as yf

st.set_page_config(page_title="AI 주식 대시보드", page_icon="📈", layout="wide")
st.markdown("""<style>
.stApp{background:#0a0e1a;color:#e2e8f0}
[data-testid="stMetric"]{background:#0f1629;border:1px solid #1e2a45;border-radius:12px;padding:16px!important}
[data-testid="stMetricValue"]{font-size:1.4rem!important;font-weight:700}
h1,h2,h3{color:#e2e8f0!important}
[data-testid="stExpander"]{background:#0f1629!important;border:1px solid #1e2a45!important;border-radius:10px!important}
.stButton button{background:#00d4ff18;border:1px solid #00d4ff44;color:#00d4ff;border-radius:10px;font-weight:600}
.stTabs [aria-selected="true"]{background:#1e2a45!important;color:#00d4ff!important}
#MainMenu,footer,header{visibility:hidden}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def load_report():
    d = "reports"
    if not os.path.exists(d): return None, None
    files = sorted([f for f in os.listdir(d) if f.endswith(".json")], reverse=True)
    if not files: return None, None
    with open(os.path.join(d, files[0]), "r", encoding="utf-8") as f:
        return json.load(f), files[0]

@st.cache_data(ttl=3600)
def get_chart(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d", auto_adjust=True, progress=False)
        return df.dropna()
    except: return None

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
        margin=dict(l=0,r=0,t=30,b=0), height=300,
        title=f"{ticker} 3개월 차트")
    return fig

def heatmap(flows):
    if not flows: return None
    fig = go.Figure(go.Treemap(
        labels=[e["섹터"] for e in flows], parents=[""]*len(flows),
        values=[abs(e["등락(%)"])*10+e["자금(백만$)"]/100 for e in flows],
        customdata=[(e["등락(%)"], e["자금(백만$)"]) for e in flows],
        texttemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%<br>$%{customdata[1]:,.0f}M",
        marker=dict(colors=[e["등락(%)"] for e in flows],
            colorscale=[[0,"#ff4d6d"],[0.5,"#1e2a45"],[1,"#00e676"]], cmid=0),
        textfont=dict(color="#fff", size=13)))
    fig.update_layout(paper_bgcolor="#0a0e1a", margin=dict(l=0,r=0,t=10,b=0), height=360)
    return fig

# 헤더
c1, c2 = st.columns([5,1])
with c1:
    st.markdown("<h1 style=\'background:linear-gradient(135deg,#00d4ff,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:2rem;font-weight:900;\'>⚡ AI STOCK TERMINAL</h1>", unsafe_allow_html=True)
    st.caption(f"🕐 {datetime.now().strftime(\'%Y년 %m월 %d일 %H:%M\')} 기준")
with c2:
    st.write("")
    if st.button("🔄 새로 분석 실행", use_container_width=True):
        with st.spinner("분석 중..."):
            subprocess.run(["python", "main.py"])
        st.cache_data.clear()
        st.rerun()

st.divider()
report_data, filename = load_report()
if not report_data:
    st.warning("⚠ 리포트가 없어요! 새로 분석 실행 버튼을 눌러주세요.")
    st.stop()
st.caption(f"📄 {filename}")

# 지수
st.subheader("📊 주요 지수 & 자산")
snap = report_data.get("market_snapshot", {})
cols = st.columns(len(snap))
for i,(name,info) in enumerate(snap.items()):
    with cols[i]: st.metric(name, f"{info[\'price\']:,.2f}", f"{info[\'change_pct\']:+.2f}%")

st.divider()
tab1,tab2,tab3 = st.tabs(["🏆 AI 추천 종목","🗺 시장 지도","🤖 AI 리포트"])

with tab1:
    recs = report_data.get("recommendations", [])
    if not recs: st.info("데이터 없음"); st.stop()
    if "sel" not in st.session_state: st.session_state.sel = recs[0]["ticker"]
    L, R = st.columns([1,2])
    with L:
        st.markdown("#### 종목 리스트")
        for i,s in enumerate(recs):
            rc = "#00e676" if s["ret_5d"]>=0 else "#ff4d6d"
            bc = "#00d4ff" if s["ticker"]==st.session_state.sel else "#1e2a45"
            st.markdown(f"<div style=\'background:#0f1629;border:1px solid {bc};border-radius:10px;padding:10px 14px;margin-bottom:6px;\'><div style=\'display:flex;justify-content:space-between;\'><span style=\'font-weight:800;color:#e2e8f0;font-family:monospace;\'>#{i+1} {s[\'ticker\']}</span><span style=\'font-size:11px;background:#00d4ff18;color:#00d4ff;border-radius:5px;padding:1px 6px;\'>{s[\'score\']}점</span></div><div style=\'display:flex;justify-content:space-between;margin-top:4px;\'><span style=\'color:#94a3b8;font-size:13px;\'>${s[\'price\']:,.2f}</span><span style=\'color:{rc};font-size:13px;font-weight:600;\'>{s[\'ret_5d\']:+.1f}%</span></div></div>", unsafe_allow_html=True)
            if st.button("선택", key=f"b_{s[\'ticker\']}", use_container_width=True):
                st.session_state.sel = s["ticker"]; st.rerun()
    with R:
        sel = next((s for s in recs if s["ticker"]==st.session_state.sel), recs[0])
        tc = "#00e676" if sel["ret_5d"]>=0 else "#ff4d6d"
        st.markdown(f"<div style=\'background:#0f1629;border:1px solid #1e2a45;border-radius:12px;padding:16px 20px;margin-bottom:16px;\'><span style=\'font-size:24px;font-weight:900;color:#00d4ff;font-family:monospace;\'>{sel[\'ticker\']}</span> <span style=\'font-size:20px;font-weight:700;color:#e2e8f0;\'>${sel[\'price\']:,.2f}</span> <span style=\'color:{tc};font-weight:600;\'>{sel[\'ret_5d\']:+.1f}%</span> <span style=\'background:#00d4ff18;color:#00d4ff;border-radius:6px;padding:2px 8px;font-size:11px;\'>점수 {sel[\'score\']}/100</span></div>", unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("RSI", f"{sel[\'rsi\']:.0f}")
        with c2: st.metric("MACD", sel["macd"])
        with c3: st.metric("추세", sel["ma_trend"])
        df = get_chart(sel["ticker"])
        if df is not None and len(df)>5:
            st.plotly_chart(candlestick(df, sel["ticker"]), use_container_width=True)
        if sel.get("reasons"):
            st.markdown("**선정 이유:** " + " · ".join(sel["reasons"]))
        ai = sel.get("ai_analysis","")
        if ai and "기술적 지표" not in ai and "오류" not in ai:
            st.info(f"🤖 {ai}")
        else:
            st.info("💡 config.py에 GEMINI_API_KEY를 입력하면 AI 분석이 표시됩니다.")

with tab2:
    st.subheader("🗺 섹터별 시장 지도")
    flows = report_data.get("etf_flows",[])
    h = heatmap(flows)
    if h: st.plotly_chart(h, use_container_width=True)
    if flows:
        cols = st.columns(len(flows))
        for i,e in enumerate(flows):
            with cols[i]: st.metric(e["섹터"], f"${e[\'자금(백만$)\']:,.0f}M", f"{e[\'등락(%)\']:+.1f}%")

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
    else: st.info("💡 config.py에 GEMINI_API_KEY를 입력하면 AI 시장 분석이 표시됩니다.")

st.divider()
st.caption("⚠ 본 대시보드는 참고용입니다. 투자 손실에 대한 책임은 투자자 본인에게 있습니다.")
'''
open('app.py','w',encoding='utf-8').write(code)
print('app.py 생성 완료!')
```