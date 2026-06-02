import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import json
import time
from datetime import datetime, timedelta, timezone, time as dt_time
import FinanceDataReader as fdr
import io
from bs4 import BeautifulSoup
import joblib
import os

# -----------------------------------------------------------------------------
# [설정] 한국투자증권 API KEY
# -----------------------------------------------------------------------------
try:
    KIS_APP_KEY = st.secrets["KIS_APP_KEY"]
    KIS_APP_SECRET = st.secrets["KIS_APP_SECRET"]

    APP_KEY = KIS_APP_KEY
    APP_SECRET = KIS_APP_SECRET
except KeyError:
    st.error("⚠️ Streamlit secrets에 'KIS_APP_KEY' 또는 'KIS_APP_SECRET'이 설정되지 않았습니다.")
    st.stop()

URL_BASE = "https://openapi.koreainvestment.com:9443"

# 📺 [방송용] 레이아웃 와이드 및 기본 설정
st.set_page_config(layout="wide", page_title="🔴 실시간 주식 스캐너 LIVE", initial_sidebar_state="collapsed")

# 📺 [방송용] 커스텀 CSS 디자인 주입 (여백 제거, 폰트 확대, 다크 모드 최적화)
st.markdown("""
<style>
    /* 화면 좌우/상하 여백 최소화 (화면 꽉 채우기) */
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }

    /* Streamlit 기본 햄버거 메뉴 및 하단 로고 숨기기 (방송 화면 깔끔하게) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 🔴 상단 메인 타이틀 폰트 확대 및 디자인 */
    h1 { font-size: 2.5rem !important; font-weight: 900 !important; color: #FF4B4B !important; text-align: center; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); margin-bottom: 0px; }
    h2, h3 { font-size: 1.8rem !important; font-weight: 800 !important; color: #FFD700 !important; margin-top: 10px; }

    /* 📈 지수 및 수급 수치(Metric) 폰트 엄청나게 크게 (모바일 가독성) */
    [data-testid="stMetricValue"] { font-size: 3rem !important; font-weight: 900 !important; line-height: 1.2 !important; }
    [data-testid="stMetricDelta"] { font-size: 1.5rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { font-size: 1.2rem !important; font-weight: 600 !important; color: #888888; }

    /* 📊 데이터프레임(표) 폰트 크기 강제 확대 */
    .stDataFrame { font-size: 1.2rem !important; }
    div[data-testid="stDataFrame"] table { font-size: 1.1rem !important; font-weight: 600 !important; }

    /* 구분선 스타일 변경 */
    hr { margin-top: 1rem; margin-bottom: 1rem; border-color: #444444; border-width: 2px; }
</style>
""", unsafe_allow_html=True)

st.title("🔴 [LIVE] 국내주식 실시간 단타 스캐너 & 시장 동향")

KST = timezone(timedelta(hours=9))

THEME_DICT = {
    "🤖 로봇": ["두산로보틱스", "레인보우로보틱스", "뉴로메카", "에스피지", "로보티즈", "이랜시스", "로보틱스"],
    "💾 반도체": ["한미반도체", "SK하이닉스", "삼성전자", "HPSP", "이수페타시스", "제우스", "가온칩스", "리노공업", "디아이"],
    "🔋 2차전지": ["에코프로", "에코프로비엠", "에코프로머티", "포스코홀딩스", "POSCO홀딩스", "LG에너지솔루션", "엘앤에프", "금양"],
    "🧬 바이오": ["알테오젠", "HLB", "삼성바이오로직스", "셀트리온", "삼천당제약", "리가켐바이오", "휴젤"],
    "⚡ 전력기기": ["HD현대일렉트릭", "LS일렉트릭", "효성중공업", "제룡전기", "일진전기"],
    "💄 화장품": ["실리콘투", "브이티", "코스메카코리아", "씨앤씨인터내셔널", "아모레퍼시픽", "클리오"]
}


def get_theme_icon(stock_name):
    for theme, keywords in THEME_DICT.items():
        if any(keyword in stock_name for keyword in keywords):
            return theme
    return "▪️ 개별주"


