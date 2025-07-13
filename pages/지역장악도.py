import streamlit as st
import pandas as pd
import altair as alt
import gspread
import numpy as np
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="행정동·연령대별 장악도 분석", layout="wide")

# 시도 명칭 매핑
province_map = {
    '서울': '서울특별시', '인천': '인천광역시', '경기': '경기도', '광주': '광주광역시',
    '부산': '부산광역시', '대구': '대구광역시', '대전': '대전광역시', '울산': '울산광역시',
    '경남': '경상남도', '경북': '경상북도', '전남': '전라남도', '충북': '충청북도', '충남': '충청남도'
}

special_cities = {
    "수원시","성남시","안양시","부천시","안산시",
    "고양시","용인시","청주시","천안시",
    "전주시","포항시","창원시"
}

##### 헬퍼: 계층별 마스크 빌드 #####
def build_mask(df, province, city, dong):
    mask = pd.Series(True, index=df.index)
    if province != "전체":
        mask &= df["시/도"] == province
    if city != "전체":
        mask &= df["시/군/구"] == city
    if dong != "전체":
        mask &= df["행정동"] == dong
    return mask

def split_address(addr: str):
    parts = addr.split()
    # 세종특별자치시 처리: ['세종특별자치시', '어진동']
    if parts[0] == "세종특별자치시" and len(parts) == 2:
        return pd.Series({
            "시/도": parts[0],
            "시/군/구": "",
            "행정동": parts[1]
        })
    # 네 칸짜리: ['경기도', '수원시', '영통구', '망포동']
    elif len(parts) == 4 and parts[1] in special_cities:
        return pd.Series({
            "시/도": parts[0],
            "시/군/구": f"{parts[1]} {parts[2]}",
            "행정동": parts[3]
        })
    # 기본 세 칸짜리: ['서울특별시', '강남구', '역삼동']
    elif len(parts) == 3 and parts[1] not in special_cities:
        return pd.Series({
            "시/도": parts[0],
            "시/군/구": parts[1],
            "행정동": parts[2]
        })
    # 그 외는 무시
    else:
        return pd.Series({
            "시/도": None,
            "시/군/구": None,
            "행정동": None
        })

# 1) 인구 데이터 로드 (Google Sheets)
@st.cache_data
def load_population():
    creds = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds)
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    ws = client.open_by_key(sheet_id).worksheet("연령별인구현황")
    pop = pd.DataFrame(ws.get_all_records())

    split_df = pop["행정기관"].apply(split_address)
    split_df.columns = ["시/도", "시/군/구", "행정동"]

    df = pd.concat([pop, split_df], axis=1)

    df = df[df["시/도"].notna()]

    # 연령대 컬럼 식별
    age_cols = [c for c in df.columns if c not in ['시/도', '시/군/구', '행정동', '행정기관', '행정기관코드','총 인구수', '연령구간인구수']]
    if '총 인구수' in df.columns:
        df = df.rename(columns={'총 인구수':'전체인구'})
    # pop: 행정동(예: '경기도 시흥시 월곶동') + 연령대별 인구수 + 전체인구
    return df[['행정기관'] + ['시/도'] + ['시/군/구'] + ['행정동'] + age_cols + ['전체인구']]

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
    df['행정기관'] = np.where(
        df['시/도'] == '세종특별자치시',
        # 세종일 경우: 시/도 + 행정동
        df['시/도'] + ' ' + df['행정동'],
        # 그 외: 시/도 + 시/군/구 + 행정동
        df['시/도'] + ' ' + df['시/군/구'] + ' ' + df['행정동']
    )
    return [df, acc]

# 데이터 로드
pop_df = load_population()
patient_df, acc = load_patient_data()

# --- 사이드바 expander에 필터 묶기 ---
with st.sidebar.expander("활성 환자 기간", expanded=True):
    months = st.slider("최근 몇 개월 활성으로 볼지", 6, 24, 12)
    cutoff = datetime.now() - timedelta(days=30*months)
    st.write(f"{cutoff.date()} 이후")

