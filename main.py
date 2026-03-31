import sys
import time
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

import config
from data.collector import (get_market_snapshot, get_stock_history,
                             get_fred_indicators, get_etf_flows,
                             print_market_table)
from analysis.screener import screen_stocks, print_recommendations
from analysis.ai_analyst import init_gemini, analyze_market, analyze_stocks
from output.report import save_report

console = Console()

def run_analysis():
    console.print(Panel(
        f"[bold yellow]🚀 AI 주식 분석 대시보드[/bold yellow]\n"
        f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        border_style="yellow",
    ))

    console.print(Rule("[bold]STEP 1: 시장 데이터 수집[/bold]"))
    market_snapshot = get_market_snapshot(config.MARKET_SYMBOLS)
    print_market_table(market_snapshot)

    fred_data = {}
    if config.FRED_API_KEY and config.FRED_API_KEY != "여기에_FRED_API_키_입력":
        fred_data = get_fred_indicators(config.FRED_API_KEY)

    etf_flows = get_etf_flows()

    console.print(Rule("[bold]STEP 2: 종목 스크리닝[/bold]"))
    stock_data = get_stock_history(
        tickers  = config.SCREENING_UNIVERSE,
        period   = config.DATA_PERIOD,
        interval = config.DATA_INTERVAL,
    )
    recommendations = screen_stocks(stock_data, top_n=config.TOP_N_STOCKS)
    print_recommendations(recommendations)

    ai_market_analysis = "AI 분석 건너뜀 (API 키 미설정)"
    if config.GEMINI_API_KEY and config.GEMINI_API_KEY != "여기에_제미나이_API_키_입력":
        console.print(Rule("[bold]STEP 3: AI 분석[/bold]"))
        try:
            model = init_gemini(config.GEMINI_API_KEY)
            ai_market_analysis = analyze_market(model, market_snapshot, fred_data, etf_flows)
            recommendations = analyze_stocks(model, recommendations)
        except Exception as e:
            console.print(f"[red]AI 분석 오류: {e}[/red]")

    console.print(Rule("[bold]STEP 4: 결과 저장[/bold]"))
    save_report(
        market_snapshot    = market_snapshot,
        fred_data          = fred_data,
        etf_flows          = etf_flows,
        recommendations    = recommendations,
        ai_market_analysis = ai_market_analysis,
    )

    console.print(Panel(
        "[bold green]✅ 분석 완료![/bold green]\n"
        "reports/ 폴더에서 오늘의 리포트를 확인하세요.",
        border_style="green",
    ))

if __name__ == "__main__":
    if "--auto" in sys.argv:
        import schedule
        schedule.every().day.at("07:00").do(run_analysis)
        run_analysis()
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_analysis()