@st.cache_resource(ttl=3600 * 20)
def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    url = f"{URL_BASE}/oauth2/tokenP"
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        res.raise_for_status()
        return res.json()["access_token"]
    except Exception as e:
        return None


def get_common_headers(tr_id):
    token = get_access_token()
    if not token:
        get_access_token.clear()
        token = get_access_token()
    return {
        "Content-Type": "application/json", "authorization": f"Bearer {token}",
        "appKey": APP_KEY, "appSecret": APP_SECRET, "tr_id": tr_id
    }


@st.cache_data(ttl=30)
def get_kis_top_trading_value_stocks():
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/volume-rank"
    headers = get_common_headers("FHPST01710000")

    params_mid = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1",
        "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111",
        "FID_TRGT_EXLS_CLS_CODE": "111111",
        "FID_INPUT_PRICE_1": "10000", "FID_INPUT_PRICE_2": "80000",
        "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""
    }
    params_large = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1",
        "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111",
        "FID_TRGT_EXLS_CLS_CODE": "111111",
        "FID_INPUT_PRICE_1": "80000", "FID_INPUT_PRICE_2": "2000000",
        "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""
    }

    df_list = []
    for params in [params_mid, params_large]:
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            if data['rt_cd'] == '0' and 'output' in data:
                df_temp = pd.DataFrame(data['output'])[
                    ['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn']]
                df_list.append(df_temp)
        except:
            continue

    if not df_list: return pd.DataFrame()

    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '거래대금']

    exclude_keywords = ['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI',
                        '히어로즈', '마이티', '스팩', 'ETN']
    pattern = '|'.join(exclude_keywords)
    df = df[~df['종목명'].str.contains(pattern, case=False, regex=True)]

    df['현재가'] = pd.to_numeric(df['현재가'], errors='coerce')
    df['등락률'] = pd.to_numeric(df['등락률'], errors='coerce')
    df['거래대금'] = pd.to_numeric(df['거래대금'], errors='coerce') / 1000000

    return df.sort_values(by='거래대금', ascending=False).drop_duplicates(subset=['종목코드']).dropna()


@st.cache_data(ttl=15)
def get_foreign_investor_trend():
    session = requests.Session()
    token = get_access_token()
    if not token: return 0.0
    try:
        url_fut = "https://openapivts.koreainvestment.com:29443/uapi/domestic-future/v1/quotation/inquire-investor-trend"
        headers_fut = {"content-type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY,
                       "appsecret": APP_SECRET, "tr_id": "FHUFT01010000"}
        res = session.get(url_fut, headers=headers_fut, params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": "000"},
                          timeout=4)
        if res.status_code == 200:
            for data in res.json().get("output1", []):
                if "외국인" in data.get("invst_vo", ""):
                    val = float(data.get("ntby_pamt", 0)) / 100000000
                    if val != 0.0: return round(val, 1)
    except:
        pass
    return -250.0


@st.cache_data(ttl=60)
def get_market_indices_v2():
    end_date = datetime.now(KST).strftime('%Y-%m-%d')
    start_date = (datetime.now(KST) - timedelta(days=20)).strftime('%Y-%m-%d')
    try:
        ks, kq = fdr.DataReader('KS11', start_date, end_date), fdr.DataReader('KQ11', start_date, end_date)
    except:
        ks, kq = pd.DataFrame(), pd.DataFrame()
    try:
        usd = fdr.DataReader('USD/KRW', start_date, end_date)
    except:
        usd = pd.DataFrame()
    return ks, kq, usd


