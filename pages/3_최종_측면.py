import pandas as pd
import plotly.express as px
import streamlit as st

from src import dashboard_common as dc
from src import metrics

show_learning, target_cpa, has_target = dc.render_sidebar()
start_date, end_date = dc.render_date_header("최종 측면 — 비용이 만들어낸 구독 신청과 그 단가")

ctx = dc.PeriodContext(start_date, end_date, show_learning)
if ctx.filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다. 기간 또는 필터를 조정해주세요.")
    st.stop()

alerts: list[tuple[str, str]] = []
if has_target and pd.notna(ctx.cpa) and ctx.cpa > target_cpa:
    over_pct = (ctx.cpa / target_cpa - 1) * 100
    alerts.append(("error", f"CPA ₩{ctx.cpa:,.0f}이 목표 ₩{target_cpa:,.0f}보다 {over_pct:.0f}% 높습니다."))

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

with st.container(border=True):
    st.markdown("**비용 효율** — 비용이 구독 신청 1건당 단가로 이어지는 흐름")
    g1, a1, g2, a2, g3 = st.columns([3, 0.5, 3, 0.5, 3])
    dc.show_metric(g1, "비용", f"₩{ctx.cost:,.0f}", ctx.cost, ctx.prev_cost, inverse=True)
    dc.show_arrow(a1)
    dc.show_metric(g2, "구독 신청", f"{ctx.conv:,.0f}건", ctx.conv, ctx.prev_conv)
    dc.show_arrow(a2)
    dc.show_metric(
        g3,
        "전환당비용(CPA)",
        f"₩{ctx.cpa:,.0f}" if pd.notna(ctx.cpa) else "N/A",
        ctx.cpa,
        ctx.prev_cpa,
        inverse=True,
    )
    if has_target and pd.notna(ctx.cpa):
        target_diff = (ctx.cpa - target_cpa) / target_cpa * 100
        if ctx.cpa > target_cpa:
            g3.markdown(f":red[목표 ₩{target_cpa:,.0f} 대비 {target_diff:+.1f}% 초과]")
        else:
            g3.markdown(f":green[목표 ₩{target_cpa:,.0f} 대비 {target_diff:+.1f}%]")

st.subheader("지표 추이")
trend_metrics = [("비용", "비용"), ("구독 신청", "구독 신청"), ("CPA (전환당비용)", "전환당비용")]
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
        st.plotly_chart(fig, width="stretch", key=f"trend3_{metric_col}")
        st.caption("주황색 음영 = 학습 기간(Y) 구간" + ("· 빨간 점선 = 목표 CPA" if has_target and is_cpa_tab else ""))

st.divider()
full_note = dc.full_period_note()

st.subheader("키워드별 성과")
st.caption(full_note)
keywords = dc.get_keywords()

fig_kw = px.bar(
    keywords.sort_values("비용", ascending=False), x="키워드", y="비용", color="광고그룹", color_discrete_map=dc.GROUP_COLORS
)
st.plotly_chart(fig_kw, width="stretch")

st.markdown("**품질평가점수 vs 전환당비용(CPA)**")
fig_qs = px.scatter(
    keywords,
    x="품질평가점수",
    y="CPA",
    size="비용",
    color="광고그룹",
    color_discrete_map=dc.GROUP_COLORS,
    hover_name="키워드",
)
if has_target:
    fig_qs.add_hline(y=target_cpa, line_dash="dash", line_color=dc.TARGET_LINE_COLOR, annotation_text="목표 CPA")
st.plotly_chart(fig_qs, width="stretch")
st.caption("점 크기 = 비용. 품질평가점수는 낮고 CPA는 높은 키워드가 개선 우선순위입니다.")

sort_map = {"비용": "비용", "구독 신청": "구독 신청", "CTR (%)": "CTR_pct", "CPA": "CPA"}
sort_label = st.selectbox("정렬 기준", list(sort_map.keys()))
ascending = st.checkbox("오름차순 정렬", value=False)
st.dataframe(
    dc.style_table(
        keywords.sort_values(sort_map[sort_label], ascending=ascending, na_position="last"),
        target_cpa,
        has_target,
        cpa_col="CPA",
    ),
    width="stretch",
)
if has_target:
    st.caption(f"빨간색 행 = CPA가 목표(₩{target_cpa:,.0f})를 초과한 키워드")

st.divider()
st.subheader("광고그룹 요약")
st.caption(full_note)
ad_groups = dc.get_ad_groups()
placements = dc.get_placements()

fig_groups = px.bar(
    ad_groups.sort_values("CPA"), x="광고그룹", y="CPA", color="광고그룹", color_discrete_map=dc.GROUP_COLORS
)
if has_target:
    fig_groups.add_hline(y=target_cpa, line_dash="dash", line_color=dc.TARGET_LINE_COLOR, annotation_text="목표 CPA")
st.plotly_chart(fig_groups, width="stretch")
st.dataframe(dc.style_table(ad_groups, target_cpa, has_target, cpa_col="CPA"), width="stretch")

st.subheader("게재위치")
if placements.empty:
    st.info("게재위치(placements) 데이터가 아직 없습니다.")
else:
    st.dataframe(dc.style_table(placements, target_cpa, has_target), width="stretch")
