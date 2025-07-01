# .streamlit/config.toml
primaryColor = "#0072C3"
backgroundColor = "#F7FAFC"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#333333"
font = "sans serif"

# app.py
import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import folium_static
from folium.plugins import FastMarkerCluster

# 페이지 설정
st.set_page_config(page_title="환자 대시보드", layout="wide")

# 1) 데이터 로드
@st.cache_data
def load_data():
    return pd.read_excel("서울안녕환자데이터.xlsx")

df = load_data()

# 2) 전처리
# 진료일자 변환
df['진료일자'] = pd.to_datetime(df['진료일자'], format='%Y%m%d')
# 진료시간대 분류 함수
def categorize_time(hms):
    # hms 값을 문자열로 변환한 뒤 반드시 6자리로 앞을 0으로 채움
    if pd.isna(hms):
        time_str = '000000'
    else:
        # 숫자형이면 int로 바꾸고, 문자열이면 그대로 변환
        try:
            val = int(hms)
            time_str = str(val).zfill(6)
        except:
            time_str = str(hms).zfill(6)
    hour = int(time_str[:2])
    return f"{hour:02d}"

# 시간대 컬럼 생성
df['진료시간대'] = df['진료시간'].apply(categorize_time)
# 연령대 구분 (10단위)
bins = list(range(0, 101, 10)) + [999]
labels = ["10대이하"] + [f"{i}대" for i in range(10, 100, 10)] + ["90대이상"]
df['연령대'] = pd.cut(
    df['나이'],
    bins=bins,
    labels=labels,
    right=False,
    include_lowest=True
)

# 3) 사이드바 필터
st.sidebar.header("필터 설정")
# 시작일과 종료일을 별도 입력으로 분리하여 UX 개선
start_date = st.sidebar.date_input(
    "시작 진료일자(2023/11/09)", df['진료일자'].min()
)
end_date = st.sidebar.date_input(
    "종료 진료일자(2025/06/24)", df['진료일자'].max(),
    #min_value=start_date  # 종료일은 시작일보다 이전으로 지정할 수 없음
)
age_band = st.sidebar.multiselect(
    "연령대", options=df['연령대'].cat.categories.tolist(),
    default=df['연령대'].cat.categories.tolist()
)
gender = st.sidebar.selectbox(
    "성별", options=["전체"] + df['성별'].dropna().unique().tolist()
)

# 필터 적용
filtered = df[
    (df['진료일자'] >= pd.to_datetime(start_date)) &
    (df['진료일자'] <= pd.to_datetime(end_date)) &
    (df['연령대'].isin(age_band))
]
if gender != "전체":
    filtered = filtered[filtered['성별'] == gender]

# 4) KPI 카드
total_patients = len(filtered)
new_count = len(filtered[filtered['초/재진'] == "신환"])
return_count = len(filtered[filtered['초/재진'] != "신환"])
new_ratio = new_count / total_patients if total_patients else 0
return_ratio = return_count / total_patients if total_patients else 0
avg_age = filtered['나이'].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("총 환자 수", total_patients)
col2.metric("신환 비율", f"{new_ratio:.1%}")
col3.metric("재방문 비율", f"{return_ratio:.1%}")
col4.metric("평균 연령", f"{avg_age:.1f}세")

# 8) 알림
if new_ratio > 0.5:
    st.success("신환 비율이 50%를 넘었습니다.")
elif return_ratio > 0.7:
    st.success("재방문 비율이 70%를 넘었습니다.")

# 5) 일별 내원 추이
st.subheader("일별 내원 추이")
daily = filtered.groupby('진료일자').size().reset_index(name='count')
# 투명한 포인트를 크게 추가해 hover 인식 영역 확대
base = alt.Chart(daily).encode(
    x='진료일자:T',
    y='count:Q'
)
line = base.mark_line()
points = base.mark_point(size=200, opacity=0).encode(
    tooltip=[
        alt.Tooltip('진료일자:T', title='날짜'),
        alt.Tooltip('count:Q', title='내원 환자 수')
    ]
)
line_chart = (line + points).interactive()
st.altair_chart(line_chart, use_container_width=True)

st.subheader("요일×시간대 내원 패턴")
filtered['요일'] = filtered['진료일자'].dt.day_name()
heat = filtered.groupby(['요일', '진료시간대']).size().reset_index(name='count')
heat_chart = alt.Chart(heat).mark_rect().encode(
    x=alt.X('진료시간대:O', title="시간대"),
    y=alt.Y('요일:O', sort=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']),
    color=alt.Color('count:Q', scale=alt.Scale(scheme='greens'), title='환자 수')
).properties()
st.altair_chart(heat_chart, use_container_width=True)

st.subheader("환자 지도 분포 (Fast Cluster)")
m = folium.Map(location=[37.5665, 126.9780], zoom_start=7)
data = list(filtered.dropna(subset=['y', 'x'])[['y', 'x']].itertuples(index=False, name=None))
FastMarkerCluster(data).add_to(m)
folium_static(m, width=800, height=600)
