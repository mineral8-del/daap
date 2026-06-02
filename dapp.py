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

# 📺 [초압축 와이드 뷰] 레이아웃 설정
st.set_page_config(layout="wide", page_title="🔴 하이모바일 주식 대시보드 LIVE", initial_sidebar_state="collapsed")

# 📺 모바일 가로 송출 최적화 커스텀 CSS
st.markdown("""
<style>
    /* 여백 제로화 */
    .block-container { padding-top: 0.2rem !important; padding-bottom: 0rem !important; padding-left: 0.3rem !important; padding-right: 0.3rem !important; max-width: 100%; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="column"] { padding-left: 0.15rem !important; padding-right: 0.15rem !important; }
    
    /* 🏢 회사명 아주 작게 구석으로 배치 */
    .company-sub { font-size: 0.8rem !important; color: #888888 !important; font-weight: 700; text-align: left; margin-bottom: -5px; }
    
    /* 🕒 중앙 정렬 초거대 디지털 시계 디자인 */
    .center-clock-container { text-align: center; margin-top: -10px; margin-bottom: 5px; }
    #clockDisplay { font-size: 3.5rem !important; font-weight: 900 !important; color: #ffffff !important; background-color: #000000 !important; padding: 0px 20px; border-radius: 8px; display: inline-block; letter-spacing: 2px; box-shadow: 0px 0px 10px rgba(255,255,255,0.2); }
    
    /* 🎯 테이블 헤더 타이틀 크기 확대 */
    .table-title { font-size: 1.5rem !important; font-weight: 900 !important; color: #FF4B4B !important; margin-top: 5px; margin-bottom: 5px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# 🏢 상단 한구석 회사명 표시
st.markdown("<div class='company-sub'>주식회사 하이모바일 LIVE</div>", unsafe_allow_html=True)

# 🕒 정중앙 배치 초거대 디지털 시계 구조
st.markdown("""
    <div class='center-clock-container'>
        <div id="clockDisplay">00:00:00</div>
    </div>
    <script>
        function updateClock() {
            var now = new Date();
            var hours = now.getHours().toString().padStart(2, '0');
            var minutes = now.getMinutes().toString().padStart(2, '0');
            var seconds = now.getSeconds().toString().padStart(2, '0');
            var timeString = hours + ':' + minutes + ':' + seconds;
            
            var clockElement = document.getElementById('clockDisplay');
            if (clockElement) {
                clockElement.innerText = timeString;
            }
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
""", unsafe_allow_html=True)

# 스트림릿 내장 브라우저 통신용 대체 시계 스크립트
import streamlit.components.v1 as components
components.html("""
    <script>
        function updateClock() {
            var now = new Date();
            var hours = now.getHours().toString().padStart(2, '0');
            var minutes = now.getMinutes().toString().padStart(2, '0');
            var seconds = now.getSeconds().toString().padStart(2, '0');
            var timeString = hours + ':' + minutes + ':' + seconds;
            
            var clockElements = window.parent.document.querySelectorAll('#clockDisplay');
            clockElements.forEach(function(el) {
                el.innerText = timeString;
            });
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
""", height=0, width=0)

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
    end_date = datetime.now(KST).strftime('%Y-%m-%d')
    start_date = (datetime.now(KST) - timedelta(days=20)).strftime('%Y-%m-%d')
    try: ks, kq = fdr.DataReader('KS11', start_date, end_date), fdr.DataReader('KQ11', start_date, end_date) 
    except: ks, kq = pd.DataFrame(), pd.DataFrame()
    try: usd = fdr.DataReader('USD/KRW', start_date, end_date)
    except: usd = pd.DataFrame()
    return ks, kq, usd

# 📺 [텍스트 전원 검정색 전광판] 수치 가독성 조절
def get_dynamic_metric_html(title, value_str, delta_str, status="up"):
    text_color = "#000000"
    if status == "up": bg_color = "#ffdddd"; border_color = "#FF4B4B"
    elif status == "down": bg_color = "#cce5ff"; border_color = "#3b82f6"
    else: bg_color = "#f0f0f0"; border_color = "#888888"
        
    return f"""
    <div style="background-color: {bg_color}; border-left: 5px solid {border_color}; border-radius: 4px; padding: 4px; text-align: center; line-height: 1.1; margin-bottom: 5px;">
        <div style="font-size: 0.9rem; color: {text_color}; font-weight: 800;">{title}</div>
        <div style="font-size: 1.4rem; color: {text_color}; font-weight: 900; margin: 1px 0;">{value_str}</div>
        <div style="font-size: 0.9rem; color: {text_color}; font-weight: 800;">{delta_str}</div>
    </div>
    """

def display_index_metric_custom(df, title):
    if df.empty or 'Close' not in df.columns:
        st.markdown(get_dynamic_metric_html(title, "N/A", "데이터 없음", "flat"), unsafe_allow_html=True); return
    df_clean = df['Close'].dropna()
    if len(df_clean) == 0:
        st.markdown(get_dynamic_metric_html(title, "N/A", "데이터 없음", "flat"), unsafe_allow_html=True); return
        
    current_val = df_clean.iloc[-1]
    prev_val = df_clean.iloc[-2] if len(df_clean) > 1 else current_val
    delta = current_val - prev_val
    delta_percent = (delta / prev_val) * 100 if prev_val != 0 else 0
    if np.isnan(delta) or np.isnan(delta_percent): delta, delta_percent = 0.0, 0.0
        
    status = "up" if delta > 0 else "down" if delta < 0 else "flat"
    sign = "+" if delta > 0 else ""
    html = get_dynamic_metric_html(title, f"{current_val:,.2f}", f"{sign}{delta:,.2f} ({sign}{delta_percent:.2f}%)", status)
    st.markdown(html, unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_after_market_data(top10_df):
    if top10_df.empty: return pd.DataFrame(columns=['종목코드', '시간외 현재가', '시간외 등락률', '_sort_ratio_num'])
    url, headers = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", get_common_headers("FHKST01010100") 
    after_market_results = []
    for idx, row in top10_df.iterrows():
        try:
            res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": row['종목코드']})
            data = res.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                after_price, after_ratio = float(data['output'].get('ovtm_untp_prpr', 0)), float(data['output'].get('ovtm_untp_prdy_ctrt', 0))
                after_market_results.append({'종목코드': row['종목코드'], '시간외 현재가': f"{int(after_price):,} 원" if after_price > 0 else "-", '시간외 등락률': f"{after_ratio:+.2f} %" if after_price > 0 else "-", '_sort_ratio_num': after_ratio})
            time.sleep(0.1) 
        except: after_market_results.append({'종목코드': row['종목코드'], '시간외 현재가': "-", '시간외 등락률': "-", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(after_market_results)
    return df if not df.empty else pd.DataFrame(columns=['종목코드', '시간외 현재가', '시간외 등락률', '_sort_ratio_num'])

@st.cache_data(ttl=60, show_spinner=False)
def fetch_pre_market_data(top10_df):
    if top10_df.empty: return pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 갭상승률', '_sort_ratio_num'])
    url, headers = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", get_common_headers("FHKST01010100") 
    pre_market_results = []
    for idx, row in top10_df.iterrows():
        try:
            res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": row['종목코드']})
            data = res.json()
            if data.get('rt_cd') == '0' and 'output' in data:
                def safe_float(val): return float(val) if val not in [None, "", " "] else 0.0
                pre_price, pre_ratio = safe_float(data['output'].get('antc_cnpr', 0)), safe_float(data['output'].get('antc_cntg_prdy_ctrt', 0))
                pre_market_results.append({'종목코드': row['종목코드'], '☀️ 예상 체결가': f"{int(pre_price):,} 원" if pre_price > 0 else "대기", '☀️ 갭상승률': f"{pre_ratio:+.2f} %" if pre_price > 0 else "0.00 %", '_sort_ratio_num': pre_ratio})
            time.sleep(0.1) 
        except: pre_market_results.append({'종목코드': row['종목코드'], '☀️ 예상 체결가': "-", '☀️ 갭상승률': "-", '_sort_ratio_num': 0.0})
    df = pd.DataFrame(pre_market_results)
    return df if not df.empty else pd.DataFrame(columns=['종목코드', '☀️ 예상 체결가', '☀️ 갭상승률', '_sort_ratio_num'])

# -----------------------------------------------------------------------------
# 🤖 오토 파일럿 시간 자동 연동
# -----------------------------------------------------------------------------
now_time = datetime.now(KST).time()
time_pre_start, time_reg_start, time_after_start, time_after_end = dt_time(8, 30), dt_time(9, 0), dt_time(15, 30), dt_time(18, 0)
pre_market_mode, after_market_mode = False, True

if time_pre_start <= now_time < time_reg_start: pre_market_mode, after_market_mode = True, False
elif time_reg_start <= now_time < time_after_start: pre_market_mode, after_market_mode = False, False
elif time_after_start <= now_time < time_after_end: pre_market_mode, after_market_mode = False, True

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60000, limit=10000, key="auto_scanner_refresh")
except ImportError: pass

# -----------------------------------------------------------------------------
# [상단 1열] 지수 & 외인 전광판 (밀착 배열)
# -----------------------------------------------------------------------------
ks_df, kq_df, usd_df = get_market_indices_v2()
if 'foreign_futures_net' not in st.session_state: st.session_state.foreign_futures_net = get_foreign_investor_trend()
ff_net = st.session_state.foreign_futures_net

c1, c2, c3, c4, c5 = st.columns(5)
with c1: display_index_metric_custom(ks_df, "KOSPI")
with c2: display_index_metric_custom(kq_df, "KOSDAQ")
with c3: display_index_metric_custom(usd_df, "USD/KRW")
with c4:
    status = "up" if ff_net > 0 else "down" if ff_net < 0 else "flat"
    sign = "+" if ff_net > 0 else ""
    html_ff = get_dynamic_metric_html("외인 선물 순매수", f"{sign}{ff_net:,} 억", "매수 우위" if ff_net > 0 else "매도 우위" if ff_net < 0 else "대기 중", status)
    st.markdown(html_ff, unsafe_allow_html=True)
with c5:
    score = min(100, max(0, int(50 + (ff_net / 10))))
    html_score = get_dynamic_metric_html("시장 매력도", f"{score} 점", "시장 탄력도", "up" if score >= 50 else "down")
    st.markdown(html_score, unsafe_allow_html=True)

st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 📊 커스텀 HTML 전광판 테이블 (종목명 크기 극대화)
# -----------------------------------------------------------------------------
if pre_market_mode: st.markdown("<div class='table-title'>🎯 장전 갭상승 예상지표 Top 10</div>", unsafe_allow_html=True)
elif after_market_mode: st.markdown("<div class='table-title'>🌙 시간외 단일가 수급지표 Top 10</div>", unsafe_allow_html=True)
else: st.markdown("<div class='table-title'>📈 실시간 AI 주도성 랭킹 Top 10</div>", unsafe_allow_html=True)

df_universe = get_kis_top_trading_value_stocks()

if not df_universe.empty:
    filtered_df = df_universe[df_universe['등락률'] > -2.0].copy()
    X_live = filtered_df[['등락률', '거래대금', '현재가']].fillna(0)
    filtered_df['10분_상승예측(%)'] = ((filtered_df['등락률'] * 0.5) + np.log1p(filtered_df['거래대금'])).round(2)
    filtered_df['테마'] = filtered_df['종목명'].apply(get_theme_icon)
    
    def detect_signal(row):
        if row['등락률'] >= 7.0 and row['거래대금'] > 50000: return "🔥 돌파"
        elif 1.0 <= row['등락률'] < 5.0 and row['거래대금'] > 20000: return "💧 눌림"
        return "▪️ 관망"
    filtered_df['매매상태'] = filtered_df.apply(detect_signal, axis=1)
    
    top_10 = filtered_df.sort_values(by='10분_상승예측(%)', ascending=False).head(10)
    
    if pre_market_mode:
        extra_df = fetch_pre_market_data(top_10)
        top_10 = pd.merge(top_10, extra_df, on='종목코드', how='left').sort_values(by='_sort_ratio_num', ascending=False)
    elif after_market_mode:
        extra_df = fetch_after_market_data(top_10)
        top_10 = pd.merge(top_10, extra_df, on='종목코드', how='left').sort_values(by='_sort_ratio_num', ascending=False)

    # 출력용 딕셔너리 생성 ('순위' 컬럼 명시적 추가)
    output_dict = {
        '순위': [f"{i}위" for i in range(1, len(top_10) + 1)],
        '테마': top_10['테마'], 
        '상태': top_10['매매상태'], 
        'AI 스코어': top_10['10분_상승예측(%)'].apply(lambda x: f"🚀 {x}점"),
        '종목명': top_10['종목명'],
        '현재가': top_10['현재가'].apply(lambda x: f"{int(x):,} 원"),
        '상승률': top_10['등락률'].apply(lambda x: f"{x:+.2f} %"),
    }
    
    if pre_market_mode:
        output_dict['☀️ 갭상승률'] = top_10['☀️ 갭상승률']
        output_dict['☀️ 체결가'] = top_10['☀️ 예상 체결가']
    elif after_market_mode:
        output_dict['🌙 시간외 등락'] = top_10['시간외 등락률']
        output_dict['🌙 시간외 가'] = top_10['시간외 현재가']
        
    output_dict['거래대금(백만)'] = top_10['거래대금'].apply(lambda x: f"{int(x):,}")
    output_df = pd.DataFrame(output_dict).reset_index(drop=True)
    
    # 💡 HTML 테이블 커스텀 렌더링 시작
    html_table = "<table style='width: 100%; border-collapse: collapse; text-align: center; background-color: #ffffff;'>"
    
    # 헤더 생성
    html_table += "<thead><tr style='background-color: #f2f2f2; border-bottom: 3px solid #000000;'>"
    for col in output_df.columns:
        html_table += f"<th style='padding: 10px; font-size: 1.1rem; font-weight: 800; color: #000000;'>{col}</th>"
    html_table += "</tr></thead><tbody>"
    
    # 데이터 열 생성 (종목명 글씨만 2.2rem으로 대폭 확대!)
    for _, row in output_df.iterrows():
        html_table += "<tr style='border-bottom: 1px solid #dddddd;'>"
        for col in output_df.columns:
            if col == '종목명':
                # 종목명: 크기 2.2rem, 가장 두꺼운 폰트(900), 완전한 검정색
                html_table += f"<td style='padding: 12px 10px; font-size: 2.2rem; font-weight: 900; color: #000000; letter-spacing: -1px;'>{row[col]}</td>"
            else:
                # 나머지 정보: 크기 1.3rem, 진한 회색/검정색
                html_table += f"<td style='padding: 12px 10px; font-size: 1.3rem; font-weight: 700; color: #333333;'>{row[col]}</td>"
        html_table += "</tr>"
    html_table += "</tbody></table>"
    
    # 화면에 HTML 렌더링
    st.markdown(html_table, unsafe_allow_html=True)
    
else:
    st.error("데이터 로드 중입니다...")
