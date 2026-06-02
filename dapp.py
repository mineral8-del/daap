import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta, timezone, time as dt_time
import FinanceDataReader as fdr
import io
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

# 📺 [초압축 뷰] 레이아웃 와이드
st.set_page_config(layout="wide", page_title="🔴 하이모바일 주식 대시보드", initial_sidebar_state="collapsed")

# 📺 커스텀 CSS (여백 극강 축소 및 컬럼 밀착)
st.markdown("""
<style>
    .block-container { padding-top: 1.0rem !important; padding-bottom: 0rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100%; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    [data-testid="column"] { padding-left: 0.3rem !important; padding-right: 0.3rem !important; }
    
    .main-title { font-size: 1.5rem !important; font-weight: 900 !important; color: #FF4B4B !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); display: inline-block; vertical-align: middle; }
    .company-name { font-size: 1.0rem !important; color: #B0B0B0 !important; font-weight: 700 !important; margin-left: 10px; display: inline-block; vertical-align: middle; }
    
    h3 { font-size: 1.1rem !important; font-weight: 800 !important; color: #FFD700 !important; margin-top: 0px; margin-bottom: 5px; }
    
    /* 메트릭(수치) 폰트 최적화 */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 900 !important; line-height: 1.0 !important; }
    [data-testid="stMetricDelta"] { font-size: 1.0rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { font-size: 0.9rem !important; font-weight: 600 !important; color: #888888; margin-bottom: -5px;}
    
    /* 데이터프레임 압축 */
    .stDataFrame { font-size: 1.0rem !important; }
    div[data-testid="stDataFrame"] table { font-size: 1.0rem !important; font-weight: 600 !important; padding: 0px !important;}
    
    hr { margin-top: 0.5rem; margin-bottom: 0.5rem; border-color: #333333; border-width: 1px; }
</style>
""", unsafe_allow_html=True)

# 🏢 메인 타이틀
st.markdown("""
    <div style='margin-bottom: 5px;'>
        <span class='main-title'>🔴 [LIVE] 스캐너 24H</span>
        <span class='company-name'>| 주식회사 하이모바일</span>
    </div>
""", unsafe_allow_html=True)

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
        if any(keyword in stock_name for keyword in keywords): return theme
    return "▪️ 개별주"

