import pandas as pd
import plotly.express as px
import streamlit as st

from src import dashboard_common as dc
from src import metrics

show_learning, target_cpa, has_target = dc.render_sidebar()
start_date, end_date = dc.render_date_header("전환율 — 구독 신청으로 이어지는 전환 성과")

ctx = dc.PeriodContext(start_date, end_date, show_learning)
if ctx.filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다. 기간 또는 필터를 조정해주세요.")
    st.stop()

# 핵심 요약 배너 — 표·차트를 보기 전에 가장 중요한 신호부터 먼저 보여준다.
alerts: list[tuple[str, str]] = []
if has_target and pd.notna(ctx.cpa) and ctx.cpa > target_cpa:
    over_pct = (ctx.cpa / target_cpa - 1) * 100
    alerts.append(("error", f"CPA ₩{ctx.cpa:,.0f}이 목표 ₩{target_cpa:,.0f}보다 {over_pct:.0f}% 높습니다."))

conv_change = metrics.pct_change(ctx.conv, ctx.prev_conv)
if conv_change is not None and conv_change <= -15:
    alerts.append(("error", f"구독 신청이 이전 기간 대비 {conv_change:.0f}% 감소했습니다."))

cpa_change = metrics.pct_change(ctx.cpa, ctx.prev_cpa)
if cpa_change is not None and cpa_change >= 15:
    alerts.append(("warning", f"CPA가 이전 기간 대비 {cpa_change:+.0f}% 상승했습니다."))

if alerts:
    for level, msg in alerts:
        getattr(st, level)(msg)
else:
    st.success("주요 지표에 특별한 경고 신호가 없습니다.")

if ctx.has_prev:
    st.caption(f"vs 이전 기간 {ctx.prev_start:%Y-%m-%d} ~ {ctx.prev_end:%Y-%m-%d}")
else:
    st.caption("이전 기간이 리포트 데이터 범위를 벗어나 전기 대비 증감률은 표시하지 않습니다.")

# 핵심 지표: 전환율 하나만 크게 강조
conv_delta = metrics.pct_change(ctx.convrate, ctx.prev_convrate)
if conv_delta is not None:
    hero_color = dc.STATUS_GOOD_COLOR if conv_delta >= 0 else dc.STATUS_BAD_COLOR
    hero_arrow = "▲" if conv_delta >= 0 else "▼"
    hero_delta_html = (
        f"<div style='font-size:18px; font-weight:600; color:{hero_color};'>"
        f"{hero_arrow} {conv_delta:+.1f}% · 이전 기간 대비</div>"
    )
else:
    hero_delta_html = f"<div style='font-size:14px; color:{dc.MUTED_TEXT_COLOR};'>이전 기간 비교 불가</div>"

with st.container(border=True):
    st.markdown(
        f"""
        <div style="text-align:center; padding:6px 0 10px 0;">
          <div style="font-size:15px; color:{dc.MUTED_TEXT_COLOR}; letter-spacing:0.02em;">핵심 지표 · 전환율</div>
          <div style="font-size:68px; font-weight:800; line-height:1.15; margin:2px 0;">{ctx.convrate:.2f}%</div>
          {hero_delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.subheader("지표 추이")
# KPI 영역과 같은 순서: 전환율(히어로) → 트래픽 퍼널 → 비용 효율. 탭은 항상 첫 번째가
# 기본으로 열리므로 전환율을 맨 앞에 둬서 기본 노출 지표로 삼는다. 이 페이지는 7개 지표를
# 한 번에 훑어보는 개요이고, 노출·클릭 성과/최종 측면 페이지는 각자 맥락 안에서 관련
# 지표(노출·CTR·클릭 / 비용·구독신청·CPA) 추이를 별도로 반복해서 보여준다.
trend_metrics = [
    ("전환율", "전환율_pct"),
    ("노출수", "노출수"),
    ("CTR", "CTR_pct"),
    ("클릭수", "클릭수"),
    ("구독 신청", "구독 신청"),
    ("비용", "비용"),
    ("CPA (전환당비용)", "전환당비용"),
]
trend_tabs = st.tabs([label for label, _ in trend_metrics])
for trend_tab, (label, metric_col) in zip(trend_tabs, trend_metrics):
    with trend_tab:
        fig = px.line(
            ctx.filtered, x="날짜", y=metric_col, markers=True, color_discrete_sequence=[dc.GROUP_COLORS["홈트 클래스"]]
        )
        for learning_date in ctx.filtered.loc[ctx.filtered["학습기간_flag"], "날짜"]:
            fig.add_vrect(
                x0=learning_date, x1=learning_date + pd.Timedelta(days=1), fillcolor="orange", opacity=0.15, line_width=0
            )
        is_cpa_tab = metric_col == "전환당비용"
        if has_target and is_cpa_tab:
            fig.add_hline(
                y=target_cpa,
                line_dash="dash",
                line_color=dc.TARGET_LINE_COLOR,
                annotation_text=f"목표 CPA ₩{target_cpa:,.0f}",
            )
        st.plotly_chart(fig, width="stretch", key=f"trend1_{metric_col}")
        st.caption("주황색 음영 = 학습 기간(Y) 구간" + ("· 빨간 점선 = 목표 CPA" if has_target and is_cpa_tab else ""))

st.subheader("주별 추이")
week_df = metrics.aggregate_by_week(ctx.filtered)
st.dataframe(dc.style_table(week_df, target_cpa, has_target, cpa_col="CPA"), width="stretch")
st.caption("ISO 캘린더 주(월요일 시작) 기준 합계·가중평균이며, 맨 앞/뒤 주는 일수가 7일보다 적은 부분 주일 수 있습니다.")

st.divider()
st.subheader("요일별 성과")
weekday_df = metrics.aggregate_by_weekday(ctx.filtered)
weekday_metric_map = {
    "평균 전환율 (%)": "전환율_pct",
    "CPA": "CPA",
    "구독 신청 합계": "구독 신청",
    "평균 CTR (%)": "CTR_pct",
    "비용 합계": "비용",
}
weekday_label = st.selectbox("요일별 지표", list(weekday_metric_map.keys()))
weekday_col = weekday_metric_map[weekday_label]
fig_weekday = px.bar(weekday_df, x="요일", y=weekday_col, color_discrete_sequence=[dc.GROUP_COLORS["홈트 클래스"]])
if has_target and weekday_col == "CPA":
    fig_weekday.add_hline(y=target_cpa, line_dash="dash", line_color=dc.TARGET_LINE_COLOR, annotation_text="목표 CPA")
st.plotly_chart(fig_weekday, width="stretch")
st.caption("현재 선택된 기간·필터 기준 요일별 합계(CPA·CTR·전환율은 가중평균)이며, 요일별 표본 일수가 적으면 편차가 클 수 있습니다.")
st.dataframe(dc.style_table(weekday_df, target_cpa, has_target, cpa_col="CPA"), width="stretch")

with st.expander("일별 상세 데이터 보기"):
    display_df = ctx.filtered.drop(columns=["학습기간_flag"]).copy()
    display_df["날짜"] = display_df["날짜"].dt.strftime("%Y-%m-%d")
    st.dataframe(dc.style_table(display_df, target_cpa, has_target, cpa_col="전환당비용"), width="stretch")
