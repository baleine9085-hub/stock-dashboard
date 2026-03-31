import json
import os
from datetime import datetime
from rich.console import Console

console = Console()

def save_report(market_snapshot, fred_data, etf_flows, recommendations, ai_market_analysis, output_dir="reports"):
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    report = {
        "date":               today,
        "market_snapshot":    market_snapshot,
        "fred_indicators":    fred_data,
        "etf_flows":          etf_flows,
        "recommendations":    recommendations,
        "ai_market_analysis": ai_market_analysis,
    }

    json_path = os.path.join(output_dir, f"report_{today}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    txt_path = os.path.join(output_dir, f"report_{today}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"{'='*60}\n")
        f.write(f"  AI 주식 분석 리포트 - {today}\n")
        f.write(f"{'='*60}\n\n")
        f.write("[ 시장 현황 ]\n")
        for name, info in market_snapshot.items():
            sign = "+" if info["change_pct"] >= 0 else ""
            f.write(f"  {name:15s}: {info['price']:>10,.2f}  ({sign}{info['change_pct']:.2f}%)\n")
        f.write("\n[ AI 시장 분석 ]\n")
        f.write(ai_market_analysis + "\n")
        f.write("\n[ 추천 종목 TOP 10 ]\n")
        for i, stock in enumerate(recommendations, 1):
            f.write(f"\n  #{i} {stock['ticker']} - 점수: {stock['score']}/100\n")
            f.write(f"     현재가: ${stock['price']:,.2f} | 5일수익률: {stock['ret_5d']:+.1f}%\n")
            f.write(f"     RSI: {stock['rsi']} | MACD: {stock['macd']} | 추세: {stock['ma_trend']}\n")
            f.write(f"     이유: {', '.join(stock['reasons'])}\n")

    console.print(f"\n[green]✅ 리포트 저장 완료![/green]")
    console.print(f"   📄 JSON: {json_path}")
    console.print(f"   📝 텍스트: {txt_path}")
    return json_path, txt_path