@st.cache_resource(ttl=3600*20)
def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    url = f"{URL_BASE}/oauth2/tokenP"
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
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
            data = res.json()
            if data['rt_cd'] == '0' and 'output' in data: df_list.append(pd.DataFrame(data['output'])[['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn']])
        except: continue
    if not df_list: return pd.DataFrame()
    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '거래대금']
    df = df[~df['종목명'].str.contains('|'.join(['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '히어로즈', '마이티', '스팩', 'ETN']), case=False, regex=True)]
    df['현재가'], df['등락률'], df['거래대금'] = pd.to_numeric(df['현재가'], errors='coerce'), pd.to_numeric(df['등락률'], errors='coerce'), pd.to_numeric(df['거래대금'], errors='coerce') / 1000000 
    return df.sort_values(by='거래대금', ascending=False).drop_duplicates(subset=['종목코드']).dropna()

@st.cache_data(ttl=15)
def get_foreign_investor_trend():
    session, token = requests.Session(), get_access_token()
    if not token: return 0.0
    try:
        res = session.get("https://openapivts.koreainvestment.com:29443/uapi/domestic-future/v1/quotation/inquire-investor-trend", headers={"content-type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHUFT01010000"}, params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": "000"}, timeout=4)
        if res.status_code == 200:
            for data in res.json().get("output1", []):
                if "외국인" in data.get("invst_vo", ""):
                    val = float(data.get("ntby_pamt", 0)) / 100000000
                    if val != 0.0: return round(val, 1)
    except: pass
    return 0.0

@st.cache_data(ttl=60)
def get_market_indices_v2():
    end_date, start_date = datetime.now(KST).strftime('%Y-%m-%d'), (datetime.now(KST) - timedelta(days=20)).strftime('%Y-%m-%d')
    try: ks, kq = fdr.DataReader('KS11', start_date, end_date), fdr.DataReader('KQ11', start_date, end_date) 
    except: ks, kq = pd.DataFrame(), pd.DataFrame()
    try: usd = fdr.DataReader('USD/KRW', start_date, end_date)
    except: usd = pd.DataFrame()
    return ks, kq, usd

def display_index_metric(df, title):
    if df.empty:
        st.metric(title, "N/A", "데이터 없음")
        return
    current_val = df['Close'].iloc[-1]
    prev_val = df['Close'].iloc[-2] if len(df) > 1 else current_val
    delta = current_val - prev_val
    delta_percent = (delta / prev_val) * 100
    st.metric(label=title, value=f"{current_val:,.2f}", delta=f"{delta:+.2f} ({delta_percent:+.2f}%)")

@st.cache_data(ttl=60, show_spinner=False)
def fetch_after_market_data(top30_df):
    if top30_df.empty: return pd.DataFrame(columns=['종목코드', '시간외 현재가', '시간외 등락률', '시간외 거래량', '_sort_ratio_num'])
    url, headers = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", get_common_headers("FHKST01010100") 
    after_market_results = []
    for i, (idx, row) in enumerate(top30_df.iterrows()):
        try:
            res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": row['종목코드']})
            data = res.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                after_price, after_ratio, after_vol = float(data['output'].get('ovtm_untp_prpr', 0)), float(data['output'].get('ovtm_untp_prdy_ctrt', 0)), float(data['output'].get('ovtm_untp_vol', 0))
                after_market_results.append({'종목코드': row['종목코드'], '시간외 현재가': f"{int(after_price):,} 원" if after_price > 0 else "-", '시간외 등락률': f"{after_ratio:+.2f} %" if after_price > 0 else "-", '시간외 거래량': f"{int(after_vol):,}" if after_price > 0 else "-", '_sort_ratio_num': after_ratio})
            time.sleep(0.1) 
        except: after_market_results.append({'종목코드': row['종목코드'], '시간외 현재가': "-", '시간외 등락률': "-", '시간외 거래량': "-", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(after_market_results)
    if df.empty: df = pd.DataFrame(columns=['종목코드', '시간외 현재가', '시간외 등락률', '시간외 거래량', '_sort_ratio_num'])
    return df

@st.cache_data(ttl=60, show_spinner=False)
def fetch_pre_market_data(top30_df):
    if top30_df.empty: return pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 예상 갭상승률', '☀️ 예상 거래량', '_sort_ratio_num'])
    url, headers = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", get_common_headers("FHKST01010100") 
    pre_market_results = []
    for i, (idx, row) in enumerate(top30_df.iterrows()):
        try:
            res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": row['종목코드']})
            data = res.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                def safe_float(val): return float(val) if val not in [None, "", " "] else 0.0
                pre_price, pre_ratio, pre_vol = safe_float(data['output'].get('antc_cnpr', 0)), safe_float(data['output'].get('antc_cntg_prdy_ctrt', 0)), safe_float(data['output'].get('antc_cntg_vol', 0))
                pre_market_results.append({'종목코드': row['종목코드'], '☀️ 예상 체결가': f"{int(pre_price):,} 원" if pre_price > 0 else "대기", '☀️ 예상 갭상승률': f"{pre_ratio:+.2f} %" if pre_price > 0 else "0.00 %", '☀️ 예상 거래량': f"{int(pre_vol):,}" if pre_price > 0 else "0", '_sort_ratio_num': pre_ratio})
            time.sleep(0.2) 
        except: pre_market_results.append({'종목코드': row['종목코드'], '☀️ 예상 체결가': "-", '☀️ 예상 갭상승률': "-", '☀️ 예상 거래량': "-", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(pre_market_results)
    if df.empty: df = pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 예상 갭상승률', '☀️ 예상 거래량', '_sort_ratio_num'])
    return df

# -----------------------------------------------------------------------------
# 🤖 오토 파일럿 시간 판별 로직
# -----------------------------------------------------------------------------
now_time = datetime.now(KST).time()
time_pre_start, time_reg_start, time_after_start, time_after_end = dt_time(8, 30), dt_time(9, 0), dt_time(15, 30), dt_time(18, 0)
default_auto, default_pre, default_after = False, False, True

if time_pre_start <= now_time < time_reg_start: default_auto, default_pre, default_after = True, True, False
elif time_reg_start <= now_time < time_after_start: default_auto, default_pre, default_after = True, False, False
elif time_after_start <= now_time < time_after_end: default_auto, default_pre, default_after = True, False, True

# -----------------------------------------------------------------------------
# [상단 1열] 텍스트 전광판 (지수 3개 + 수급 2개 = 5분할)
# -----------------------------------------------------------------------------
st.markdown("<hr style='margin-top: 0; margin-bottom: 5px;'>", unsafe_allow_html=True)
ks_df, kq_df, usd_df = get_market_indices_v2()
if 'foreign_futures_net' not in st.session_state: st.session_state.foreign_futures_net = get_foreign_investor_trend()
ff_net = st.session_state.foreign_futures_net

c1, c2, c3, c4, c5 = st.columns(5)
with c1: display_index_metric(ks_df, "KOSPI")
with c2: display_index_metric(kq_df, "KOSDAQ")
with c3: display_index_metric(usd_df, "USD/KRW")
with c4:
    if ff_net > 0: st.metric("외인 선물 순매수", f"+{ff_net:,} 억", "매수 우위", delta_color="normal")
    elif ff_net < 0: st.metric("외인 선물 순매수", f"{ff_net:,} 억", "매도 우위", delta_color="inverse")
    else: st.metric("외인 선물 순매수", "0.0 억", "대기 중", delta_color="off")
with c5:
    score = min(100, max(0, int(50 + (ff_net / 10))))
    st.metric("시장 매력도", f"{score} 점", "탄력도", delta_color="normal" if ff_net > 0 else "inverse" if ff_net < 0 else "off")

# -----------------------------------------------------------------------------
# [상단 2열] 스위치 컨트롤 및 제목
# -----------------------------------------------------------------------------
st.markdown("<hr style='margin-top: 10px; margin-bottom: 10px;'>", unsafe_allow_html=True)

sc1, sc2, sc3, _ = st.columns([1.5, 1.5, 1.5, 5.5])
with sc1: auto_refresh = st.toggle("⏱️ 1분 갱신", value=default_auto)
with sc2: pre_market_mode = st.toggle("☀️ 동시호가 모드", value=default_pre)
with sc3: after_market_mode = st.toggle("🌙 시간외 모드", value=default_after)

if auto_refresh:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=60000, limit=10000, key="auto_scanner_refresh")
    except ImportError: pass

# -----------------------------------------------------------------------------
# 📊 와이드 스캐너 테이블 (화면 꽉 채우기)
# -----------------------------------------------------------------------------
if pre_market_mode: st.markdown("<h3>🎯 장전 예상 갭상승 타겟 Top 30</h3>", unsafe_allow_html=True)
elif after_market_mode: st.markdown("<h3>🌙 시간외 단일가 수급 타겟 Top 30</h3>", unsafe_allow_html=True)
else: st.markdown("<h3>📈 실시간 돌파/눌림목 타겟 Top 30 (AI 예측 랭킹)</h3>", unsafe_allow_html=True)

df_universe = get_kis_top_trading_value_stocks()

if not df_universe.empty:
    filtered_df = df_universe[df_universe['등락률'] > -2.0].copy()
    X_live = filtered_df[['등락률', '거래대금', '현재가']].fillna(0)
    filtered_df['10분_상승예측(%)'] = ((filtered_df['등락률'] * 0.5) + np.log1p(filtered_df['거래대금'])).round(2)
    filtered_df['테마'] = filtered_df['종목명'].apply(get_theme_icon)
    
    def detect_signal(row):
        if row['등락률'] >= 7.0 and row['거래대금'] > 50000: return "🔥 돌파매매"
        elif 1.0 <= row['등락률'] < 5.0 and row['거래대금'] > 20000: return "💧 눌림목"
        return "▪️ 관망"
    filtered_df['매매상태'] = filtered_df.apply(detect_signal, axis=1)
    
    top_30 = filtered_df.sort_values(by='10분_상승예측(%)', ascending=False).head(30)
    
    if pre_market_mode:
        extra_df = fetch_pre_market_data(top_30)
        top_30 = pd.merge(top_30, extra_df, on='종목코드', how='left').sort_values(by='_sort_ratio_num', ascending=False)
    elif after_market_mode:
        extra_df = fetch_after_market_data(top_30)
        top_30 = pd.merge(top_30, extra_df, on='종목코드', how='left').sort_values(by='_sort_ratio_num', ascending=False)

    output_dict = {
        '섹터/테마': top_30['테마'], 
        '매매상태': top_30['매매상태'], 
        '종목명': top_30['종목명'],
        '현재가 (원)': top_30['현재가'].apply(lambda x: f"{int(x):,} 원"),
        '상승률 (%)': top_30['등락률'].apply(lambda x: f"{x:+.2f} %"),
        '누적 거래대금 (백만원)': top_30['거래대금'].apply(lambda x: f"{int(x):,}")
    }
    
    if pre_market_mode:
        output_dict['☀️ 예상 갭상승률'] = top_30['☀️ 예상 갭상승률']
        output_dict['☀️ 예상 체결가'] = top_30['☀️ 예상 체결가']
    elif after_market_mode:
        output_dict['🌙 시간외 등락률'] = top_30['시간외 등락률']
        output_dict['🌙 시간외 현재가'] = top_30['시간외 현재가']
        
    output_df = pd.DataFrame(output_dict).reset_index(drop=True)
    
    # 테이블이 빈 공간을 완벽히 메우도록 높이 설정
    st.dataframe(output_df, use_container_width=True, height=800, hide_index=True)
else:
    st.error("데이터 로드 중입니다...")
