"""data/raw/*.csv 로딩 및 정제.

CLAUDE.md의 "데이터 처리 시 주의사항" 참고:
- 모든 CSV는 UTF-8 BOM -> encoding="utf-8-sig"로 읽는다.
- CTR, 전환율 등은 "13.87%" 형태의 문자열이라 숫자로 변환해야 한다.
- campaign_daily.csv 마지막 행("합계")은 집계 행이므로 제외한다.
- device_hour.csv는 기기/시간대 두 차원이 한 파일에 섞여 있어 분리한다.
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _read_csv(filename: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / filename, encoding="utf-8-sig")


def _pct_to_float(series: pd.Series) -> pd.Series:
    """"13.87%" 같은 문자열 컬럼을 float(13.87)로 변환. 빈 값은 NaN 유지."""
    cleaned = series.astype(str).str.rstrip("%").str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def _to_numeric(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def load_campaign_daily() -> pd.DataFrame:
    df = _read_csv("campaign_daily.csv")
    # "합계" 같은 집계 행은 날짜 형식이 아니므로 파싱 실패(NaT)로 걸러낸다.
    # 리포트마다 집계 행 라벨이 달라질 수 있어 문자열 비교보다 안전하다.
    df["날짜"] = pd.to_datetime(df["날짜"], format="%Y-%m-%d", errors="coerce")
    df = df[df["날짜"].notna()].copy()
    df["CTR_pct"] = _pct_to_float(df["CTR"])
    df["전환율_pct"] = _pct_to_float(df["전환율"])
    _to_numeric(df, ["노출수", "클릭수", "평균 CPC", "비용", "구독 신청", "전환당비용"])
    df["학습기간_flag"] = df["학습 기간"].fillna("") == "Y"
    return df.sort_values("날짜").reset_index(drop=True)


def load_keywords() -> pd.DataFrame:
    df = _read_csv("keywords.csv")
    df["CTR_pct"] = _pct_to_float(df["CTR"])
    _to_numeric(df, ["품질평가점수", "노출수", "클릭수", "평균 CPC", "비용", "구독 신청"])
    df["CPA"] = df["비용"] / df["구독 신청"].replace(0, pd.NA)
    return df


def load_search_terms() -> pd.DataFrame:
    df = _read_csv("search_terms.csv")
    df["CTR_pct"] = _pct_to_float(df["CTR"])
    _to_numeric(df, ["노출수", "클릭수", "비용", "구독 신청", "전환당비용"])
    return df


def load_device_hour() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = _read_csv("device_hour.csv")
    df["CTR_pct"] = _pct_to_float(df["CTR"])
    _to_numeric(df, ["노출수", "클릭수", "비용", "구독 신청"])
    df["CPA"] = df["비용"] / df["구독 신청"].replace(0, pd.NA)
    device_df = df[df["구분"] == "기기"].reset_index(drop=True)
    hour_df = df[df["구분"] == "시간대"].reset_index(drop=True)
    return device_df, hour_df


def load_ad_groups() -> pd.DataFrame:
    df = _read_csv("ad_groups.csv")
    df["CTR_pct"] = _pct_to_float(df["CTR"])
    _to_numeric(df, ["키워드 수", "평균 품질평가점수", "노출수", "클릭수", "평균 CPC", "비용", "구독 신청"])
    df["CPA"] = df["비용"] / df["구독 신청"].replace(0, pd.NA)
    return df


def load_placements() -> pd.DataFrame:
    df = _read_csv("placements.csv")
    if df.empty:
        return df
    df["CTR_pct"] = _pct_to_float(df["CTR"])
    _to_numeric(df, ["노출수", "클릭수", "비용", "구독 신청"])
    return df
