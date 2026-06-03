import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 📱 [쇼츠용 세로 뷰] 레이아웃 설정 (반드시 가장 상단에 위치)
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="🔴 하이모바일 쇼츠 LIVE", initial_sidebar_state="collapsed")

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
KST = timezone(timedelta(hours=9))

# -----------------------------------------------------------------------------
# 🎨 쇼츠용 초거대 텍스트 CSS 최적화
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* 상단 여백 및 불필요한 Streamlit UI 완벽 제거 */
    .stApp { background-color: #0f0f13; }
    .block-container { 
        padding-top: 0rem !important; 
        padding-bottom: 0rem !important; 
        padding-left: 5px !important; 
        padding-right: 5px !important; 
        margin-top: 0px !important; 
        max-width: 100% !important; 
    }
    header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"] { display: none !important; }

    /* 메인 타이틀 */
    .main-title { color: #ff4b4b; font-size: 3.5rem; font-weight: 900; text-align: center; margin-top: 5px; margin-bottom: 5px; letter-spacing: -2px; }

    /* 노란색 시간 캡슐 */
    .time-container { text-align: center; margin-bottom: 15px; }
    .time-pill { background-color: #eab308; color: #000000; font-size: 2.0rem; font-weight: 900; padding: 8px 30px; border-radius: 50px; display: inline-block; box-shadow: 0 0 20px rgba(234, 179, 8, 0.5); }

    /* 카드 전체 레이아웃 */
    .stock-card { background-color: #1a1a21; border-radius: 15px; padding: 15px 8px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 10px rgba(0,0,0,0.5); border: 2px solid #27272a; }

    /* 랭킹 동그라미 뱃지 */
    .rank-circle { background: linear-gradient(135deg, #f87171, #ef4444); color: white; width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2.6rem; font-weight: 900; margin-right: 10px; flex-shrink: 0; }

    /* 왼쪽: 종목명 & 상태 */
    .name-col { width: 38%; display: flex; flex-direction: column; text-align: left; }
    .stock-name { color: white; font-size: 2.6rem; font-weight: 900; letter-spacing: -2px; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.1; }
    .status-text { font-size: 1.6rem; font-weight: 800; color: #a1a1aa; margin-top: 5px; }

    /* 중앙: 현재가 & 상승률 */
    .center-col { width: 32%; display: flex; flex-direction: column; align-items: flex-end; text-align: right; padding-right: 10px; }
    .current-price { font-size: 1.8rem; font-weight: 800; color: #ffffff; letter-spacing: -1px; margin: 0; line-height: 1.1; }
    .center-return { font-size: 2.8rem; font-weight: 900; letter-spacing: -2px; margin-top: 5px; line-height: 1.1; }

    /* 오른쪽: 기대수익률 */
    .right-col { width: 30%; text-align: center; display: flex; flex-direction: column; justify-content: center; background: rgba(34, 197, 94, 0.1); padding: 12px 5px; border-radius: 12px; }
    .expected-label { color: #22c55e; font-size: 1.4rem; font-weight: 900; margin-bottom: 2px; letter-spacing: -1px; }
    .expected-value { color: #22c55e; font-size: 3.0rem; font-weight: 900; letter-spacing: -2px; line-height: 1.1; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 📡 데이터 수집 및 상태 관리 함수
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

@st.cache_data(ttl=30)
def get_kis_top_trading_value_stocks():
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/volume-rank"
    headers = get_common_headers("FHPST01710000")
    df_list = []
    
    # 1만원~8만원 / 8만원~200만원 두 번 호출
    for params in [
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "10000", "FID_INPUT_PRICE_2": "80000", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""},
        {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "80000", "FID_INPUT_PRICE_2": "2000000", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""}
    ]:
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.json().get('rt_cd') == '0':
                # 💡 'stck_hgpr'(고가) 추가 추출
                df_list.append(pd.DataFrame(res.json()['output'])[['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn', 'stck_hgpr']])
        except: continue
        
    if not df_list: return pd.DataFrame()
    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '누적거래대금', '고가']
    
    # 노이즈 필터링
    df = df[~df['종목명'].str.contains('|'.join(['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '히어로즈', '마이티', '스팩', 'ETN']), case=False, regex=True)]
    
    df['현재가'] = pd.to_numeric(df['현재가'], errors='coerce')
    df['등락률'] = pd.to_numeric(df['등락률'], errors='coerce')
    df['고가'] = pd.to_numeric(df['고가'], errors='coerce')
    df['누적거래대금'] = pd.to_numeric(df['누적거래대금'], errors='coerce') / 1000000 # 백만 단위
    
    return df.drop_duplicates(subset=['종목코드']).dropna()

# -----------------------------------------------------------------------------
# 🚀 자동 새로고침 타이머 (1분)
# -----------------------------------------------------------------------------
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60000, limit=10000, key="auto_refresh")
except ImportError: pass

# -----------------------------------------------------------------------------
# 🧠 1분 수급 트래킹을 위한 세션 상태 초기화
# -----------------------------------------------------------------------------
if 'prev_volume_dict' not in st.session_state:
    st.session_state.prev_volume_dict = {}

# -----------------------------------------------------------------------------
# 📊 알고리즘 고도화 데이터 세팅
# -----------------------------------------------------------------------------
df_universe = get_kis_top_trading_value_stocks()
top_10 = pd.DataFrame()

if not df_universe.empty:
    df_universe = df_universe[df_universe['등락률'] > -5.0].copy() # 폭락주 제외
    
    # 💡 [핵심 1] 1분 순간 수급 폭발력 계산 (현재 누적대금 - 1분전 누적대금)
    df_universe['1분_거래대금'] = df_universe.apply(
        lambda row: row['누적거래대금'] - st.session_state.prev_volume_dict.get(row['종목코드'], row['누적거래대금']), axis=1
    )
    
    # 다음 1분 뒤 계산을 위해 현재 누적거래대금 저장
    st.session_state.prev_volume_dict = dict(zip(df_universe['종목코드'], df_universe['누적거래대금']))
    
    # 처음 실행 시(변화량 0)엔 누적거래대금의 일부로 대체하여 에러 방지
    df_universe['1분_거래대금'] = df_universe['1분_거래대금'].replace(0, df_universe['누적거래대금'] * 0.01)

    # 💡 [핵심 2] 윗꼬리 리스크 감점 계산 (고가 대비 얼마나 밀렸는가?)
    # 예: 고가 10000원, 현재가 9000원이면 윗꼬리는 10%
    df_universe['윗꼬리(%)'] = ((df_universe['고가'] - df_universe['현재가']) / df_universe['고가'] * 100).clip(lower=0)

    # 💡 [핵심 3] 다중 팩터 기대수익 점수 알고리즘 (가중치 조절 가능)
    W_MOMENTUM = 0.4 # 등락률 가중치
    W_VOLUME = 0.8   # 순간 거래대금 가중치 (단타이므로 수급을 가장 중요하게 세팅)
    W_RISK = 0.5     # 윗꼬리 감점 가중치

    df_universe['AI_스코어'] = (
        (df_universe['등락률'] * W_MOMENTUM) 
        + (np.log1p(df_universe['1분_거래대금']) * W_VOLUME) 
        - (df_universe['윗꼬리(%)'] * W_RISK)
    ).round(2)
    
    # 상태 텍스트
    df_universe['매매상태'] = df_universe.apply(
        lambda r: "🚀 수급 폭발형" if r['1분_거래대금'] > 5000 and r['윗꼬리(%)'] < 3.0
        else ("🎯 S급 눌림목" if r['등락률'] < 0 and r['누적거래대금'] > 10000 
        else "🔥 상승 추세형"), axis=1
    )
    
    # 표시용 포맷 (음수 방지 및 소수점 1자리)
    df_universe['기대수익_str'] = df_universe['AI_스코어'].apply(lambda x: f"+{max(0.1, x):.1f}%")
    df_universe['현재가_str'] = df_universe['현재가'].apply(lambda x: f"{int(x):,}원") 
    
    # 점수 높은 순으로 10개 추출
    top_10 = df_universe.sort_values(by='AI_스코어', ascending=False).head(10)

# -----------------------------------------------------------------------------
# 🎯 화면 상단 (타이틀 & 노란색 시계 캡슐)
# -----------------------------------------------------------------------------
st.markdown("<div class='main-title'>AI 단타 타점 TOP 10</div>", unsafe_allow_html=True)

current_time_str = datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')
st.markdown(f"""
    <div class='time-container'>
        <div class='time-pill'>⚡ {current_time_str} 기준</div>
    </div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 🃏 커스텀 HTML 카드 리스트 그리기
# -----------------------------------------------------------------------------
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
