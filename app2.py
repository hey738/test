import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static



# 1) 데이터 로딩
@st.cache_data
def load_data():
    df = pd.read_excel('주소변환.xlsx')
    return df

df = load_data()

# 1. 방문 날짜 필터
st.sidebar.subheader("기간 선택")
year_list = sorted(df['최종내원일'].dt.year.dropna().astype(int).unique())
selected_year = st.sidebar.selectbox("연도", ['전체'] + year_list, key='selected_year')
# '전체' 선택 시 모든 년도
if selected_year != '전체':
    month_list = sorted(df[df['최종내원일'].dt.year == selected_year]['최종내원일'].dt.month.unique())
else:
    month_list = sorted(df['최종내원일'].dt.month.dropna().astype(int).unique())
selected_month = st.sidebar.selectbox("월", ['전체'] + month_list, key='selected_month')
# 날짜 범위
min_date = df['최종내원일'].min().date()
max_date = df['최종내원일'].max().date()
start_date, end_date = st.sidebar.date_input(
    "기간 선택",
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date,
    key='date_range'
)

# 2. 행정구역 필터
st.sidebar.subheader("지역 설정")
# 시/도
sido_list = sorted(df['region_1depth'].dropna().unique())
selected_sido = st.sidebar.selectbox("시/도", ['전체'] + sido_list, key='selected_sido')
# 시/군/구
if selected_sido != '전체':
    sigungu_list = sorted(df[df['region_1depth'] == selected_sido]['region_2depth'].dropna().unique())
else:
    sigungu_list = sorted(df['region_2depth'].dropna().unique())
selected_sigungu = st.sidebar.selectbox("시/군/구", ['전체'] + sigungu_list, key='selected_sigungu')
# 읍/면/동
if selected_sigungu != '전체':
    eup_list = sorted(df[df['region_2depth'] == selected_sigungu]['region_3depth'].dropna().unique())
elif selected_sido != '전체':
    eup_list = sorted(df[df['region_1depth'] == selected_sido]['region_3depth'].dropna().unique())
else:
    eup_list = sorted(df['region_3depth'].dropna().unique())
selected_eup = st.sidebar.selectbox("읍/면/동", ['전체'] + eup_list, key='selected_eup')

# 3. 인구·환자 속성 필터
st.sidebar.subheader("환자 정보")
selected_gender = st.sidebar.selectbox(
    "성별",
    ['전체'] + sorted(df['성별'].dropna().unique()),
    key='selected_gender'
)
selected_nationality = st.sidebar.selectbox(
    "내/외국인 여부",
    ['전체'] + sorted(df['국적'].dropna().unique()),
    key='selected_nationality'
)
age_groups = ['아동(6~12)', '청소년(13~18)', '청년(19~29)', '장년(30~44)', '중년(45~64)', '전기노인(65~74)', '후기노인(75+)']
selected_agegroup = st.sidebar.selectbox(
    "연령대",
    ['전체'] + age_groups,
    key='selected_agegroup'
)

# --- 데이터 필터링 함수 ---
def filter_data(df):
    tmp = df.copy()
    # 날짜
    if selected_year != '전체':
        tmp = tmp[tmp['최종내원일'].dt.year == selected_year]
    if selected_month != '전체':
        tmp = tmp[tmp['최종내원일'].dt.month == selected_month]
    tmp = tmp[(tmp['최종내원일'].dt.date >= start_date) & (tmp['최종내원일'].dt.date <= end_date)]
    # 지역
    if selected_sido != '전체': tmp = tmp[tmp['region_1depth'] == selected_sido]
    if selected_sigungu != '전체': tmp = tmp[tmp['region_2depth'] == selected_sigungu]
    if selected_eup != '전체': tmp = tmp[tmp['region_3depth'] == selected_eup]
    # 인구
    if selected_gender != '전체': tmp = tmp[tmp['성별'] == selected_gender]
    if selected_nationality != '전체': tmp = tmp[tmp['국적'] == selected_nationality]
    if selected_agegroup != '전체': tmp = tmp[tmp['나이대'] == selected_agegroup]
    return tmp

# 4) 좌표가 있는 데이터만 사용
df = df.dropna(subset=['y', 'x'])
# 필터링 적용
filtered_df = filter_data(df)

# 5) 결과 출력
st.write(f"필터된 환자 수: {len(filtered_df)}")
st.dataframe(filtered_df)

# 6) 클러스터링 지도 시각화
if not filtered_df.empty:
    center = [filtered_df['y'].mean(), filtered_df['x'].mean()]
else:
    center = [37.3894945307695, 126.738758120593]  # 서울 기본
m = folium.Map(location=center, zoom_start=12)
marker_cluster = MarkerCluster().add_to(m)
for _, row in filtered_df.iterrows():
    folium.Marker(
        location=[row['y'], row['x']],
        popup=row.get('주소', '')
    ).add_to(marker_cluster)
folium_static(m, width=1000, height=750)