# with st.sidebar.expander("지역 선택", expanded=True):
#     # 1) 시/도
#     provinces = ["전체"] + sorted(pop_df['시/도'].unique())
#     default_province = "경기도"
#     province_idx = provinces.index(default_province) if default_province in provinces else 0
#     province = st.selectbox("시/도", provinces, index=province_idx)

#     # 2) 시/군/구
#     if province == "전체":
#         cities = ["전체"]
#     else:
#         cities = ["전체"] + sorted(
#             pop_df[pop_df['시/도']==province]['시/군/구'].unique()
#         )
#     default_city = "시흥시"
#     city_idx = cities.index(default_city) if default_city in cities else 0
#     city = st.selectbox("시/군/구", cities, index=city_idx)

#     # 3) 행정동
#     if province == "전체" or city == "전체":
#         dongs = ["전체"]
#     else:
#         dongs = ["전체"] + sorted(
#             pop_df[
#                 (pop_df['시/도']==province)&
#                 (pop_df['시/군/구']==city)
#             ]['행정동'].unique()
#         )
#     default_dong = "월곶동"
#     dong_idx = dongs.index(default_dong) if default_dong in dongs else 0
#     dong = st.selectbox("행정동", dongs, index=dong_idx)

with st.sidebar.expander("지역 선택", expanded=True):
    provinces = ["전체"] + sorted(pop_df['시/도'].unique())
    province = st.selectbox("시/도", provinces, index=0)
    if province == "전체":
        cities = ["전체"]
    else:
        cities = ["전체"] + sorted(
            pop_df[pop_df['시/도']==province]['시/군/구'].unique()
        )
    city = st.selectbox("시/군/구", cities)
    if province == "전체" or city == "전체":
        dongs = ["전체"]
    else:
        dongs = ["전체"] + sorted(
            pop_df[(pop_df['시/도']==province)&(pop_df['시/군/구']==city)]['행정동'].unique()
        )
    dong = st.selectbox("행정동", dongs)

# --- 활성 환자 필터링 & 집계 ---
active = patient_df[patient_df['진료일자'] >= cutoff].copy()
grouped = (
    active
    .groupby(['시/도','시/군/구','행정동','연령대'])['환자번호']
    .nunique()
    .reset_index(name='환자수')
)

# --- 인구 대비 장악도 계산 ---
# age_cols를 라벨 패턴으로 뽑기 (9세이하 포함)
age_cols = [
    c for c in pop_df.columns
    if c == "9세이하" or c.endswith("대") or c.endswith("세이상")
]

pop_melt = pop_df.melt(
    id_vars=['시/도','시/군/구','행정동','전체인구'],
    value_vars=age_cols,
    var_name='연령대',
    value_name='인구수'
)
pop_melt['인구수'] = (
    pop_melt['인구수']
      .astype(str)
      .str.replace(',', '')
      .pipe(pd.to_numeric, errors='coerce')
)

merge = pd.merge(
    pop_melt, grouped,
    on=['시/도','시/군/구','행정동','연령대'],
    how='left'
).fillna({'환자수':0,'인구수':0})
merge['장악도(%)'] = (merge['환자수']/merge['인구수']*100).round(2)

# --- KPI 카드 ---
mask_pop = build_mask(pop_df, province, city, dong)
mask_pat = build_mask(patient_df, province, city, dong)
mask_act = build_mask(active, province, city, dong)

col1, col2, col3 = st.columns(3)
total_pop       = int(pop_df.loc[mask_pop, '전체인구'].sum())
total_patients  = patient_df.loc[mask_pat, '환자번호'].nunique()
active_patients = active.loc[mask_act, '환자번호'].nunique()
region_pen      = total_patients/total_pop*100 if total_pop else 0
period_pen      = active_patients/total_pop*100 if total_pop else 0

