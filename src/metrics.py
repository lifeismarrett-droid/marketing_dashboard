"""집계 지표 계산.

일별 CTR(%)을 단순 평균하면 노출수 차이가 반영되지 않아 왜곡되므로,
기간 합계 KPI는 노출수/클릭수/전환수 합계 기준으로 다시 계산한다(가중평균).
"""

import pandas as pd


def weighted_ctr(impressions: pd.Series, clicks: pd.Series) -> float:
    total_impressions = impressions.sum()
    if total_impressions == 0:
        return 0.0
    return clicks.sum() / total_impressions * 100


def conversion_rate(clicks: pd.Series, conversions: pd.Series) -> float:
    total_clicks = clicks.sum()
    if total_clicks == 0:
        return 0.0
    return conversions.sum() / total_clicks * 100


def cpa(cost: pd.Series, conversions: pd.Series) -> float:
    total_conversions = conversions.sum()
    if total_conversions == 0:
        return float("nan")
    return cost.sum() / total_conversions


def pct_change(current: float, previous: float | None) -> float | None:
    """이전 값 대비 증감률(%). 이전 값이 없거나 0/NaN이면 비교 불가로 None."""
    if previous is None or pd.isna(previous) or previous == 0 or pd.isna(current):
        return None
    return (current - previous) / previous * 100


WEEKDAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]


def aggregate_by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    """요일별(월~일) 합계 및 가중평균 지표.

    df는 '요일', '노출수', '클릭수', '비용', '구독 신청' 컬럼이 필요하다.
    표본 일수가 요일마다 다를 수 있어 "일수" 컬럼을 함께 반환한다.
    """
    rows = []
    for day in WEEKDAY_ORDER:
        subset = df[df["요일"] == day]
        if subset.empty:
            continue
        rows.append(
            {
                "요일": day,
                "일수": len(subset),
                "노출수": subset["노출수"].sum(),
                "클릭수": subset["클릭수"].sum(),
                "비용": subset["비용"].sum(),
                "구독 신청": subset["구독 신청"].sum(),
                "CTR_pct": weighted_ctr(subset["노출수"], subset["클릭수"]),
                "전환율_pct": conversion_rate(subset["클릭수"], subset["구독 신청"]),
                "CPA": cpa(subset["비용"], subset["구독 신청"]),
            }
        )
    return pd.DataFrame(rows)


def aggregate_by_week(df: pd.DataFrame) -> pd.DataFrame:
    """ISO 캘린더 주(월요일 시작) 단위 합계 및 가중평균 지표.

    df는 '날짜'(datetime), '노출수', '클릭수', '비용', '구독 신청' 컬럼이 필요하다.
    기간 맨 앞/뒤 주는 7일이 안 채워진 부분 주일 수 있어 "일수" 컬럼을 함께 반환한다.
    """
    if df.empty:
        return pd.DataFrame()

    iso = df["날짜"].dt.isocalendar()
    grouped = df.assign(_연도=iso["year"], _주차=iso["week"]).groupby(["_연도", "_주차"], sort=True)

    rows = []
    for (year, week), subset in grouped:
        rows.append(
            {
                "주차": f"{year}-W{week:02d}",
                "기간": f"{subset['날짜'].min():%m-%d} ~ {subset['날짜'].max():%m-%d}",
                "일수": len(subset),
                "노출수": subset["노출수"].sum(),
                "클릭수": subset["클릭수"].sum(),
                "비용": subset["비용"].sum(),
                "구독 신청": subset["구독 신청"].sum(),
                "CTR_pct": weighted_ctr(subset["노출수"], subset["클릭수"]),
                "전환율_pct": conversion_rate(subset["클릭수"], subset["구독 신청"]),
                "CPA": cpa(subset["비용"], subset["구독 신청"]),
            }
        )
    return pd.DataFrame(rows)
