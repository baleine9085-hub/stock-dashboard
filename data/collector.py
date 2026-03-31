import yfinance as yf
import pandas as pd
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()

def get_market_snapshot(symbols: dict) -> dict:
    console.print("[bold cyan]📡 시장 데이터 수집 중...[/bold cyan]")
    result = {}
    for name, ticker in symbols.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="2d")
            if len(hist) < 2:
                continue
            today_close = hist["Close"].iloc[-1]
            prev_close  = hist["Close"].iloc[-2]
            change_pct  = ((today_close - prev_close) / prev_close) * 100
            volume      = hist["Volume"].iloc[-1]
            result[name] = {
                "ticker":     ticker,
                "price":      round(today_close, 2),
                "prev_close": round(prev_close, 2),
                "change_pct": round(change_pct, 2),
                "volume":     int(volume),
            }
            console.print(f"  [green]✓[/green] {name}: ${today_close:,.2f} ({change_pct:+.2f}%)")
        except Exception as e:
            console.print(f"  [red]✗ {name} 오류: {e}[/red]")
    return result

def get_stock_history(tickers: list, period: str = "3mo", interval: str = "1d") -> dict:
    console.print(f"\n[bold cyan]📊 {len(tickers)}개 종목 히스토리 수집 중...[/bold cyan]")
    stock_data = {}
    try:
        raw = yf.download(
            tickers=tickers, period=period, interval=interval,
            group_by="ticker", auto_adjust=True, progress=False,
        )
        for ticker in tickers:
            try:
                df = raw[ticker].copy() if len(tickers) > 1 else raw.copy()
                df.dropna(inplace=True)
                if len(df) > 10:
                    stock_data[ticker] = df
            except Exception:
                pass
        console.print(f"  [green]✓ {len(stock_data)}개 종목 수집 완료[/green]")
    except Exception as e:
        console.print(f"  [red]오류: {e}[/red]")
    return stock_data

def get_fred_indicators(fred_api_key: str) -> dict:
    try:
        from fredapi import Fred
        fred = Fred(api_key=fred_api_key)
        indicators = {
            "기준금리(%)":    "FEDFUNDS",
            "10년물 국채(%)": "DGS10",
            "2년물 국채(%)":  "DGS2",
            "CPI 물가지수":   "CPIAUCSL",
            "실업률(%)":      "UNRATE",
        }
        result = {}
        for name, series_id in indicators.items():
            try:
                series = fred.get_series(series_id)
                result[name] = {
                    "value": round(float(series.dropna().iloc[-1]), 2),
                    "date":  series.dropna().index[-1].strftime("%Y-%m-%d"),
                }
            except:
                result[name] = {"value": "N/A", "date": "N/A"}
        return result
    except Exception as e:
        console.print(f"[red]FRED 오류: {e}[/red]")
        return {}

def get_etf_flows(etf_tickers: dict = None) -> list:
    if etf_tickers is None:
        etf_tickers = {
            "기술(XLK)":     "XLK",
            "금융(XLF)":     "XLF",
            "헬스케어(XLV)": "XLV",
            "에너지(XLE)":   "XLE",
            "반도체(SOXX)":  "SOXX",
            "AI/성장(QQQ)":  "QQQ",
        }
    console.print("\n[bold cyan]💰 ETF 자금 흐름 분석 중...[/bold cyan]")
    flows = []
    for name, ticker in etf_tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if len(hist) < 2:
                continue
            today_close  = hist["Close"].iloc[-1]
            prev_close   = hist["Close"].iloc[-2]
            change_pct   = ((today_close - prev_close) / prev_close) * 100
            today_volume = hist["Volume"].iloc[-1]
            avg_volume   = hist["Volume"].mean()
            vol_ratio    = today_volume / avg_volume if avg_volume > 0 else 1.0
            dollar_volume = (today_volume * today_close) / 1_000_000
            flows.append({
                "섹터": name, "ticker": ticker,
                "가격": round(today_close, 2),
                "등락(%)": round(change_pct, 2),
                "거래량비율": round(vol_ratio, 2),
                "자금(백만$)": round(dollar_volume, 1),
            })
        except Exception as e:
            pass
    flows.sort(key=lambda x: x["자금(백만$)"], reverse=True)
    return flows

def print_market_table(snapshot: dict):
    table = Table(title="📈 시장 현황", show_header=True, header_style="bold magenta")
    table.add_column("자산",   style="cyan",  width=14)
    table.add_column("현재가", style="white", justify="right")
    table.add_column("전일대비", justify="right")
    table.add_column("거래량",  justify="right")
    for name, info in snapshot.items():
        change_str = f"{info['change_pct']:+.2f}%"
        color = "green" if info["change_pct"] >= 0 else "red"
        table.add_row(name, f"{info['price']:,}", f"[{color}]{change_str}[/{color}]", f"{info['volume']:,}")
    console.print(table)