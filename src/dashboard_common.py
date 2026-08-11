"""3개 페이지(전환율 / 노출·클릭 성과 / 최종 측면)가 공유하는 상수·데이터·렌더링 헬퍼.

각 페이지 파일은 맨 위에서 render_sidebar() → render_date_header() → PeriodContext(...)
순서로 호출해 동일한 필터 상태(날짜 범위·학습기간·목표 CPA)를 공유한다. 사이드바 위젯에
명시적 key를 부여해뒀기 때문에 st.session_state를 통해 페이지를 이동해도 값이 유지된다.
"""

from datetime import datetime

import pandas as pd
import streamlit as st
from matplotlib.colors import LinearSegmentedColormap

from src import data_loader, metrics

# 광고그룹 2개를 모든 차트에서 동일한 색으로 고정 (색맹 안전성 검증된 조합).
GROUP_COLORS = {"홈트 클래스": "#2a78d6", "홈핏 브랜드": "#eb6834"}
TARGET_LINE_COLOR = "#d03b3b"
TARGET_HIGHLIGHT_BG = "rgba(226, 104, 92, 0.35)"
STATUS_GOOD_COLOR = "#0ca30c"
STATUS_BAD_COLOR = TARGET_LINE_COLOR
MUTED_TEXT_COLOR = "#898781"

# 표 히트맵 색상. matplotlib 기본 컬러맵(RdYlGn)은 채도가 너무 높아 표 전체를 덮으면
# 눈이 피로해지고, 반대로 지나치게 낮추면 칙칙해 보인다 — 그 중간 지점(선명하지만
# 쨍하지 않은 코랄 ↔ 따뜻한 연회색 ↔ 선명한 그린)을 직접 만든다.
_HEATMAP_GOOD_HIGH_CMAP = LinearSegmentedColormap.from_list(
    "balanced_good_high", ["#e2685c", "#f0ede4", "#5cb85c"]
)
_HEATMAP_GOOD_LOW_CMAP = _HEATMAP_GOOD_HIGH_CMAP.reversed()

# 세그먼트(키워드·기기·시간대 등)를 비교할 때, 전환수가 이 값 미만이면 "표본이 작다"고
# 판단한다. 업계 통상 관례(비율 비교에 최소 10건 안팎)를 따른 임의 기준이며 정답은 아니다.
SMALL_SAMPLE_THRESHOLD = 10


def small_sample_warning(conversions: float, subject: str) -> str | None:
    """전환수가 SMALL_SAMPLE_THRESHOLD 미만이면 표본 크기 주의 문구, 아니면 None."""
    if pd.isna(conversions) or conversions >= SMALL_SAMPLE_THRESHOLD:
        return None
    return (
        f"{subject}의 전환은 {conversions:,.0f}건으로 표본이 작습니다. "
        "이 정도 건수로는 다른 구간과의 우열 비교가 통계적으로 큰 의미를 갖기 어려우니 참고용으로만 보세요."
    )

# 표에서 항상 비어 있거나(예산 소진, 고객 아님) 값이 하나뿐이라(광고 관련성 등)
# "한눈에 파악"에 도움이 안 되는 컬럼, 그리고 _pct 컬럼과 중복되는 원본 % 문자열 컬럼.
DROP_COLS = ["CTR", "전환율", "예산 소진", "고객 아님", "광고 관련성", "예상 CTR", "방문 페이지"]
RENAME_COLS = {"CTR_pct": "CTR(%)", "전환율_pct": "전환율(%)"}
NUMBER_FORMATS = {
    "노출수": "{:,.0f}",
    "클릭수": "{:,.0f}",
    "키워드 수": "{:,.0f}",
    "구독 신청": "{:,.0f}",
    "비용": "₩{:,.0f}",
    "평균 CPC": "₩{:,.0f}",
    "전환당비용": "₩{:,.0f}",
    "CPA": "₩{:,.0f}",
    "품질평가점수": "{:.1f}",
    "평균 품질평가점수": "{:.1f}",
    "CTR(%)": "{:.2f}%",
    "전환율(%)": "{:.2f}%",
}
# 히트맵 색상 방향: 높을수록 좋은 지표 vs 낮을수록 좋은 지표(비용성 지표)를 구분한다.
HEATMAP_HIGH_IS_GOOD = ["CTR(%)", "전환율(%)", "구독 신청", "품질평가점수", "평균 품질평가점수"]
HEATMAP_LOW_IS_GOOD = ["CPA", "비용", "평균 CPC", "전환당비용"]


