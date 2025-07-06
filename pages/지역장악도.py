import streamlit as st
import pandas as pd
import folium
import altair as alt
import gspread
from streamlit_folium import folium_static
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="행정동·연령대별 장악도 분석", layout="wide")

# 시도 명칭 매핑
province_map = {
    '서울': '서울특별시', '인천': '인천광역시', '경기': '경기도', '광주': '광주광역시',
    '부산': '부산광역시', '대구': '대구광역시', '대전': '대전광역시', '울산': '울산광역시',
    '경남': '경상남도', '경북': '경상북도', '전남': '전라남도', '충북': '충청북도', '충남': '충청남도'
}

# 1) 인구 데이터 로드 (Google Sheets)
@st.cache_data
def load_population():
    creds = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds)
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    ws = client.open_by_key(sheet_id).worksheet("연령별인구현황")
    pop = pd.DataFrame(ws.get_all_records())
    pop = pop.rename(columns={"행정기관": "행정동"})
    # 연령대 컬럼 식별
    age_cols = [c for c in pop.columns if c not in ['행정동','행정기관코드','총 인구수', '연령구간인구수']]
    if '총 인구수' in pop.columns:
        pop = pop.rename(columns={'총 인구수':'전체인구'})
    # pop: 행정동(예: '경기도 시흥시 월곶동') + 연령대별 인구수 + 전체인구
    return pop[['행정동'] + age_cols + ['전체인구']]

# 2) 환자 데이터 로드 및 전처리
@st.cache_data
def load_patient_data():
    creds = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds)
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    ws = client.open_by_key(sheet_id).worksheet("Sheet1")
    df = pd.DataFrame(ws.get_all_records())
    # 진료일자 변환
    df['진료일자'] = pd.to_datetime(df['진료일자'], format='%Y%m%d')
    # 중복 환자ID: 마지막 진료일 기준
    df = df.sort_values('진료일자').drop_duplicates('환자번호', keep='last')
    # 연령대 컬럼 생성
    bins = list(range(0, 101, 10)) + [999]
    labels = ["0-9세"] + [f"{i}대" for i in range(10,100,10)] + ["100세이상"]
    df['연령대'] = pd.cut(df['나이'], bins=bins, labels=labels, right=False)
    acc = len(df[df['행정동'] != ""]) / len(df)
    # 시도명 매핑
    df['시/도'] = df['시/도'].map(province_map).fillna(df['시/도'])
    # full 행정동 생성 (예: '경기도 시흥시 월곶동')
    df['행정동'] = df['시/도'] + ' ' + df['시/군/구'] + ' ' + df['행정동']
    return [df, acc]

# 데이터 로드
pop_df = load_population()
patient_df, acc = load_patient_data()

# 3) 활성 환자 기간 설정
st.sidebar.header("활성 환자 기간 설정")
months = st.sidebar.slider("최근 몇 개월 활성으로 볼지", 6, 24, 12)
cutoff = datetime.now() - timedelta(days=30*months)
st.sidebar.write(f"컷오프 날짜: {cutoff.date()}")

# 4) 활성 환자 필터링 및 집계
active = patient_df[patient_df['진료일자'] >= cutoff].copy()
# 행정동․연령대별 고유 환자 수
grouped = active.groupby(['행정동','연령대'])['환자번호'].nunique().reset_index(name='환자수')

# 5) 인구 대비 장악도 계산
age_cols = [c for c in pop_df.columns if c not in ['행정동','전체인구']]
pop_melt = pop_df.melt(id_vars=['행정동','전체인구'], value_vars=age_cols, var_name='연령대', value_name='인구수')
merge = pd.merge(pop_melt, grouped, on=['행정동','연령대'], how='left').fillna({'환자수':0})
merge['장악도(%)'] = (merge['환자수']/merge['인구수']*100).round(2)

default = "경기도 시흥시 월곶동"
options = merge['행정동'].unique().tolist()
sel = st.selectbox('행정동 선택', options, index=options.index(default))

# KPI 카드
col1, col2, col3 = st.columns(3)
col1.metric("인구수", f"{pop_df[pop_df['행정동']==sel]['전체인구'].values[0]:,}명")
col2.metric("환자수", f"{len(patient_df[patient_df['행정동'] == sel]):,}명")
col3.metric("활성 환자수", f"{len(active[active['행정동'] == sel]):,}명")
col1.metric("지역 장악도", f"{round(len(patient_df[patient_df['행정동'] == sel]) / (pop_df[pop_df['행정동']==sel]['전체인구'].values[0])*100, 1)}%")
col2.metric("기간내 지역 장악도", f"{round(len(active[active['행정동'] == sel]) / (pop_df[pop_df['행정동']==sel]['전체인구'].values[0])*100, 1)}%")
col3.metric("정확도", f"{round(acc*100)}%")

# 7) 특정 행정동 선택 그래프
st.subheader(f"{sel} 연령대 장악도 비교")
sel_df = merge[merge['행정동']==sel]
# 원하는 순서 리스트
custom_order = [
    "0-9세", "10대", "20대", "30대", "40대",
    "50대", "60대", "70대", "80대", "90대", "100세이상"
]

# 차트
bar = (
    alt.Chart(sel_df)
       .mark_bar()
       .encode(
           x=alt.X(
               "연령대:O",
               title="연령대",
               sort=custom_order,                  # 순서 지정
               axis=alt.Axis(labelAngle=-45),      # 레이블 -45도 회전
               scale=alt.Scale(rangeStep=50)       # (선택) 막대 폭 조절
           ),
           y=alt.Y("장악도(%):Q", title="장악도(%)"),
           tooltip=[
               alt.Tooltip("인구수:Q", title="인구수"),
               alt.Tooltip("환자수:Q", title="환자수"),
               alt.Tooltip("장악도(%):Q", title="장악도(%)"),
           ]
       )
       .properties(height=400)
)
st.altair_chart(bar, use_container_width=True)