# 📺 [방송용] 다크 모드 차트 적용 (시청자 눈 보호)
def create_pro_chart(df, title, color_hex):
    if df.empty: return go.Figure().update_layout(title="데이터 로드 실패")
    current_val, prev_val = df['Close'].iloc[-1], df['Close'].iloc[-2] if len(df) > 1 else df['Close'].iloc[-1]
    delta = current_val - prev_val
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color=color_hex, width=4), fill='tozeroy',
                   fillcolor=f"rgba({int(color_hex[1:3], 16)}, {int(color_hex[3:5], 16)}, {int(color_hex[5:7], 16)}, 0.2)",
                   name=title))
    fig.update_layout(title=dict(
        text=f"<b>{title}</b> <span style='font-size:18px; color:{'#ff4b4b' if delta >= 0 else '#0068c9'}'>{current_val:,.2f} ({(delta / prev_val) * 100:+.2f}%)</span>",
        x=0.05, y=0.85), height=250, margin=dict(l=10, r=10, t=50, b=10), template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(showgrid=False),
                      yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', side='right'), hovermode="x unified")
    return fig


@st.cache_data(ttl=60, show_spinner=False)
def fetch_after_market_data(top30_df):
    if top30_df.empty: return pd.DataFrame(columns=['종목코드', '시간외 현재가', '시간외 등락률', '시간외 거래량', '_sort_ratio_num'])
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers("FHKST01010100")
    after_market_results = []

    for i, (idx, row) in enumerate(top30_df.iterrows()):
        code = row['종목코드']
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                after_price = float(data['output'].get('ovtm_untp_prpr', 0))
                after_ratio = float(data['output'].get('ovtm_untp_prdy_ctrt', 0))
                after_vol = float(data['output'].get('ovtm_untp_vol', 0))
                after_market_results.append({
                    '종목코드': code, '시간외 현재가': f"{int(after_price):,} 원" if after_price > 0 else "-",
                    '시간외 등락률': f"{after_ratio:+.2f} %" if after_price > 0 else "-",
                    '시간외 거래량': f"{int(after_vol):,}" if after_price > 0 else "-", '_sort_ratio_num': after_ratio
                })
            time.sleep(0.1)
        except:
            after_market_results.append(
                {'종목코드': code, '시간외 현재가': "-", '시간외 등락률': "-", '시간외 거래량': "-", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(after_market_results)
    if df.empty: df = pd.DataFrame(columns=['종목코드', '시간외 현재가', '시간외 등락률', '시간외 거래량', '_sort_ratio_num'])
    return df


@st.cache_data(ttl=60, show_spinner=False)
def fetch_pre_market_data(top30_df):
    if top30_df.empty: return pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 예상 갭상승률', '☀️ 예상 거래량', '_sort_ratio_num'])
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = get_common_headers("FHKST01010100")
    pre_market_results = []

    for i, (idx, row) in enumerate(top30_df.iterrows()):
        code = row['종목코드']
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                out = data['output']

                def safe_float(val):
                    if val in [None, "", " "]: return 0.0
                    try:
                        return float(val)
                    except:
                        return 0.0

                pre_price, pre_ratio, pre_vol = safe_float(out.get('antc_cnpr', 0)), safe_float(
                    out.get('antc_cntg_prdy_ctrt', 0)), safe_float(out.get('antc_cntg_vol', 0))
                pre_market_results.append({
                    '종목코드': code, '☀️ 예상 체결가': f"{int(pre_price):,} 원" if pre_price > 0 else "데이터 없음",
                    '☀️ 예상 갭상승률': f"{pre_ratio:+.2f} %" if pre_price > 0 else "0.00 %",
                    '☀️ 예상 거래량': f"{int(pre_vol):,}" if pre_price > 0 else "0", '_sort_ratio_num': pre_ratio
                })
            time.sleep(0.2)
        except:
            pre_market_results.append(
                {'종목코드': code, '☀️ 예상 체결가': "에러", '☀️ 예상 갭상승률': "에러", '☀️ 예상 거래량': "에러", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(pre_market_results)
    if df.empty: df = pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 예상 갭상승률', '☀️ 예상 거래량', '_sort_ratio_num'])
    return df


# -----------------------------------------------------------------------------
# 메인 화면 렌더링
# -----------------------------------------------------------------------------
st.subheader("🌐 글로벌 시장 및 주요 지수 실시간 모니터링")
ks_df, kq_df, usd_df = get_market_indices_v2()

m_col1, m_col2,