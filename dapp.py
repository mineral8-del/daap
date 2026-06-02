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

# 📺 [방송용] 커스텀 CSS 디자인 주입 (여백 제거, 다크 모드 최적화)
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; max-width: 100%; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    h1 { font-size: 2.5rem !important; font-weight: 900 !important; color: #FF4B4B !important; text-align: center; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); margin-bottom: 0px; }
    h2, h3 { font-size: 1.8rem !important; font-weight: 800 !important; color: #FFD700 !important; margin-top: 10px; }
    [data-testid="stMetricValue"] { font-size: 3rem !important; font-weight: 900 !important; line-height: 1.2 !important; }
    [data-testid="stMetricDelta"] { font-size: 1.5rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { font-size: 1.2rem !important; font-weight: 600 !important; color: #888888; }
    .stDataFrame { font-size: 1.2rem !important; }
    div[data-testid="stDataFrame"] table { font-size: 1.1rem !important; font-weight: 600 !important; }
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

@st.cache_resource(ttl=3600*20)
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
                df_temp = pd.DataFrame(data['output'])[['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn']]
                df_list.append(df_temp)
        except: continue
            
    if not df_list: return pd.DataFrame()
        
    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '거래대금']
    
    exclude_keywords = ['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '히어로즈', '마이티', '스팩', 'ETN']
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
        headers_fut = {"content-type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHUFT01010000"}
        res = session.get(url_fut, headers=headers_fut, params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": "000"}, timeout=4)
        if res.status_code == 200:
            for data in res.json().get("output1", []):
                if "외국인" in data.get("invst_vo", ""):
                    val = float(data.get("ntby_pamt", 0)) / 100000000
                    if val != 0.0: return round(val, 1)
    except: pass
    return -250.0

@st.cache_data(ttl=60)
def get_market_indices_v2():
    end_date = datetime.now(KST).strftime('%Y-%m-%d')
    start_date = (datetime.now(KST) - timedelta(days=20)).strftime('%Y-%m-%d')
    try: ks, kq = fdr.DataReader('KS11', start_date, end_date), fdr.DataReader('KQ11', start_date, end_date) 
    except: ks, kq = pd.DataFrame(), pd.DataFrame()
    try: usd = fdr.DataReader('USD/KRW', start_date, end_date)
    except: usd = pd.DataFrame()
    return ks, kq, usd

# 📺 [방송용] 다크 모드 차트 적용
def create_pro_chart(df, title, color_hex):
    if df.empty: return go.Figure().update_layout(title="데이터 로드 실패")
    current_val = df['Close'].iloc[-1]
    prev_val = df['Close'].iloc[-2] if len(df) > 1 else df['Close'].iloc[-1]
    delta = current_val - prev_val
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color=color_hex, width=4), fill='tozeroy', fillcolor=f"rgba({int(color_hex[1:3],16)}, {int(color_hex[3:5],16)}, {int(color_hex[5:7],16)}, 0.2)", name=title))
    fig.update_layout(title=dict(text=f"<b>{title}</b> <span style='font-size:18px; color:{'#ff4b4b' if delta >=0 else '#0068c9'}'>{current_val:,.2f} ({(delta / prev_val) * 100:+.2f}%)</span>", x=0.05, y=0.85), height=250, margin=dict(l=10, r=10, t=50, b=10), template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', side='right'), hovermode="x unified")
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
        except: after_market_results.append({'종목코드': code, '시간외 현재가': "-", '시간외 등락률': "-", '시간외 거래량': "-", '_sort_ratio_num': 0.0})
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
                    try: return float(val)
                    except: return 0.0
                pre_price = safe_float(out.get('antc_cnpr', 0))
                pre_ratio = safe_float(out.get('antc_cntg_prdy_ctrt', 0))
                pre_vol = safe_float(out.get('antc_cntg_vol', 0))
                
                pre_market_results.append({
                    '종목코드': code, '☀️ 예상 체결가': f"{int(pre_price):,} 원" if pre_price > 0 else "데이터 없음",
                    '☀️ 예상 갭상승률': f"{pre_ratio:+.2f} %" if pre_price > 0 else "0.00 %",
                    '☀️ 예상 거래량': f"{int(pre_vol):,}" if pre_price > 0 else "0", '_sort_ratio_num': pre_ratio
                })
            time.sleep(0.2) 
        except: pre_market_results.append({'종목코드': code, '☀️ 예상 체결가': "에러", '☀️ 예상 갭상승률': "에러", '☀️ 예상 거래량': "에러", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(pre_market_results)
    if df.empty: df = pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 예상 갭상승률', '☀️ 예상 거래량', '_sort_ratio_num'])
    return df

# -----------------------------------------------------------------------------
# 1. 상단 글로벌 지수 렌더링
# -----------------------------------------------------------------------------
st.subheader("🌐 글로벌 시장 및 주요 지수 실시간 모니터링")
ks_df, kq_df, usd_df = get_market_indices_v2()

col1, col2, col3 = st.columns(3)
with col1: st.plotly_chart(create_pro_chart(ks_df, "KOSPI", "#FF4B4B"), use_container_width=True)
with col2: st.plotly_chart(create_pro_chart(kq_df, "KOSDAQ", "#00CC96"), use_container_width=True)
with col3: st.plotly_chart(create_pro_chart(usd_df, "USD/KRW", "#636EFA"), use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 2. 외국인 수급 렌더링
# -----------------------------------------------------------------------------
if 'foreign_futures_net' not in st.session_state: st.session_state.foreign_futures_net = get_foreign_investor_trend()
foreign_futures_net = st.session_state.foreign_futures_net

if foreign_futures_net > 0:
    value_str, program_intensity, trade_signal, delta_msg, score_color = f"+{foreign_futures_net:,} 억 원", min(100, int(50 + (foreign_futures_net / 10))), "🚀 외인 매수 우위 (상승장)", "매수 우위", "normal"
elif foreign_futures_net < 0:
    value_str, program_intensity, trade_signal, delta_msg, score_color = f"{foreign_futures_net:,} 억 원", max(0, int(50 - (abs(foreign_futures_net) / 10))), "⚠️ 외인 매도 우위 (하락장)", "매도 우위", "inverse"
else:
    value_str, program_intensity, trade_signal, delta_msg, score_color = "0.0 억 원", 50, "⏸️ 수급 데이터 대기 중", "데이터 없음", "off"

m_col1, m_col2 = st.columns(2)
m_col1.metric(label="📊 외국인 주식선물 순매수 금액", value=value_str, delta=delta_msg, delta_color=score_color)
m_col2.metric(label="🔥 시장 전체 매력도 (100점 만점)", value=f"{program_intensity} 점", delta=trade_signal, delta_color=score_color)

st.markdown("---")

# -----------------------------------------------------------------------------
# 3. 🤖 오토 파일럿 및 메인 스캐너 테이블 렌더링
# -----------------------------------------------------------------------------
now_time = datetime.now(KST).time()
time_pre_start, time_reg_start, time_after_start, time_after_end = dt_time(8, 30), dt_time(9, 0), dt_time(15, 30), dt_time(18, 0)
default_auto, default_pre, default_after = False, False, True

if time_pre_start <= now_time < time_reg_start: default_auto, default_pre, default_after = True, True, False
elif time_reg_start <= now_time < time_after_start: default_auto, default_pre, default_after = True, False, False
elif time_after_start <= now_time < time_after_end: default_auto, default_pre, default_after = True, False, True

t_col1, t_col2, t_col3 = st.columns(3)
with t_col1: auto_refresh = st.toggle("⏱️ 1분 자동 갱신 (방송 ON)", value=default_auto)
with t_col2: pre_market_mode = st.toggle("☀️ 동시호가 모드", value=default_pre)
with t_col3: after_market_mode = st.toggle("🌙 시간외 모드", value=default_after)

if auto_refresh:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=60000, limit=10000, key="auto_scanner_refresh")
    except ImportError: pass

if pre_market_mode: st.markdown("<h3>🎯 오늘 아침 시초가 갭상승 예상 타겟 Top 30</h3>", unsafe_allow_html=True)
elif after_market_mode: st.markdown("<h3>🌙 시간외 단일가 수급 및 내일 시초가 타겟 Top 30</h3>", unsafe_allow_html=True)
else: st.markdown("<h3>📈 실시간 단타 돌파/눌림목 타겟 Top 30 (AI 랭킹)</h3>", unsafe_allow_html=True)

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
        '섹터': top_30['테마'], '상태': top_30['매매상태'],
        '종목명': top_30['종목명'],
        '현재가': top_30['현재가'].apply(lambda x: f"{int(x):,} 원"),
        '상승률': top_30['등락률'].apply(lambda x: f"{x:+.2f} %"),
        '거래대금(백만)': top_30['거래대금'].apply(lambda x: f"{int(x):,}")
    }
    
    if pre_market_mode:
        output_dict['☀️ 갭상승 예상'] = top_30['☀️ 예상 갭상승률']
        output_dict['☀️ 예상 체결가'] = top_30['☀️ 예상 체결가']
    elif after_market_mode:
        output_dict['🌙 시간외 등락률'] = top_30['시간외 등락률']
        output_dict['🌙 시간외 가격'] = top_30['시간외 현재가']
        
    output_df = pd.DataFrame(output_dict).reset_index(drop=True)
    
    # 방송 시청자들이 보기 좋게 데이터프레임 전체 넓이 사용
    selected_rows = st.dataframe(output_df, use_container_width=True, height=500, selection_mode="single-row", on_select="rerun")
else:
    st.error("데이터 로드 중입니다...")
    output_df = pd.DataFrame()

# -----------------------------------------------------------------------------
# 4. 📺 방송용 하단 실시간 1분봉 차트 (다크 테마 적용)
# -----------------------------------------------------------------------------
st.markdown("---")
selected_idx = selected_rows.selection.rows[0] if (hasattr(selected_rows, 'selection') and len(selected_rows.selection.rows) > 0) else 0

if not output_df.empty and selected_idx < len(output_df):
    target_code = top_30.iloc[selected_idx]['종목코드']
    target_name = output_df.iloc[selected_idx]['종목명']
    
    st.markdown(f"<h3>🔍 [{target_name}] 실시간 1분봉 AI 정밀 분석</h3>", unsafe_allow_html=True)
    
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    headers = get_common_headers("FHKST03010200")
    params = {"FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": target_code, "FID_INPUT_HOUR_1": datetime.now(KST).strftime("%H%M%S"), "FID_PW_DATA_INCU_YN": "Y"}
    try:
        res = requests.get(url, headers=headers, params=params)
        res_data = res.json()
        if res_data['rt_cd'] == '0' and 'output2' in res_data:
            min_data = res_data['output2'][::-1] 
            df_min = pd.DataFrame({"Open": [float(m['stck_oprc']) for m in min_data], "High": [float(m['stck_hgpr']) for m in min_data], "Low": [float(m['stck_lwpr']) for m in min_data], "Close": [float(m['stck_prpr']) for m in min_data], "Volume": [float(m['cntg_vol']) for m in min_data]}, index=pd.to_datetime([f"{m['stck_bsop_date']} {m['stck_cntg_hour']}" for m in min_data], format="%Y%m%d %H%M%S"))
            df_min = df_min[df_min['Close'] > 0]
            
            if not df_min.empty:
                df_min['MA5'], df_min['MA20'] = df_min['Close'].rolling(5).mean(), df_min['Close'].rolling(20).mean()
                df_min['Diff'] = df_min['Close'].diff().fillna(0)
                min_price, max_price = df_min['Low'].min(), df_min['High'].max()
                price_margin = (max_price - min_price) * 0.1 if max_price != min_price else min_price * 0.01
                
                # 📺 방송용 1분봉 다크 차트
                fig_stock = go.Figure()
                fig_stock.add_trace(go.Candlestick(x=df_min.index, open=df_min['Open'], high=df_min['High'], low=df_min['Low'], close=df_min['Close'], increasing_line_color='#FF4B4B', decreasing_line_color='#0068C9', name="주가"))
                fig_stock.add_trace(go.Scatter(x=df_min.index, y=df_min['MA5'], mode='lines', line=dict(color='#FFD700', width=2), name="5분선", hoverinfo='skip'))
                fig_stock.add_trace(go.Scatter(x=df_min.index, y=df_min['MA20'], mode='lines', line=dict(color='#00FA9A', width=2), name="20분선", hoverinfo='skip'))
                fig_stock.add_trace(go.Bar(x=df_min.index, y=df_min['Volume'], name="거래량", marker_color=['#FF4B4B' if d >= 0 else '#0068C9' for d in df_min['Diff']], opacity=0.7, yaxis='y2'))
                
                fig_stock.update_layout(
                    template="plotly_dark", height=500, margin=dict(l=10, r=40, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=True, gridcolor='#333333', type='date', tickformat='%H:%M', rangeslider=dict(visible=False)), 
                    yaxis=dict(side='right', showgrid=True, gridcolor='#333333', tickformat=',', range=[min_price - price_margin, max_price + price_margin], domain=[0.3, 1]), 
                    yaxis2=dict(side='right', showgrid=False, tickformat=',', domain=[0, 0.2]), 
                    hovermode='x unified', showlegend=False
                )
                st.plotly_chart(fig_stock, use_container_width=True)
    except: pass