col1.metric("인구수", f"{total_pop:,}명")
col2.metric("환자수", f"{total_patients:,}명")
col3.metric("활성 환자수", f"{active_patients:,}명")

col1.metric("지역 장악도", f"{region_pen:.1f}%")
col2.metric("기간내 장악도", f"{period_pen:.1f}%")
col3.metric("정확도", f"{acc*100:.0f}%")

# --- 연령대 장악도 막대 차트 ---
mask_merge = build_mask(merge, province, city, dong)
sel_df    = merge.loc[mask_merge]

agg_df = (
    sel_df
    .groupby('연령대', as_index=False)[['인구수','환자수']]
    .sum()
)
agg_df['장악도(%)'] = (agg_df['환자수']/agg_df['인구수']*100).round(4)

agg_df['count_label'] = (
    agg_df['환자수'].map(lambda x: f"{x:,}명") +
    " / " +
    agg_df['인구수'].map(lambda x: f"{x:,}명")
)

custom_order = [
    "9세이하", "10대", "20대", "30대", "40대",
    "50대", "60대", "70대", "80대", "90대", "100세이상"
]

title = (
    f"{dong} 연령대 장악도" if dong!="전체" else
    f"{province} {city} 연령대 장악도" if city!="전체" else
    f"{province} 연령대 장악도" if province!="전체" else
    "전체 지역 연령대 장악도"
)
st.subheader(title)

bar = (
    alt.Chart(agg_df)
       .mark_bar()
       .encode(
           x=alt.X('연령대:O', sort=custom_order, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(
                '장악도(%):Q',
                axis=alt.Axis(format='.4f'),  # 소수점 두 자리로 라벨
                title='장악도(%)'
            ),
           tooltip=[
               alt.Tooltip('인구수:Q', title='인구수', format=','),
               alt.Tooltip('환자수:Q', title='환자수', format=','),
               alt.Tooltip('장악도(%):Q', title='장악도(%)', format='.4f'),
           ]
       )
       .properties(height=400, width={'step':60})
)

# 2) 퍼센트 레이블 (막대 위에)
label_rate = (
    alt.Chart(agg_df)
      .transform_calculate(
        display="""
          format(datum["장악도(%)"], ".4f") + "%"
        """
      )
      .mark_text(
        align='center',
        baseline='middle',
        dy=-20,
        fontWeight='bold'
      )
      .encode(
        x=alt.X('연령대:O', sort=custom_order),
        y=alt.Y('장악도(%):Q'),
        text=alt.Text('display:N')
      )
)

# 3) 환자수/인구수 레이블 (퍼센트 레이블 바로 아래)
label_count = (
    alt.Chart(agg_df)
      .transform_calculate(
        display="""
          format(datum["환자수"], ",") + ' / ' + format(datum["인구수"], ",")
        """
      )
      .mark_text(
         dy=2,                # 퍼센트 레이블에서 2px 아래
         fontWeight='bold',
         align='center',
         baseline='top'
      )
      .encode(
         x=alt.X('연령대:O', sort=custom_order),
         y=alt.Y('장악도(%):Q'),
         text=alt.Text('count_label:N')  
      )
)

final = bar + label_rate + label_count
st.altair_chart(final, use_container_width=True)

# 1) 전치 & 컬럼 순서 재배치
df_t = agg_df.set_index('연령대').T[custom_order].copy()

# 2) 각 행을 문자열로 포맷
df_t.loc['인구수']     = df_t.loc['인구수'].astype(int).map("{:,}".format)
df_t.loc['환자수']     = df_t.loc['환자수'].astype(int).map("{:,}".format)
df_t.loc['장악도(%)']  = df_t.loc['장악도(%)'].map(lambda x: f"{x:.4f}%")

# 3) 전체를 str 타입으로 강제 캐스팅
df_t = df_t.astype(str)

# 4) 데이터프레임 출력
st.dataframe(df_t)