@st.cache_data
def get_campaign_daily() -> pd.DataFrame:
    return data_loader.load_campaign_daily()


@st.cache_data
def get_keywords() -> pd.DataFrame:
    return data_loader.load_keywords()


@st.cache_data
def get_search_terms() -> pd.DataFrame:
    return data_loader.load_search_terms()


@st.cache_data
def get_device_hour() -> tuple[pd.DataFrame, pd.DataFrame]:
    return data_loader.load_device_hour()


@st.cache_data
def get_ad_groups() -> pd.DataFrame:
    return data_loader.load_ad_groups()


@st.cache_data
def get_placements() -> pd.DataFrame:
    return data_loader.load_placements()


def full_period_note() -> str:
    daily = get_campaign_daily()
    min_date, max_date = daily["날짜"].min(), daily["날짜"].max()
    return (
        f"※ 원본 리포트 전체 기간({min_date:%Y-%m-%d} ~ {max_date:%Y-%m-%d}) 기준입니다. "
        "이 CSV들은 일자별 데이터가 아니라 기간 집계본이라 사이드바의 기간 필터가 적용되지 않습니다."
    )


def render_sidebar() -> tuple[bool, int, bool]:
    """새로고침 / 학습기간 / 목표 CPA 사이드바 위젯. 모든 페이지 맨 위에서 호출한다.

    반환값: (show_learning, target_cpa, has_target)
    """
    if "data_loaded_at" not in st.session_state:
        st.session_state["data_loaded_at"] = datetime.now()

    with st.sidebar:
        if st.button("데이터 새로고침"):
            st.cache_data.clear()
            st.session_state["data_loaded_at"] = datetime.now()
            st.rerun()
        st.caption(f"마지막 새로고침: {st.session_state['data_loaded_at']:%Y-%m-%d %H:%M}")
        st.caption("data/raw/ 의 CSV를 새 리포트로 교체한 뒤 이 버튼을 누르면 즉시 반영됩니다.")

        show_learning = st.checkbox("학습 기간(Y) 데이터 포함", value=True, key="show_learning")

        st.markdown("---")
        st.subheader("목표 설정")
        daily = get_campaign_daily()
        overall_cpa = metrics.cpa(daily["비용"], daily["구독 신청"])
        default_target = int(overall_cpa) if pd.notna(overall_cpa) else 0
        target_cpa = st.number_input(
            "목표 CPA (원)",
            min_value=0,
            value=0,
            step=1000,
            key="target_cpa",
            help=(
                "이 값을 초과하는 CPA는 차트·표에서 빨간색으로 강조됩니다. 0이면 강조를 끕니다. "
                f"(참고: 전체 기간 평균 CPA ≈ ₩{default_target:,})"
            ),
        )

        st.markdown("---")
        st.caption(
            "**필터 적용 범위**\n\n"
            "· 기간·학습기간 → 일별/주별/요일별 추이에만 적용\n\n"
            "· 키워드·검색어·기기/시간대·광고그룹 표는 항상 전체 기간 기준\n\n"
            "원본 리포트에 날짜별 세부 데이터가 없어 두 종류의 표가 서로 다른 범위를 갖습니다."
        )
    return show_learning, target_cpa, target_cpa > 0


def render_date_header(subtitle: str) -> tuple:
    """제목 + 우측 상단 기간 선택기. 반환값: (start_date, end_date)."""
    daily = get_campaign_daily()
    min_date, max_date = daily["날짜"].min(), daily["날짜"].max()

    header_left, header_right = st.columns([3, 1])
    with header_left:
        st.title("홈핏 마케팅 대시보드")
        st.caption(subtitle)
    with header_right:
        st.write("")
        date_range = st.date_input(
            "기간",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="date_range_filter",
        )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date
    return start_date, end_date


