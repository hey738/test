import streamlit as st
import pandas as pd

st.set_page_config(page_title="호랑팜 대시보드", layout="wide")

st.header('데모 데이터 입니다~', divider='orange')

# 📊 예시 지표 값 (실제 계산 로직은 추후 연결)
revisit_rate = 85          # %
new_patients = 32          # 최근 30일
avg_revisit_gap = 12.4     # 일

# 🧱 3개 컬럼 구성: 위젯은 왼쪽(col1), 가운데(col2)는 비워둠
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.markdown(
        f"""
        <div style="
            width: 180px;
            height: 180px;
            background-color: #383838;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            margin: auto;
        ">
            <div style="font-size:18px; color:#ccc;">🔁 재방문율</div>
            <div style="font-size: 48px; font-weight: bold; color:white;">{revisit_rate}%</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div style="
            width: 180px;
            height: 180px;
            background-color: #2e8b57;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            margin: auto;
        ">
            <div style="font-size:18px; color:#e0fbe0;">🆕 신규 환자</div>
            <div style="font-size: 48px; font-weight: bold; color:white;">{new_patients}명</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div style="
            width: 180px;
            height: 180px;
            background-color: #4b4b89;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            margin: auto;
        ">
            <div style="font-size:18px; color:#dde5ff;">📅 평균 방문 간격</div>
            <div style="font-size: 36px; font-weight: bold; color:white;">{avg_revisit_gap}일</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# 📊 제목
st.markdown(
    "<h2 style='text-align: left; margin-bottom: 10px;'>📊 전체 기간 월별 환자 방문자 수 (2023~2025)</h2>",
    unsafe_allow_html=True
)

# 📈 데이터 처리 및 차트
@st.cache_data
def load_data():
    df = pd.read_excel('주소변환.xlsx')
    return df

df = load_data()
total_patients = len(df)
drop_patients = len(df[df['최종내원일'].isna()])
df = df[~df['최종내원일'].isna()]

st.text(f'환자 유실율: {round(drop_patients/total_patients*100, 1)}%')
df['연월'] = df['최종내원일'].dt.to_period('M').astype(str)
monthly_visits = df.groupby('연월').size().reset_index(name='방문자수')
monthly_visits = monthly_visits.sort_values('연월')

st.line_chart(monthly_visits.set_index('연월'))
