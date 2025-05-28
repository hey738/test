import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import folium_static

# 1) 데이터 로딩
@st.cache_data
def load_data():
    df = pd.read_excel('주소변환.xlsx', parse_dates=['최종내원일'])
    return df

df = load_data().dropna(subset=['y','x'])  # 좌표 없는 행 미리 제거

# 필터를 한 번에 처리할 폼
with st.sidebar.form(key="filter_form"):
    st.subheader("기간 선택")
    # 연도
    year_list = sorted(df['최종내원일'].dt.year.dropna().astype(int).unique())
    sel_year = st.selectbox("연도", ['전체'] + year_list, key='selected_year')
    # 월
    if sel_year != '전체':
        month_list = sorted(df[df['최종내원일'].dt.year == sel_year]['최종내원일']
                            .dt.month.dropna().astype(int).unique())
    else:
        month_list = sorted(df['최종내원일'].dt.month.dropna().astype(int).unique())
    sel_month = st.selectbox("월", ['전체'] + month_list, key='selected_month')

    # 날짜 범위
    min_date = df['최종내원일'].min().date()
    max_date = df['최종내원일'].max().date()
    start_date, end_date = st.date_input(
        "날짜 범위", [min_date, max_date],
        min_value=min_date, max_value=max_date,
        key='date_range'
    )

    st.subheader("지역 설정")
    # 시/도
    sido_list = sorted(df['region_1depth'].dropna().unique())
    sel_sido = st.selectbox("시/도", ['전체'] + sido_list, key='selected_sido')
    # 시/군/구
    if sel_sido != '전체':
        sigungu_list = sorted(df[df['region_1depth']==sel_sido]['region_2depth'].dropna().unique())
    else:
        sigungu_list = sorted(df['region_2depth'].dropna().unique())
    sel_sigungu = st.selectbox("시/군/구", ['전체'] + sigungu_list, key='selected_sigungu')
    # 읍/면/동
    if sel_sigungu != '전체':
        eup_list = sorted(df[df['region_2depth']==sel_sigungu]['region_3depth'].dropna().unique())
    elif sel_sido != '전체':
        eup_list = sorted(df[df['region_1depth']==sel_sido]['region_3depth'].dropna().unique())
    else:
        eup_list = sorted(df['region_3depth'].dropna().unique())
    sel_eup = st.selectbox("읍/면/동", ['전체'] + eup_list, key='selected_eup')

    st.subheader("환자 정보")
    sel_gender = st.selectbox("성별", ['전체'] + sorted(df['성별'].dropna().unique()), key='selected_gender')
    sel_nat    = st.selectbox("내/외국인 여부", ['전체'] + sorted(df['국적'].dropna().unique()), key='selected_nationality')
    age_groups = ['아동(6~12)','청소년(13~18)','청년(19~29)','장년(30~44)','중년(45~64)','전기노인(65~74)','후기노인(75+)']
    sel_age    = st.selectbox("연령대", ['전체'] + age_groups, key='selected_agegroup')

    # 폼 전송 버튼
    apply = st.form_submit_button("적용")

# 필터링 함수
def filter_data(df,
                year, month, sd, ed,
                sido, sigungu, eup,
                gender, nat, age):
    tmp = df.copy()
    if year!='전체':
        tmp = tmp[tmp['최종내원일'].dt.year==year]
    if month!='전체':
        tmp = tmp[tmp['최종내원일'].dt.month==month]
    tmp = tmp[(tmp['최종내원일'].dt.date>=sd)&(tmp['최종내원일'].dt.date<=ed)]
    if sido!='전체':
        tmp = tmp[tmp['region_1depth']==sido]
    if sigungu!='전체':
        tmp = tmp[tmp['region_2depth']==sigungu]
    if eup!='전체':
        tmp = tmp[tmp['region_3depth']==eup]
    if gender!='전체':
        tmp = tmp[tmp['성별']==gender]
    if nat!='전체':
        tmp = tmp[tmp['국적']==nat]
    if age!='전체':
        tmp = tmp[tmp['나이대']==age]
    return tmp

# 폼 적용 여부에 따라 데이터 결정
if apply:
    filtered_df = filter_data(
        df,
        sel_year, sel_month, start_date, end_date,
        sel_sido, sel_sigungu, sel_eup,
        sel_gender, sel_nat, sel_age
    )
else:
    # 적용 전엔 전체 데이터 혹은 이전 결과 유지
    filtered_df = df.copy()

#  결과 출력
st.write(f"필터된 환자 수: {len(filtered_df)}")
st.dataframe(filtered_df)

# 지도 클러스터링
center = ([filtered_df['y'].mean(), filtered_df['x'].mean()]
          if not filtered_df.empty else [37.5665,126.9780])
m = folium.Map(location=center, zoom_start=12)
marker_cluster = MarkerCluster().add_to(m)
for _, r in filtered_df.iterrows():
    folium.Marker([r['y'],r['x']], popup=r.get('주소','')).add_to(marker_cluster)
folium_static(m, width=1000, height=750)
