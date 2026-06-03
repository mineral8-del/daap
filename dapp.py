import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime, timedelta, timezone
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# -----------------------------------------------------------------------------
# 📱 [쇼츠용 세로 뷰] 레이아웃 설정
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="🔴 하이모바일 쇼츠 LIVE", initial_sidebar_state="collapsed")

# -----------------------------------------------------------------------------
# [설정] 한국투자증권 API KEY
# -----------------------------------------------------------------------------
APP_KEY = os.environ.get("APP_KEY") or os.environ.get("KIS_APP_KEY")
APP_SECRET = os.environ.get("APP_SECRET") or os.environ.get("KIS_APP_SECRET")

# Streamlit Cloud Secret 지원 (os.environ에 없을 경우 st.secrets에서 찾기)
if not APP_KEY or not APP_SECRET:
    try:
        APP_KEY = st.secrets.get("APP_KEY") or st.secrets.get("KIS_APP_KEY")
        APP_SECRET = st.secrets.get("APP_SECRET") or st.secrets.get("KIS_APP_SECRET")
    except:
        pass

if not APP_KEY or not APP_SECRET:
    st.error("⚠️ 앱키(APP_KEY) 또는 시크릿키(APP_SECRET)가 설정되지 않았습니다.")
    st.stop()

URL_BASE = "https://openapi.koreainvestment.com:9443" 
KST = timezone(timedelta(hours=9))

