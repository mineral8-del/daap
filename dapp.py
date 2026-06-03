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

# 🎨 카드형 디자인 전용 CSS (💡 모든 폰트와 여백을 모바일 맞춤형으로 초대폭 확대!)
st.markdown("""
<style>
    /* 전체 배경을 어둡게 설정 및 여백 최적화 */
    .stApp { background-color: #0f0f13; }
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; max-width: 100%; }
    header[data-testid="stHeader"], #MainMenu, footer { display: none !important; }
    
    /* 🎯 메인 타이틀 (AI 단타 타점 TOP 10) - 엄청 크게! */
    .main-title { color: #ff4b4b; font-size: 3.8rem; font-weight: 900; text-align: center; margin-bottom: 15px; letter-spacing: -2px; }
    
    /* ⚡ 노란색 시간 캡슐 - 더 크고 빵빵하게! */
    .time-container { text-align: center; margin-bottom: 35px; }
    .time-pill { background-color: #eab308; color: #000000; font-size: 2.0rem; font-weight: 900; padding: 10px 35px; border-radius: 50px; display: inline-block; box-shadow: 0 0 20px rgba(234, 179, 8, 0.4); letter-spacing: 1px; }
    
    /* 🃏 카드 전체 레이아웃 - 위아래 간격과 패딩 확대 */
    .stock-card { background-color: #1a1a21; border-radius: 16px; padding: 22px 25px; margin-bottom: 18px; display: flex; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 2px solid #27272a; }
    
    /* 🔴 랭킹 동그라미 뱃지 - 시원하게 확대 */
    .rank-circle { background: linear-gradient(135deg, #f87171, #ef4444); color: white; width: 65px; height: 65px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.4rem; font-weight: 900; margin-right: 20px; flex-shrink: 0; box-shadow: 0 2px 8px rgba(239, 68, 68, 0.6); }
    
    /* 📝 중앙 정보 영역 (종목명, 등락률, 상태) */
    .info-col { flex-grow: 1; display: flex; flex-direction: column; justify-content: center; text-align: left; }
    .name-row { display: flex; align-items: baseline; margin-bottom: 8px; }
    .stock-name { color: white; font-size: 2.8rem; font-weight: 900; margin-right: 12px; letter-spacing: -1.5px; }
    .current-return { font-size: 1.8rem; font-weight: 800; }
    .status-text { font-size: 1.6rem; font-weight: 800; color: #a1a1aa; margin-top: 2px; }
    
    /* 💰 오른쪽 수익률 영역 */
    .return-col { text-align: right; display: flex; flex-direction: column; justify-content: center; }
    .expected-label { color: #71717a; font-size: 1.3rem; font-weight: 700; margin-bottom: 4px; }
    .expected-value { color: #22c55e; font-size: 2.8rem; font-weight: 900; letter-spacing: -1px; }

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
# 📊 데이터 세팅 및 필터링
# -----------------------------------------------------------------------------
df_universe = get_kis_top_trading_value_stocks()
top_10 = pd.DataFrame()

if not df_universe.empty:
    df_universe = df_universe[df_universe['등락률'] > -15.0].copy()
    
    # AI 스코어 계산
    df_universe['10분_상승예측(%)'] = ((df_universe['등락률'] * 0.5) + np.log1p(df_universe['거래대금'])).round(2)
    
    # 상태 텍스트
    df_universe['매매상태'] = df_universe.apply(
        lambda r: "🔥 급등 진행형" if r['등락률'] >= 5.0 
        else ("🎯 S급 눌림목" if r['등락률'] < 0 and r['거래대금'] > 10000 
        else "🟡 지지선 근접"), axis=1
    )
    
    # 기대수익 포맷
    df_universe['기대수익_str'] = df_universe['10분_상승예측(%)'].apply(lambda x: f"+{max(0.1, x):.1f}%")
    
    # 점수 높은 순으로 10개 추출
    top_10 = df_universe.sort_values(by='10분_상승예측(%)', ascending=False).head(10)

# -----------------------------------------------------------------------------
# 🎯 화면 상단 (타이틀 & 노란색 시계 캡슐)
# -----------------------------------------------------------------------------
# 💡 단타로 타이틀 수정!
st.markdown("<div class='main-title'>AI 단타 타점 TOP 10</div>", unsafe_allow_html=True)

# 💡 파이썬 실시간 서버 시간을 직접 주입하여 '0000년' 버그 원천 차단!
current_time_str = datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')

st.markdown(f"""
    <div class='time-container'>
        <div class='time-pill' id="clockDisplay">⚡ {current_time_str} 기준</div>
    </div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 🃏 커스텀 HTML 카드 리스트 그리기 (💡 들여쓰기 금지 구역)
# -----------------------------------------------------------------------------
if not top_10.empty:
    cards_html = ""
    
    for i, (_, row) in enumerate(top_10.iterrows(), start=1):
        curr_ret = row['등락률']
        curr_ret_str = f"{curr_ret:+.2f}%"
        curr_ret_color = "#f87171" if curr_ret > 0 else "#38bdf8" if curr_ret < 0 else "#9ca3af"
        
        # ⚠️ 절대 이 부분의 띄어쓰기를 수정하지 마세요! (스트림릿 코드블록 오류 방지용)
        cards_html += f"""<div class="stock-card">
<div class="rank-circle">{i}</div>
<div class="info-col">
<div class="name-row">
<span class="stock-name">{row['종목명']}</span>
<span class="current-return" style="color: {curr_ret_color};">({curr_ret_str})</span>
</div>
<div class="status-text">{row['매매상태']}</div>
</div>
<div class="return-col">
<div class="expected-label">기대수익</div>
<div class="expected-value">{row['기대수익_str']}</div>
</div>
</div>"""
        
    st.markdown(cards_html, unsafe_allow_html=True)
else:
    st.error("데이터를 수집 중입니다. 장 시작 전이거나 네트워크 상태를 확인해주세요.")
