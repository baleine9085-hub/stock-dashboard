import pandas as pd
from rich.console import Console
from rich.table import Table
from data.indicators import get_all_indicators

console = Console()

def screen_stocks(stock_data: dict, top_n: int = 10) -> list:
    console.print(f"\n[bold cyan]🔍 {len(stock_data)}개 종목 스크리닝 중...[/bold cyan]")
    results = []

    for ticker, df in stock_data.items():
        try:
            if len(df) < 30:
                continue
            indicators = get_all_indicators(df)
            price_now  = float(df["Close"].iloc[-1])
            price_5d   = float(df["Close"].iloc[-5])  if len(df) >= 5  else price_now
            price_20d  = float(df["Close"].iloc[-20]) if len(df) >= 20 else price_now
            ret_5d     = ((price_now - price_5d)  / price_5d)  * 100
            ret_20d    = ((price_now - price_20d) / price_20d) * 100
            high_52w   = float(df["High"].max())
            low_52w    = float(df["Low"].min())
            pos_52w    = (price_now - low_52w) / (high_52w - low_52w) * 100 if high_52w != low_52w else 50.0

            reasons = []
            if indicators["macd_cross"] == "golden":
                reasons.append("MACD 골든크로스")
            if indicators["ma_trend"] == "bullish":
                reasons.append("이동평균 정배열")
            if indicators["volume_surge"]:
                reasons.append(f"거래량 급증 ({indicators['vol_ratio']:.1f}x)")
            if 40 <= indicators["rsi"] <= 60:
                reasons.append("RSI 적정 구간")
            if indicators["bb_position"] == "lower":
                reasons.append("볼린저 하단 반등")
            if ret_5d > 3:
                reasons.append(f"5일 상승 +{ret_5d:.1f}%")

            results.append({
                "ticker":   ticker,
                "price":    round(price_now, 2),
                "ret_5d":   round(ret_5d, 2),
                "ret_20d":  round(ret_20d, 2),
                "pos_52w":  round(pos_52w, 1),
                "score":    indicators["score"],
                "rsi":      indicators["rsi"],
                "macd":     indicators["macd_cross"],
                "ma_trend": indicators["ma_trend"],
                "buy_low":   round(price_now * 0.97, 2),
                "buy_high":  round(price_now * 1.01, 2),
                "target":    round(price_now * 1.15, 2),
                "stop_loss": round(price_now * 0.93, 2),
                "reasons":  reasons if reasons else ["추가 모니터링 필요"],
            })
        except Exception as e:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    top_results = results[:top_n]
    console.print(f"  [green]✓ 상위 {len(top_results)}개 종목 선정 완료[/green]")
    return top_results

def print_recommendations(recommendations: list):
    table = Table(title="🏆 오늘의 추천 종목 TOP 10", show_header=True, header_style="bold yellow")
    table.add_column("순위",      style="bold", width=4,  justify="center")
    table.add_column("티커",      style="cyan",  width=7)
    table.add_column("현재가",    justify="right")
    table.add_column("5일수익률", justify="right")
    table.add_column("RSI",       justify="right")
    table.add_column("MACD",      justify="center")
    table.add_column("추세",      justify="center")
    table.add_column("점수",      justify="center")
    table.add_column("주요 이유", width=30)

    for i, stock in enumerate(recommendations, 1):
        ret_color   = "green" if stock["ret_5d"] >= 0 else "red"
        macd_color  = "green" if stock["macd"] == "golden" else "red" if stock["macd"] == "dead" else "white"
        trend_icon  = "🟢" if stock["ma_trend"] == "bullish" else "🔴" if stock["ma_trend"] == "bearish" else "⚪"
        score_color = "green" if stock["score"] >= 70 else "yellow" if stock["score"] >= 50 else "red"
        table.add_row(
            f"#{i}", stock["ticker"], f"${stock['price']:,.2f}",
            f"[{ret_color}]{stock['ret_5d']:+.1f}%[/{ret_color}]",
            f"{stock['rsi']:.0f}",
            f"[{macd_color}]{stock['macd']}[/{macd_color}]",
            trend_icon,
            f"[{score_color}]{stock['score']}[/{score_color}]",
            " · ".join(stock["reasons"][:2]),
        )
    console.print(table)