class PeriodContext:
    """선택 기간과 직전 동일 길이 기간의 필터링된 데이터·집계 지표를 한 번에 계산."""

    def __init__(self, start_date, end_date, show_learning: bool):
        daily = get_campaign_daily()
        min_date = daily["날짜"].min()

        def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
            return df[~df["학습기간_flag"]] if not show_learning else df

        mask = (daily["날짜"] >= pd.Timestamp(start_date)) & (daily["날짜"] <= pd.Timestamp(end_date))
        self.filtered = apply_filters(daily.loc[mask].copy())

        period_len = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
        self.prev_end = pd.Timestamp(start_date) - pd.Timedelta(days=1)
        self.prev_start = self.prev_end - pd.Timedelta(days=period_len - 1)
        prev_mask = (daily["날짜"] >= self.prev_start) & (daily["날짜"] <= self.prev_end)
        prev_filtered = apply_filters(daily.loc[prev_mask].copy())
        self.has_prev = self.prev_start >= min_date and not prev_filtered.empty

        if self.filtered.empty:
            return

        f = self.filtered
        self.impr, self.clicks = f["노출수"].sum(), f["클릭수"].sum()
        self.cost, self.conv = f["비용"].sum(), f["구독 신청"].sum()
        self.ctr = metrics.weighted_ctr(f["노출수"], f["클릭수"])
        self.convrate = metrics.conversion_rate(f["클릭수"], f["구독 신청"])
        self.cpa = metrics.cpa(f["비용"], f["구독 신청"])

        if self.has_prev:
            pf = prev_filtered
            self.prev_impr, self.prev_clicks = pf["노출수"].sum(), pf["클릭수"].sum()
            self.prev_cost, self.prev_conv = pf["비용"].sum(), pf["구독 신청"].sum()
            self.prev_ctr = metrics.weighted_ctr(pf["노출수"], pf["클릭수"])
            self.prev_convrate = metrics.conversion_rate(pf["클릭수"], pf["구독 신청"])
            self.prev_cpa = metrics.cpa(pf["비용"], pf["구독 신청"])
        else:
            self.prev_impr = self.prev_clicks = self.prev_cost = None
            self.prev_conv = self.prev_ctr = self.prev_convrate = self.prev_cpa = None


def show_metric(col, label: str, value_str: str, current: float, previous: float | None, inverse: bool = False) -> None:
    change = metrics.pct_change(current, previous)
    delta_str = f"{change:+.1f}%" if change is not None else None
    col.metric(label, value_str, delta=delta_str, delta_color="inverse" if inverse else "normal")


def show_arrow(col) -> None:
    col.markdown(
        f"<div style='text-align:center; font-size:22px; padding-top:20px; color:{MUTED_TEXT_COLOR};'>→</div>",
        unsafe_allow_html=True,
    )


def style_table(df: pd.DataFrame, target_cpa: int = 0, has_target: bool = False, cpa_col: str | None = None):
    """중복/공백 컬럼 제거 + 숫자 포맷 통일 + 히트맵 색상 + (선택) 목표 CPA 초과 행 강조.

    히트맵은 컬럼별로 독립 정규화(axis=0)한다 — 비용(수십만 원)과 CTR(%, 0~100)처럼
    스케일이 다른 컬럼을 한 기준으로 섞으면 왜곡되기 때문.
    """
    tidy = df.drop(columns=[c for c in DROP_COLS if c in df.columns]).rename(columns=RENAME_COLS)
    fmt = {col: pattern for col, pattern in NUMBER_FORMATS.items() if col in tidy.columns}
    styler = tidy.style.format(fmt, na_rep="-")

    high_is_good = [c for c in HEATMAP_HIGH_IS_GOOD if c in tidy.columns]
    low_is_good = [c for c in HEATMAP_LOW_IS_GOOD if c in tidy.columns]
    if high_is_good:
        styler = styler.background_gradient(subset=high_is_good, cmap=_HEATMAP_GOOD_HIGH_CMAP, axis=0)
    if low_is_good:
        styler = styler.background_gradient(subset=low_is_good, cmap=_HEATMAP_GOOD_LOW_CMAP, axis=0)

    if cpa_col and cpa_col in tidy.columns:

        def _highlight(row):
            if has_target and pd.notna(row[cpa_col]) and row[cpa_col] > target_cpa:
                return [f"background-color: {TARGET_HIGHLIGHT_BG}"] * len(row)
            return [""] * len(row)

        styler = styler.apply(_highlight, axis=1)
    return styler
