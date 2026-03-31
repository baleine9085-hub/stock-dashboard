GEMINI_API_KEY = "AIzaSyBz85t5WjUQeHOxlIQd5p2Qv0_Z87VhTYs"
FRED_API_KEY   = "여기에_FRED_API_키_입력"

MARKET_SYMBOLS = {
    "S&P 500":    "^GSPC",
    "나스닥":      "^IXIC",
    "다우존스":    "^DJI",
    "공포지수(VIX)": "^VIX",
    "금":          "GC=F",
    "오일(WTI)":   "CL=F",
    "비트코인":    "BTC-USD",
    "달러/원":     "KRW=X",
    "달러인덱스":  "DX-Y.NYB",
}

SCREENING_UNIVERSE = [
"NVDA", "SNDK", "MU", "TSLA", "AAPL", "GLW",
    "MSFT", "GOOGL", "AMZN", "META", "AVGO",
    "AMD", "INTC", "QCOM", "AMAT", "LRCX",
    "JPM", "BAC", "GS", "MS", "V", "MA",
    "JNJ", "UNH", "PFE", "ABBV", "MRK",
    "COST", "WMT", "HD", "NKE", "MCD",
    "QQQ", "SPY", "SOXX", "XLK", "XLF",
]

DATA_PERIOD   = "3mo"
DATA_INTERVAL = "1d"
TOP_N_STOCKS  = 20