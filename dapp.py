import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta, timezone, time as dt_time
import FinanceDataReader as fdr
import os
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# [설정] 한국투자증권 API KEY (.env 파일 연동)
# -----------------------------------------------------------------------------
load_dotenv() 

APP_KEY = os.environ.get("APP_KEY") or os.environ.get("KIS_APP_KEY")
APP_SECRET = os.environ.get("APP_SECRET") or os.environ.get("KIS_APP_SECRET")

if not APP_KEY or not APP_SECRET:
    st.error("⚠️ 서버의 '.env' 파일에 앱키(APP_KEY) 또는 시크릿키(APP_SECRET)가 설정되지 않았습니다.")
    st.stop()

URL_BASE = "https://openapi.koreainvestment.com:9443" 

# 📱 [쇼츠용 세로 뷰] 레이아웃 설정
st.set_page_config(layout="wide", page_title="🔴 하이모바일 쇼츠 LIVE", initial_sidebar_state="collapsed")

# 🎨 카드형 디자인 전용 CSS
st.markdown("""
<style>
    /* 전체 배경을 어둡게 설정 및 여백 최적화 */
    .stApp { background-color: #0f0f13; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; max-width: 100%; }
    header[data-testid="stHeader"], #MainMenu, footer { display: none !important; }
    
    /* 🎯 메인 타이틀 (AI 스윙 타점 TOP 10) */
    .main-title { color: #ff4b4b; font-size: 2.8rem; font-weight: 900; text-align: center; margin-bottom: 10px; letter-spacing: -1px; }
    
    /* ⚡ 노란색 시간 캡슐 (사진과 동일하게) */
    .time-container { text-align: center; margin-bottom: 25px; }
    .time-pill { background-color: #eab308; color: #000000; font-size: 1.5rem; font-weight: 900; padding: 6px 25px; border-radius: 50px; display: inline-block; box-shadow: 0 0 15px rgba(234, 179, 8, 0.4); letter-spacing: 1px; }
    
    /* 🃏 카드 전체 레이아웃 */
    .stock-card { background-color: #1a1a21; border-radius: 12px; padding: 15px 18px; margin-bottom: 12px; display: flex; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.2); border: 1px solid #27272a; }
    
    /* 🔴 랭킹 동그라미 뱃지 */
    .rank-circle { background: linear-gradient(135deg, #f87171, #ef4444); color: white; width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; font-weight: 900; margin-right: 15px; flex-shrink: 0; box-shadow: 0 2px 5px rgba(239, 68, 68, 0.5); }
    
    /* 📝 중앙 정보 영역 (종목명, 등락률, 상태) */
    .info-col { flex-grow: 1; display: flex; flex-direction: column; justify-content: center; text-align: left; }
    .name-row { display: flex; align-items: baseline; margin-bottom: 4px; }
    .stock-name { color: white; font-size: 1.9rem; font-weight: 900; margin-right: 8px; letter-spacing: -1px; }
    .current-return { font-size: 1.2rem; font-weight: 800; }
    .status-text { font-size: 1.1rem; font-weight: 800; color: #a1a1aa; }
    
    /* 💰 오른쪽 수익률 영역 */
    .return-col { text-align: right; display: flex; flex-direction: column; justify-content: center; }
    .expected-label { color: #71717a; font-size: 0.95rem; font-weight: 700; margin-bottom: 2px; }
    .expected-value { color: #22c55e; font-size: 1.9rem; font-weight: 900; letter-spacing: -0.5px; }

</style>
""", unsafe_allow_html=True)

KST = timezone(timedelta(hours=9))

@st.cache_resource(ttl=3600*20)
def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(f"{URL_BASE}/oauth2/tokenP", headers=headers, data=json.dumps(body))
        return res.json()["access_token"]
    except: return None

def get_common_headers(tr_id):
    token = get_access_token()
    if not token: token = get_access_token()
    return {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appKey": APP_KEY, "appSecret": APP_SECRET, "tr_id": tr_id}

@st.cache_data(ttl=30)
def get_kis_top_trading_value_stocks():
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/volume-rank"
    headers = get_common_headers("FHPST01710000")
    df_list = []
    for params in [{"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "10000", "FID_INPUT_PRICE_2": "80000", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""},
                   {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "80000", "FID_INPUT_PRICE_2": "2000000", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""}]:
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.json().get('rt_cd') == '0': df_list.append(pd.DataFrame(res.json()['output'])[['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn']])
        except: continue
    if not df_list: return pd.DataFrame()
    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '거래대금']
    df = df[~df['종목명'].str.contains('|'.join(['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '히어로즈', '마이티', '스팩', 'ETN']), case=False, regex=True)]
    df['현재가'], df['등락률'], df['거래대금'] = pd.to_numeric(df['현재가'], errors='coerce'), pd.to_numeric(df['등락률'], errors='coerce'), pd.to_numeric(df['거래대금'], errors='coerce') / 1000000 
    return df.sort_values(by='거래대금', ascending=False).drop_duplicates(subset=['종목코드']).dropna()

# -----------------------------------------------------------------------------
# 🚀 자동 새로고침 타이머 (1분)
# -----------------------------------------------------------------------------
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60000, limit=10000, key="auto_refresh")
except ImportError: pass

# -----------------------------------------------------------------------------
# 📊 데이터 세팅 및 필터링 (사진과 동일한 문구로 매핑)
# -----------------------------------------------------------------------------
df_universe = get_kis_top_trading_value_stocks()
top_10 = pd.DataFrame()

if not df_universe.empty:
    df_universe = df_universe
