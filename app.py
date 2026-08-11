from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from src import data_loader, metrics

st.set_page_config(page_title="홈핏 마케팅 대시보드", layout="wide")

# 광고그룹 2개를 모든 차트에서 동일한 색으로 고정 (색맹 안전성 검증된 조합).
GROUP_COLORS = {"홈트 클래스": "#2a78d6", "홈핏 브랜드": "#eb6834"}
TARGET_LINE_COLOR = "#d03b3b"
TARGET_HIGHLIGHT_BG = "rgba(208, 59, 59, 0.22)"

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


if "data_loaded_at" not in st.session_state:
    st.session_state["data_loaded_at"] = datetime.now()

with st.sidebar:
    if st.button("데이터 새로고침"):
        st.cache_data.clear()
        st.session_state["data_loaded_at"] = datetime.now()
        st.rerun()
    st.caption(f"마지막 새로고침: {st.session_state['data_loaded_at']:%Y-%m-%d %H:%M}")
    st.caption("data/raw/ 의 CSV를 새 리포트로 교체한 뒤 이 버튼을 누르면 즉시 반영됩니다.")

daily = get_campaign_daily()
keywords = get_keywords()
search_terms = get_search_terms()
device_df, hour_df = get_device_hour()
ad_groups = get_ad_groups()
placements = get_placements()

_overall_cpa = metrics.cpa(daily["비용"], daily["구독 신청"])
_default_target_cpa = int(_overall_cpa) if pd.notna(_overall_cpa) else 0

min_date, max_date = daily["날짜"].min(), daily["날짜"].max()

header_left, header_right = st.columns([3, 1])
with header_left:
    st.title("홈핏 마케팅 대시보드")
    st.caption("구글 광고 캠페인 성과 · 구독 신청 전환 분석")
