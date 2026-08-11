import streamlit as st

st.set_page_config(page_title="홈핏 마케팅 대시보드", layout="wide", initial_sidebar_state="expanded")

pg = st.navigation(
    [
        st.Page("pages/1_전환율.py", title="전환율", default=True),
        st.Page("pages/2_노출_클릭_성과.py", title="노출·클릭 성과"),
        st.Page("pages/3_최종_측면.py", title="최종 측면"),
    ]
)
pg.run()
