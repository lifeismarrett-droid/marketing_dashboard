import pandas as pd
import plotly.express as px
import streamlit as st

from src import dashboard_common as dc

show_learning, target_cpa, has_target = dc.render_sidebar()
start_date, end_date = dc.render_date_header("노출·클릭 성과 — 트래픽이 만들어지고 소진되는 과정")

ctx = dc.PeriodContext(start_date, end_date, show_learning)
if ctx.filtered.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다. 기간 또는 필터를 조정해주세요.")
    st.stop()

if ctx.has_prev:
    st.caption(f"vs 이전 기간 {ctx.prev_start:%Y-%m-%d} ~ {ctx.prev_end:%Y-%m-%d}")
else:
    st.caption("이전 기간이 리포트 데이터 범위를 벗어나 전기 대비 증감률은 표시하지 않습니다.")

with st.container(border=True):
    st.markdown("**트래픽 퍼널** — 노출부터 클릭까지 이어지는 흐름")
    f1, a1, f2, a2, f3 = st.columns([3, 0.5, 3, 0.5, 3])
    dc.show_metric(f1, "노출수", f"{ctx.impr:,.0f}", ctx.impr, ctx.prev_impr)
    dc.show_arrow(a1)
    dc.show_metric(f2, "CTR", f"{ctx.ctr:.2f}%", ctx.ctr, ctx.prev_ctr)
    dc.show_arrow(a2)
    dc.show_metric(f3, "클릭수", f"{ctx.clicks:,.0f}", ctx.clicks, ctx.prev_clicks)

st.subheader("지표 추이")
trend_metrics = [("노출수", "노출수"), ("CTR", "CTR_pct"), ("클릭수", "클릭수")]
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
        st.plotly_chart(fig, width="stretch", key=f"trend2_{metric_col}")
        st.caption("주황색 음영 = 학습 기간(Y) 구간")

st.divider()
full_note = dc.full_period_note()

st.subheader("기기·시간대별 트래픽")
st.caption(full_note)
device_df, hour_df = dc.get_device_hour()
metric_options = {"노출수": "노출수", "클릭수": "클릭수", "CTR (%)": "CTR_pct"}

col_device, col_hour = st.columns([1, 2])
with col_device:
    device_label = st.selectbox("지표", list(metric_options.keys()), key="device_metric")
    fig_device = px.bar(
        device_df, x="값", y=metric_options[device_label], color_discrete_sequence=[dc.GROUP_COLORS["홈트 클래스"]]
    )
    st.plotly_chart(fig_device, width="stretch")
with col_hour:
    hour_label = st.selectbox("지표 ", list(metric_options.keys()), key="hour_metric")
    fig_hour = px.bar(
        hour_df, x="값", y=metric_options[hour_label], color_discrete_sequence=[dc.GROUP_COLORS["홈트 클래스"]]
    )
    st.plotly_chart(fig_hour, width="stretch")
st.caption("기기/시간대별 값은 기여(attribution) 모델에 따라 분배되어 소수일 수 있습니다.")

st.divider()
st.subheader("실검색어 리포트")
st.caption(full_note)
st.caption("실제 사용자가 입력한 검색어와 매칭된 키워드를 비교해 신규/제외 키워드 후보를 찾습니다.")

keywords = dc.get_keywords()
search_terms = dc.get_search_terms()
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
        dc.style_table(
            new_candidates[["검색어", "일치 키워드", "광고그룹", "노출수", "클릭수", "CTR_pct", "비용", "구독 신청"]],
            target_cpa,
            has_target,
        ),
        width="stretch",
    )

st.markdown("**제외 키워드 후보** — 클릭·비용은 발생했지만 전환이 0건 (네거티브 키워드 검토 대상)")
if exclude_candidates.empty:
    st.caption("해당 없음")
else:
    st.dataframe(
        dc.style_table(exclude_candidates[["검색어", "일치 키워드", "광고그룹", "클릭수", "비용"]], target_cpa, has_target),
        width="stretch",
    )

with st.expander("전체 검색어 보기"):
    st.dataframe(
        dc.style_table(
            analyzed.sort_values("클릭수", ascending=False).drop(columns=["신규_키워드_후보", "제외_키워드_후보"]),
            target_cpa,
            has_target,
        ),
        width="stretch",
    )