with header_right:
    st.write("")
    date_range = st.date_input(
        "기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

show_learning = st.sidebar.checkbox("학습 기간(Y) 데이터 포함", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("목표 설정")
target_cpa = st.sidebar.number_input(
    "목표 CPA (원)",
    min_value=0,
    value=0,
    step=1000,
    help=(
        "이 값을 초과하는 CPA는 차트·표에서 빨간색으로 강조됩니다. 0이면 강조를 끕니다. "
        f"(참고: 전체 기간 평균 CPA ≈ ₩{_default_target_cpa:,})"
    ),
)
has_target = target_cpa > 0


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    out = df
    if not show_learning:
        out = out[~out["학습기간_flag"]]
    return out


def style_table(df: pd.DataFrame, cpa_col: str | None = None):
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
        styler = styler.background_gradient(subset=high_is_good, cmap="RdYlGn", axis=0)
    if low_is_good:
        styler = styler.background_gradient(subset=low_is_good, cmap="RdYlGn_r", axis=0)

    if cpa_col and cpa_col in tidy.columns:

        def _highlight(row):
            if has_target and pd.notna(row[cpa_col]) and row[cpa_col] > target_cpa:
                return [f"background-color: {TARGET_HIGHLIGHT_BG}"] * len(row)
            return [""] * len(row)

        styler = styler.apply(_highlight, axis=1)
    return styler


mask = (daily["날짜"] >= pd.Timestamp(start_date)) & (daily["날짜"] <= pd.Timestamp(end_date))
filtered = apply_filters(daily.loc[mask].copy())

if filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다. 기간 또는 필터를 조정해주세요.")
    st.stop()

# 선택한 기간과 동일한 길이의 직전 기간 (전기 대비 증감률 계산용)
period_len = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
prev_end = pd.Timestamp(start_date) - pd.Timedelta(days=1)
prev_start = prev_end - pd.Timedelta(days=period_len - 1)
prev_mask = (daily["날짜"] >= prev_start) & (daily["날짜"] <= prev_end)
prev_filtered = apply_filters(daily.loc[prev_mask].copy())
has_prev = prev_start >= min_date and not prev_filtered.empty

curr_impr, curr_clicks = filtered["노출수"].sum(), filtered["클릭수"].sum()
curr_cost, curr_conv = filtered["비용"].sum(), filtered["구독 신청"].sum()
curr_ctr = metrics.weighted_ctr(filtered["노출수"], filtered["클릭수"])
curr_convrate = metrics.conversion_rate(filtered["클릭수"], filtered["구독 신청"])
curr_cpa = metrics.cpa(filtered["비용"], filtered["구독 신청"])

if has_prev:
    prev_impr, prev_clicks = prev_filtered["노출수"].sum(), prev_filtered["클릭수"].sum()
    prev_cost, prev_conv = prev_filtered["비용"].sum(), prev_filtered["구독 신청"].sum()
    prev_ctr = metrics.weighted_ctr(prev_filtered["노출수"], prev_filtered["클릭수"])
    prev_convrate = metrics.conversion_rate(prev_filtered["클릭수"], prev_filtered["구독 신청"])
    prev_cpa = metrics.cpa(prev_filtered["비용"], prev_filtered["구독 신청"])
else:
    prev_impr = prev_clicks = prev_cost = prev_conv = prev_ctr = prev_convrate = prev_cpa = None

# 핵심 요약 배너 — 표·차트를 보기 전에 가장 중요한 신호부터 먼저 보여준다.
alerts: list[tuple[str, str]] = []
if has_target and pd.notna(curr_cpa) and curr_cpa > target_cpa:
    over_pct = (curr_cpa / target_cpa - 1) * 100
    alerts.append(("error", f"CPA ₩{curr_cpa:,.0f}이 목표 ₩{target_cpa:,.0f}보다 {over_pct:.0f}% 높습니다."))

conv_change = metrics.pct_change(curr_conv, prev_conv)
if conv_change is not None and conv_change <= -15:
    alerts.append(("error", f"구독 신청이 이전 기간 대비 {conv_change:.0f}% 감소했습니다."))

cpa_change = metrics.pct_change(curr_cpa, prev_cpa)
if cpa_change is not None and cpa_change >= 15:
    alerts.append(("warning", f"CPA가 이전 기간 대비 {cpa_change:+.0f}% 상승했습니다."))

if alerts:
    for level, msg in alerts:
        getattr(st, level)(msg)
else:
    st.success("주요 지표에 특별한 경고 신호가 없습니다.")

if has_prev:
    st.caption(f"vs 이전 기간 {prev_start:%Y-%m-%d} ~ {prev_end:%Y-%m-%d}")
else:
    st.caption("이전 기간이 리포트 데이터 범위를 벗어나 전기 대비 증감률은 표시하지 않습니다.")


def show_metric(col, label: str, value_str: str, current: float, previous: float | None, inverse: bool = False) -> None:
    change = metrics.pct_change(current, previous)
    delta_str = f"{change:+.1f}%" if change is not None else None
    col.metric(label, value_str, delta=delta_str, delta_color="inverse" if inverse else "normal")


with st.container(border=True):
    st.markdown("**트래픽**")
    c1, c2, c3 = st.columns(3)
    show_metric(c1, "노출수", f"{curr_impr:,.0f}", curr_impr, prev_impr)
    show_metric(c2, "클릭수", f"{curr_clicks:,.0f}", curr_clicks, prev_clicks)
    show_metric(c3, "평균 CTR", f"{curr_ctr:.2f}%", curr_ctr, prev_ctr)

with st.container(border=True):
    st.markdown("**비용 · 전환**")
    c1, c2, c3, c4 = st.columns(4)
    show_metric(c1, "비용", f"₩{curr_cost:,.0f}", curr_cost, prev_cost, inverse=True)
    show_metric(c2, "구독 신청", f"{curr_conv:,.0f}건", curr_conv, prev_conv)
    show_metric(c3, "전환율", f"{curr_convrate:.2f}%", curr_convrate, prev_convrate)
    show_metric(
        c4,
        "전환당비용(CPA)",
        f"₩{curr_cpa:,.0f}" if pd.notna(curr_cpa) else "N/A",
        curr_cpa,
        prev_cpa,
        inverse=True,
    )
    if has_target and pd.notna(curr_cpa):
        target_diff = (curr_cpa - target_cpa) / target_cpa * 100
        if curr_cpa > target_cpa:
            c4.markdown(f":red[목표 ₩{target_cpa:,.0f} 대비 {target_diff:+.1f}% 초과]")
        else:
            c4.markdown(f":green[목표 ₩{target_cpa:,.0f} 대비 {target_diff:+.1f}%]")

tab_daily, tab_keywords, tab_search, tab_device, tab_groups = st.tabs(
    ["일별 추이", "키워드", "검색어", "기기/시간대", "광고그룹"]
)

full_period_note = (
    f"※ 원본 리포트 전체 기간({min_date:%Y-%m-%d} ~ {max_date:%Y-%m-%d}) 기준입니다. "
    "이 CSV들은 일자별 데이터가 아니라 기간 집계본이라 사이드바의 기간 필터가 적용되지 않습니다."
)

with tab_daily:
    st.subheader("일별 성과 추이")
    metric_map = {
        "노출수": "노출수",
        "클릭수": "클릭수",
        "비용": "비용",
        "구독 신청": "구독 신청",
        "CTR (%)": "CTR_pct",
        "전환율 (%)": "전환율_pct",
        "CPA (전환당비용)": "전환당비용",
    }
    label = st.selectbox("지표 선택", list(metric_map.keys()))
    metric_col = metric_map[label]

    fig = px.line(filtered, x="날짜", y=metric_col, markers=True, color_discrete_sequence=[GROUP_COLORS["홈트 클래스"]])
    for learning_date in filtered.loc[filtered["학습기간_flag"], "날짜"]:
        fig.add_vrect(
            x0=learning_date,
            x1=learning_date + pd.Timedelta(days=1),
            fillcolor="orange",
            opacity=0.15,
            line_width=0,
        )
    if has_target and metric_col == "전환당비용":
        fig.add_hline(
            y=target_cpa, line_dash="dash", line_color=TARGET_LINE_COLOR, annotation_text=f"목표 CPA ₩{target_cpa:,.0f}"
        )
    st.plotly_chart(fig, width="stretch")
    st.caption("주황색 음영 = 학습 기간(Y) 구간" + ("· 빨간 점선 = 목표 CPA" if has_target else ""))

    with st.expander("일별 상세 데이터 보기"):
        display_df = filtered.drop(columns=["학습기간_flag"]).copy()
        display_df["날짜"] = display_df["날짜"].dt.strftime("%Y-%m-%d")
        st.dataframe(style_table(display_df, cpa_col="전환당비용"), width="stretch")

    st.divider()
    st.subheader("요일별 성과")
    weekday_df = metrics.aggregate_by_weekday(filtered)
    weekday_metric_map = {
        "CPA": "CPA",
        "구독 신청 합계": "구독 신청",
        "평균 CTR (%)": "CTR_pct",
        "평균 전환율 (%)": "전환율_pct",
        "비용 합계": "비용",
    }
    weekday_label = st.selectbox("요일별 지표", list(weekday_metric_map.keys()))
    weekday_col = weekday_metric_map[weekday_label]
    fig_weekday = px.bar(weekday_df, x="요일", y=weekday_col, color_discrete_sequence=[GROUP_COLORS["홈트 클래스"]])
    if has_target and weekday_col == "CPA":
        fig_weekday.add_hline(y=target_cpa, line_dash="dash", line_color=TARGET_LINE_COLOR, annotation_text="목표 CPA")
    st.plotly_chart(fig_weekday, width="stretch")
    st.caption("현재 선택된 기간·필터 기준 요일별 합계(CPA·CTR·전환율은 가중평균)이며, 요일별 표본 일수가 적으면 편차가 클 수 있습니다.")
    st.dataframe(style_table(weekday_df, cpa_col="CPA"), width="stretch")

with tab_keywords:
    st.subheader("키워드별 성과")
    st.caption(full_period_note)

    fig_kw = px.bar(
        keywords.sort_values("비용", ascending=False),
        x="키워드",
        y="비용",
        color="광고그룹",
        color_discrete_map=GROUP_COLORS,
    )
    st.plotly_chart(fig_kw, width="stretch")

    st.subheader("품질평가점수 vs 전환당비용(CPA)")
    fig_qs = px.scatter(
        keywords,
        x="품질평가점수",
        y="CPA",
        size="비용",
        color="광고그룹",
        color_discrete_map=GROUP_COLORS,
        hover_name="키워드",
    )
    if has_target:
        fig_qs.add_hline(y=target_cpa, line_dash="dash", line_color=TARGET_LINE_COLOR, annotation_text="목표 CPA")
    st.plotly_chart(fig_qs, width="stretch")
    st.caption("점 크기 = 비용. 품질평가점수는 낮고 CPA는 높은 키워드가 개선 우선순위입니다.")

    st.divider()
    sort_map = {"비용": "비용", "구독 신청": "구독 신청", "CTR (%)": "CTR_pct", "CPA": "CPA"}
    sort_label = st.selectbox("정렬 기준", list(sort_map.keys()))
    ascending = st.checkbox("오름차순 정렬", value=False)
    st.dataframe(
        style_table(
            keywords.sort_values(sort_map[sort_label], ascending=ascending, na_position="last"),
            cpa_col="CPA",
        ),
        width="stretch",
    )
    if has_target:
        st.caption(f"빨간색 행 = CPA가 목표(₩{target_cpa:,.0f})를 초과한 키워드")

with tab_search:
    st.subheader("실검색어 리포트")
    st.caption(full_period_note)
    st.caption("실제 사용자가 입력한 검색어와 매칭된 키워드를 비교해 신규/제외 키워드 후보를 찾습니다.")

    existing_keywords = set(keywords["키워드"])
    analyzed = search_terms.copy()
    analyzed["신규_키워드_후보"] = ~analyzed["검색어"].isin(existing_keywords)
    analyzed["제외_키워드_후보"] = (analyzed["클릭수"] > 0) & (analyzed["구독 신청"] == 0)

    new_candidates = analyzed[analyzed["신규_키워드_후보"]].sort_values("클릭수", ascending=False)
    exclude_candidates = analyzed[analyzed["제외_키워드_후보"]].sort_values("비용", ascending=False)

    col_a, col_b = st.columns(2)
    col_a.metric("신규 키워드 후보", f"{len(new_candidates)}건")
    col_b.metric("제외 키워드 후보 (클릭 O, 전환 0)", f"{len(exclude_candidates)}건")

    st.markdown("**신규 키워드 후보** — 아직 키워드로 등록되지 않았지만 실제로 유입된 검색어")
    if new_candidates.empty:
        st.caption("해당 없음")
    else:
        st.dataframe(
            style_table(new_candidates[["검색어", "일치 키워드", "광고그룹", "노출수", "클릭수", "CTR_pct", "비용", "구독 신청"]]),
            width="stretch",
        )

    st.markdown("**제외 키워드 후보** — 클릭·비용은 발생했지만 전환이 0건 (네거티브 키워드 검토 대상)")
    if exclude_candidates.empty:
        st.caption("해당 없음")
    else:
        st.dataframe(
            style_table(exclude_candidates[["검색어", "일치 키워드", "광고그룹", "클릭수", "비용"]]),
            width="stretch",
        )

    with st.expander("전체 검색어 보기"):
        st.dataframe(
            style_table(analyzed.sort_values("클릭수", ascending=False).drop(columns=["신규_키워드_후보", "제외_키워드_후보"])),
            width="stretch",
        )

with tab_device:
    st.caption(full_period_note)
    metric_options = {
        "노출수": "노출수",
        "클릭수": "클릭수",
        "비용": "비용",
        "구독 신청": "구독 신청",
        "CTR (%)": "CTR_pct",
        "CPA": "CPA",
    }

    col_device, col_hour = st.columns([1, 2])

    with col_device:
        st.subheader("기기별 성과")
        device_label = st.selectbox("지표", list(metric_options.keys()), key="device_metric")
        fig_device = px.bar(
            device_df, x="값", y=metric_options[device_label], color_discrete_sequence=[GROUP_COLORS["홈트 클래스"]]
        )
        st.plotly_chart(fig_device, width="stretch")

    with col_hour:
        st.subheader("시간대별 성과")
        hour_label = st.selectbox("지표 ", list(metric_options.keys()), key="hour_metric")
        fig_hour = px.bar(
            hour_df, x="값", y=metric_options[hour_label], color_discrete_sequence=[GROUP_COLORS["홈트 클래스"]]
        )
        st.plotly_chart(fig_hour, width="stretch")

    st.caption("CPA가 비어 있는 막대는 해당 구간의 전환이 0건이라는 의미입니다.")
    st.caption("기기/시간대별 구독 신청 값은 기여(attribution) 모델에 따라 분배되어 소수일 수 있습니다.")

with tab_groups:
    st.subheader("광고그룹 요약")
    st.caption(full_period_note)

    fig_groups = px.bar(
        ad_groups.sort_values("CPA"), x="광고그룹", y="CPA", color="광고그룹", color_discrete_map=GROUP_COLORS
    )
    if has_target:
        fig_groups.add_hline(y=target_cpa, line_dash="dash", line_color=TARGET_LINE_COLOR, annotation_text="목표 CPA")
    st.plotly_chart(fig_groups, width="stretch")

    st.dataframe(style_table(ad_groups, cpa_col="CPA"), width="stretch")

    st.divider()
    st.subheader("게재위치")
    if placements.empty:
        st.info("게재위치(placements) 데이터가 아직 없습니다.")
    else:
        st.dataframe(style_table(placements), width="stretch")
