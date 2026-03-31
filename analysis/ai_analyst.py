import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def init_gemini(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")

def analyze_market(model, market_snapshot, fred_data, etf_flows) -> str:
    console.print("\n[bold cyan]🤖 AI 시장 분석 중...[/bold cyan]")

    market_lines = "\n".join([
        f"- {name}: {info['price']:,} ({info['change_pct']:+.2f}%)"
        for name, info in market_snapshot.items()
    ])
    fred_lines = "\n".join([
        f"- {name}: {info['value']} ({info['date']})"
        for name, info in fred_data.items()
    ]) if fred_data else "FRED 데이터 없음"
    etf_lines = "\n".join([
        f"- {e['섹터']}: {e['등락(%)']:+.1f}%, 자금 ${e['자금(백만$)']:,.0f}M"
        for e in etf_flows[:5]
    ]) if etf_flows else "ETF 데이터 없음"

    prompt = f"""
당신은 전문 미국 주식 시장 애널리스트입니다.
아래 오늘의 시장 데이터를 바탕으로 한국어로 전문적인 시장 분석 리포트를 작성해주세요.

## 오늘의 주요 지수
{market_lines}

## 미국 경제 지표 (FRED)
{fred_lines}

## ETF 섹터별 자금 흐름
{etf_lines}

다음 형식으로 작성해주세요:
1. **오늘의 시장 요약** (3~4줄)
2. **핵심 이슈** (2~3가지)
3. **섹터 동향**
4. **투자자 유의사항**
5. **내일 전망** (한 문장)
"""
    try:
        response = model.generate_content(prompt)
        analysis = response.text
        console.print(Panel(Markdown(analysis), title="[bold green]📊 AI 시장 분석[/bold green]", border_style="green"))
        return analysis
    except Exception as e:
        console.print(f"[red]AI 분석 오류: {e}[/red]")
        return f"AI 분석 오류: {e}"

def analyze_stocks(model, recommendations: list) -> list:
    console.print("\n[bold cyan]🤖 종목별 AI 분석 중...[/bold cyan]")
    for stock in recommendations[:5]:
        prompt = f"""
종목: {stock['ticker']}
현재가: ${stock['price']:,.2f} | 5일수익률: {stock['ret_5d']:+.1f}%
RSI: {stock['rsi']} | MACD: {stock['macd']} | 추세: {stock['ma_trend']}
점수: {stock['score']}/100

이 종목에 대해 한국어로 2~3문장으로 간결하게:
1. 추천 핵심 이유
2. 주의할 리스크
3. 단기 매매 전략 힌트
"""
        try:
            response = model.generate_content(prompt)
            stock["ai_analysis"] = response.text
            console.print(f"  [green]✓ {stock['ticker']} 분석 완료[/green]")
        except Exception as e:
            stock["ai_analysis"] = f"분석 오류: {e}"

    for stock in recommendations[5:]:
        stock["ai_analysis"] = "기술적 지표 기반 선정"
    return recommendations