# -----------------------------------------------------------------------------
# 🎨 쇼츠용 초거대 텍스트 CSS 최적화
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0f0f13; }
    .block-container { padding: 0px 5px !important; margin-top: 0px !important; max-width: 100% !important; }
    header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"] { display: none !important; }
    .main-title { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; text-align: center; margin-top: 5px; margin-bottom: 5px; letter-spacing: -2px; }
    .time-container { text-align: center; margin-bottom: 15px; }
    .time-pill { background-color: #eab308; color: #000000; font-size: 2.0rem; font-weight: 900; padding: 8px 30px; border-radius: 50px; display: inline-block; box-shadow: 0 0 20px rgba(234, 179, 8, 0.5); }
    .stock-card { background-color: #1a1a21; border-radius: 15px; padding: 15px 8px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 10px rgba(0,0,0,0.5); border: 2px solid #27272a; }
    .rank-circle { background: linear-gradient(135deg, #f87171, #ef4444); color: white; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.6rem; font-weight: 900; margin-right: 10px; flex-shrink: 0; }
    .name-col { width: 38%; display: flex; flex-direction: column; text-align: left; }
    .stock-name { color: white; font-size: 2.6rem; font-weight: 900; letter-spacing: -2px; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.1; }
    .status-text { font-size: 1.6rem; font-weight: 800; color: #a1a1aa; margin-top: 5px; }
    .center-col { width: 32%; display: flex; flex-direction: column; align-items: flex-end; text-align: right; padding-right: 10px; }
    .current-price { font-size: 1.8rem; font-weight: 800; color: #ffffff; letter-spacing: -1px; margin: 0; line-height: 1.1; }
    .center-return { font-size: 2.8rem; font-weight: 900; letter-spacing: -2px; margin-top: 5px; line-height: 1.1; }
    .right-col { width: 30%; text-align: center; display: flex; flex-direction: column; justify-content: center; background: rgba(34, 197, 94, 0.1); padding: 12px 5px; border-radius: 12px; }
    .expected-label { color: #22c55e; font-size: 1.4rem; font-weight: 900; margin-bottom: 2px; letter-spacing: -1px; }
    .expected-value { color: #22c55e; font-size: 3.0rem; font-weight: 900; letter-spacing: -2px; line-height: 1.1; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 📡 1. 인증 및 공통 헤더 (NameError 방지)
# -----------------------------------------------------------------------------
@st.cache_resource(ttl=3600*20)
def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(f"{URL_BASE}/oauth2/tokenP", headers=headers, data=json.dumps(body))
        res.raise_for_status()
        return res.json()["access_token"]
    except Exception as e:
        st.error("API 토큰 발급 실패. 네트워크를 확인하세요.")
        st.stop()

def get_common_headers(tr_id):
    token = get_access_token()
    return {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appKey": APP_KEY, "appSecret": APP_SECRET, "tr_id": tr_id}

# -----------------------------------------------------------------------------
# 📡 2. 거래량 순위 수집 (고가 추출 에러 수정 완료)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=30)
def get_kis_top_trading_value_stocks():
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/volume-rank"
    headers = get_common_headers("FHPST01710000")
    df_list = []
    
    for params in [
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "10000", "FID_INPUT_PRICE_2": "80000", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""},
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "80000", "FID_INPUT_PRICE_2": "2000000", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""}
    ]:
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.json().get('rt_cd') == '0':
                df_list.append(pd.DataFrame(res.json()['output'])[['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn']])
        except: continue
        
    if not df_list: return pd.DataFrame()
    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '누적거래대금']
    
    # 노이즈 필터링
    df = df[~df['종목명'].str.contains('|'.join(['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '히어로즈', '마이티', '스팩', 'ETN']), case=False, regex=True)]
    
    df['현재가'] = pd.to_numeric(df['현재가'], errors='coerce')
    df['등락률'] = pd.to_numeric(df['등락률'], errors='coerce')
    df['누적거래대금'] = pd.to_numeric(df['누적거래대금'], errors='coerce') / 1000000 
    
    return df.drop_duplicates(subset=['종목코드']).dropna()

# -----------------------------------------------------------------------------
# 🚀 3. 자동 새로고침 타이머 (1분)
# -----------------------------------------------------------------------------
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60000, limit=10000, key="auto_refresh")
except ImportError: pass

# -----------------------------------------------------------------------------
# 🧠 4. 세션 상태 초기화 및 데이터 세팅 (2단계 필터링)
# -----------------------------------------------------------------------------
if 'prev_volume_dict' not in st.session_state:
    st.session_state.prev_volume_dict = {}

df_universe = get_kis_top_trading_value_stocks()
top_10 = pd.DataFrame()

if not df_universe.empty:
    df_universe = df_universe[df_universe['등락률'] > -5.0].copy()
    
    # [핵심 1] 1분 순간 수급 계산
    df_universe['1분_거래대금'] = df_universe.apply(
        lambda row: row['누적거래대금'] - st.session_state.prev_volume_dict.get(row['종목코드'], row['누적거래대금']), axis=1
    )
    
    # 상태 업데이트
    st.session_state.prev_volume_dict = dict(zip(df_universe['종목코드'], df_universe['누적거래대금']))
    df_universe['1분_거래대금'] = np.where(
    df_universe['1분_거래대금'] == 0, 
    df_universe['누적거래대금'] * 0.01, 
    df_universe['1분_거래대금']
)
    W_MOMENTUM = 0.4
    W_VOLUME = 0.8
    W_RISK = 0.5

    # 1차 점수 계산
    df_universe['1차_스코어'] = (df_universe['등락률'] * W_MOMENTUM) + (np.log1p(df_universe['1분_거래대금']) * W_VOLUME)
    top_20 = df_universe.sort_values(by='1차_스코어', ascending=False).head(20).copy()

    # [핵심 2] 현재가 API 호출로 윗꼬리 방어 로직 적용
    high_prices = []
    price_headers = get_common_headers("FHKST01010100")
    price_url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price"
    
    for code in top_20['종목코드']:
        try:
            res = requests.get(price_url, headers=price_headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
            high_price = float(res.json()['output']['stck_hgpr'])
            high_prices.append(high_price)
        except:
            high_prices.append(top_20.loc[top_20['종목코드'] == code, '현재가'].values[0])
            
    top_20['고가'] = high_prices
    top_20['윗꼬리(%)'] = ((top_20['고가'] - top_20['현재가']) / top_20['고가'] * 100).clip(lower=0)
    top_20['AI_스코어'] = (top_20['1차_스코어'] - (top_20['윗꼬리(%)'] * W_RISK)).round(2)
    
    top_20['매매상태'] = top_20.apply(
        lambda r: "🚀 수급 폭발형" if r['1분_거래대금'] > 5000 and r['윗꼬리(%)'] < 3.0
        else ("🎯 S급 눌림목" if r['등락률'] < 0 and r['누적거래대금'] > 10000 
        else "🔥 상승 추세형"), axis=1
    )
    
    top_20['기대수익_str'] = top_20['AI_스코어'].apply(lambda x: f"+{max(0.1, x):.1f}%")
    top_20['현재가_str'] = top_20['현재가'].apply(lambda x: f"{int(x):,}원") 
    
    top_10 = top_20.sort_values(by='AI_스코어', ascending=False).head(10)

# -----------------------------------------------------------------------------
# 🎯 5. 화면 렌더링
# -----------------------------------------------------------------------------
st.markdown("<div class='main-title'>AI 단타 타점 TOP 10</div>", unsafe_allow_html=True)

current_time_str = datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')
st.markdown(f"""
    <div class='time-container'>
        <div class='time-pill'>⚡ {current_time_str} 기준</div>
    </div>
""", unsafe_allow_html=True)

if not top_10.empty:
    cards_html = ""
    for i, (_, row) in enumerate(top_10.iterrows(), start=1):
        curr_ret = row['등락률']
        curr_ret_str = f"{curr_ret:+.2f}%"
        curr_ret_color = "#f87171" if curr_ret > 0 else "#38bdf8" if curr_ret < 0 else "#9ca3af"
        
        cards_html += f"""<div class="stock-card">
<div class="rank-circle">{i}</div>
<div class="name-col">
<div class="stock-name">{row['종목명']}</div>
<div class="status-text">{row['매매상태']}</div>
</div>
<div class="center-col">
<div class="current-price">{row['현재가_str']}</div>
<div class="center-return" style="color: {curr_ret_color};">{curr_ret_str}</div>
</div>
<div class="right-col">
<div class="expected-label">기대수익</div>
<div class="expected-value">{row['기대수익_str']}</div>
</div>
</div>"""
        
    st.markdown(cards_html, unsafe_allow_html=True)
else:
    st.error("데이터를 수집 중입니다. (장을 마감했거나 첫 로딩 중입니다)")
