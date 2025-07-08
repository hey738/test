import streamlit as st
import pandas as pd
import altair as alt
import folium
import gspread
from streamlit_folium import folium_static
from folium.plugins import FastMarkerCluster
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="환자 대시보드", layout="wide")

# 1) 데이터 로드 (Google Sheets via API)
@st.cache_data
def load_data():
    creds_dict = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds_dict)
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    worksheet_name = st.secrets["google_sheets"]["worksheet_name"]
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    records = sheet.get_all_records()
    return pd.DataFrame(records)

df = load_data()

# 2) 전처리
df['진료일자'] = pd.to_datetime(df['진료일자'], format='%Y%m%d')

def categorize_time(hms):
    if pd.isna(hms):
        time_str = '000000'
    else:
        try:
            val = int(hms)
            time_str = str(val).zfill(6)
        except:
            time_str = str(hms).zfill(6)
    hour = int(time_str[:2])
    return f"{hour:02d}"

df['진료시간대'] = df['진료시간'].apply(categorize_time)

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
start_date = st.sidebar.date_input("시작 진료일자", df['진료일자'].min())
end_date = st.sidebar.date_input("종료 진료일자", df['진료일자'].max())
age_band = st.sidebar.multiselect(
    "연령대",
    options=df['연령대'].cat.categories.tolist(),
    default=df['연령대'].cat.categories.tolist()
)
gender = st.sidebar.selectbox(
    "성별",
    options=["전체"] + df['성별'].dropna().unique().tolist()
)

filtered = df[
    (df['진료일자'] >= pd.to_datetime(start_date)) &
    (df['진료일자'] <= pd.to_datetime(end_date)) &
    (df['연령대'].isin(age_band))
]
if gender != "전체":
    filtered = filtered[filtered['성별'] == gender]

# 4) KPI 카드
total_patients = len(filtered.drop_duplicates("환자번호"))
total_counts = len(filtered)
new_count = len(filtered[filtered['초/재진'] == "신환"])
return_count = len(filtered[filtered['초/재진'] != "신환"])
new_ratio = new_count / total_counts if total_counts else 0
return_ratio = return_count / total_counts if total_counts else 0
avg_age = filtered['나이'].mean()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("총 환자 수", f"{total_patients:,}명")
col2.metric("총 진료 횟수", f"{total_counts:,}번")
col3.metric("신환 비율", f"{new_ratio:.1%}")
col4.metric("재방문 비율", f"{return_ratio:.1%}")
col5.metric("평균 연령", f"{avg_age:.1f}세")

# 5) 일별 내원 추이 (토글 가능한 추세선)
st.subheader("일별 내원 추이")

# 일별 집계
daily = (
    filtered
    .groupby('진료일자')
    .size()
    .reset_index(name='환자수')
    .sort_values('진료일자')
)
# 이동평균 컬럼 추가
daily['MA6']  = daily['환자수'].rolling(window=6,  min_periods=1).mean()
daily['MA30'] = daily['환자수'].rolling(window=30, min_periods=1).mean()
daily['MA60'] = daily['환자수'].rolling(window=60, min_periods=1).mean()
daily['MA90'] = daily['환자수'].rolling(window=90, min_periods=1).mean()

# long form 변환
melted = daily.melt(
    id_vars='진료일자',
    value_vars=['환자수','MA6','MA30','MA60','MA90'],
    var_name='지표',
    value_name='값'
)

# 범례 클릭으로 토글할 셀렉션
legend_sel = alt.selection_multi(fields=['지표'], bind='legend')

# 차트
trend_chart = (
    alt.Chart(melted)
       .mark_line()
       .encode(
           x=alt.X('진료일자:T', title='진료일자'),
           y=alt.Y('값:Q', title='진료 횟수'),
           color=alt.Color('지표:N', title='지표'),
           opacity=alt.condition(legend_sel, alt.value(1), alt.value(0.1)),
           tooltip=[
               alt.Tooltip('진료일자:T', title='날짜'),
               alt.Tooltip('지표:N', title='지표'),
               alt.Tooltip('값:Q', title='값')
           ]
       )
       .add_selection(legend_sel)
       .interactive()
       .properties(height=400)
)

st.altair_chart(trend_chart, use_container_width=True)

# 6) 요일×시간대 히트맵
st.subheader("요일×시간대 내원 패턴")
filtered['요일'] = filtered['진료일자'].dt.day_name()
heat = filtered.groupby(['요일', '진료시간대']).size().reset_index(name='count')
heat_chart = alt.Chart(heat).mark_rect().encode(
    x=alt.X('진료시간대:O', title="시간대", axis=alt.Axis(labelAngle=0)),
    y=alt.Y('요일:O', sort=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']),
    color=alt.Color('count:Q', scale=alt.Scale(scheme='blues'), title='환자 수')
)
st.altair_chart(heat_chart, use_container_width=True)

# 7) 환자 지도 분포
st.subheader("환자 지도 분포")
m = folium.Map(location=[37.5665, 126.9780], zoom_start=7)
filtered['x'].replace("", pd.NA, inplace=True)
filtered['y'].replace("", pd.NA, inplace=True)
data = list(filtered.dropna(subset=['y','x'])[['y','x']].itertuples(index=False, name=None))
FastMarkerCluster(data).add_to(m)
folium_static(m, width=800, height=600)
