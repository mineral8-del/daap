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

# 📺 모바일 가로 송출 극강의 세로 압축 + 예쁜 디자인 CSS
st.markdown("""
<style>
    /* 💡 세로 공백 파괴 (상단 여백 0) */
    .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; padding-left: 0.2rem !important; padding-right: 0.2rem !important; max-width: 100%; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="column"] { padding-left: 0.1rem !important; padding-right: 0.1rem !important; }
    
    /* 🏢 회사명 구석 배치 */
    .company-sub { font-size: 0.75rem !important; color: #888888 !important; font-weight: 700; text-align: left; margin-bottom: -8px; }
    
    /* 🕒 디지털 시계 슬림화 */
    .center-clock-container { text-align: center; margin-top: -12px; margin-bottom: 1px; }
    #clockDisplay { font-size: 1.15rem !important; font-weight: 800 !important; color: #ffffff !important; background-color: #111111 !important; padding: 1px 12px; border-radius: 4px; display: inline-block; letter-spacing: 1px; }
    
    /* 🎯 테이블 헤더 타이틀 슬림화 */
    .table-title { font-size: 1.1rem !important; font-weight: 900 !important; color: #FF4B4B !important; margin-top: 1px; margin-bottom: 1px; text-align: center; }
    
    /* ✨ 10개가 무조건 한 화면에 다 들어오도록 패딩 극강 압축 */
    .custom-stock-table { width: 100%; border-collapse: separate; border-spacing: 0; text-align: center; background-color: #ffffff; border-radius: 6px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-top: 1px; }
    .custom-stock-table thead tr { background-color: #1e293b; color: #ffffff; }
    .custom-stock-table th { padding: 4px 3px; font-size: 0.9rem; font-weight: 700; }
    
    /* 💡 td 여백을 3px -> 1.5px로 줄여 세로 길이를 대폭 다이어트 */
    .custom-stock-table td { padding: 1.5px 3px; border-bottom: 1px solid #f1f5f9; line-height: 1.1; }
    .custom-stock-table tbody tr:nth-of-type(even) { background-color: #f8fafc; } 
    
    /* 종목명 폰트 크기를 아주 살짝 조절하여 10개 완벽 안착 */
    .stock-name-cell { font-size: 1.45rem; font-weight: 900; color: #0f172a; letter-spacing: -1px; } 
    .up-color { color: #ef4444 !important; } 
    .down-color { color: #3b82f6 !important; } 
    .flat-color { color: #64748b !important; } 

    /* 🚀 흐르는 시세 전광판 슬림화 (40초 부드러운 속도 유지) */
    .marquee-container { width: 100%; overflow: hidden; background-color: #0f172a; color: white; padding: 4px 0; border-radius: 4px; margin-bottom: 2px; white-space: nowrap; position: relative;}
    .marquee-content { display: inline-block; animation: scroll-left 40s linear infinite; font-size: 1.05rem; font-weight: 800; }
    @keyframes scroll-left { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }
    
    /* ⏱️ 게이지 바 슬림화 */
    .progress-container { width: 100%; background-color: #e2e8f0; border-radius: 2px; height: 3px; margin-bottom: 2px; overflow: hidden; }
    #scanProgressBar { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa, #ef4444); width: 0%; transition: width 0.1s linear; }
</style>
""", unsafe_allow_html=True)

# 🏢 상단 한구석 회사명 표시
st.markdown("<div class='company-sub'>주식회사 하이모바일 LIVE</div>", unsafe_allow_html=True)

# 🕒 정중앙 배치 날짜+디지털 시계
st.markdown("""
    <div class='center-clock-container'>
        <div id="clockDisplay">0000-00-00 00:00:00</div>
    </div>
    <script>
        function updateClock() {
            var now = new Date();
            var year = now.getFullYear();
            var month = (now.getMonth() + 1).toString().padStart(2, '0');
            var date = now.getDate().toString().padStart(2, '0');
            var hours = now.getHours().toString().padStart(2, '0');
            var minutes = now.getMinutes().toString().padStart(2, '0');
            var seconds = now.getSeconds().toString().padStart(2, '0');
            var timeString = year + '-' + month + '-' + date + ' ' + hours + ':' + minutes + ':' + seconds;
            var clockElement = document.getElementById('clockDisplay');
            if (clockElement) clockElement.innerText = timeString;
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html("""
    <script>
        function updateClock() {
            var now = new Date();
            var year = now.getFullYear();
            var month = (now.getMonth() + 1).toString().padStart(2, '0');
            var date = now.getDate().toString().padStart(2, '0');
            var hours = now.getHours().toString().padStart(2, '0');
            var minutes = now.getMinutes().toString().padStart(2, '0');
            var seconds = now.getSeconds().toString().padStart(2, '0');
            var timeString = year + '-' + month + '-' + date + ' ' + hours + ':' + minutes + ':' + seconds;
            var clockElements = window.parent.document.querySelectorAll('#clockDisplay');
            clockElements.forEach(function(el) { el.innerText = timeString; });
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
""", height=0, width=0)

KST = timezone(timedelta(hours=9))

THEME_DICT = {
    "🤖 로봇": ["두산로보틱스", "레인보우로보틱스", "뉴로메카", "에스피지", "로보티즈", "이랜시스", "로보틱스", "로보스타"],
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
            if res.json().get('rt_cd') == '0': df_list.append(pd.DataFrame(res.json()['output'])[['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr', 'prdy_ctrt', 'acml_tr_pbmn']])
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

def get_dynamic_metric_html(title, value_str, delta_str, status="up"):
    text_color = "#000000"
    if status == "up": bg_color = "#ffdddd"; border_color = "#FF4B4B"
    elif status == "down": bg_color = "#cce5ff"; border_color = "#3b82f6"
    else: bg_color = "#f0f0f0"; border_color = "#888888"
        
    return f"""
    <div style="background-color: {bg_color}; border-left: 5px solid {border_color}; border-radius: 4px; padding: 1px 3px; text-align: center; line-height: 1.05; margin-bottom: 1px;">
        <div style="font-size: 0.75rem; color: {text_color}; font-weight: 800;">{title}</div>
        <div style="font-size: 1.1rem; color: {text_color}; font-weight: 900; margin: 0px 0;">{value_str}</div>
        <div style="font-size: 0.75rem; color: {text_color}; font-weight: 800;">{delta_str}</div>
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
    st.markdown(get_dynamic_metric_html(title, f"{current_val:,.2f}", f"{sign}{delta:,.2f} ({sign}{delta_percent:.2f}%)", status), unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_after_market_data(top10_df):
    if top10_df.empty: return pd.DataFrame()
    url, headers = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", get_common_headers("FHKST01010100") 
    results = []
    for _, row in top10_df.iterrows():
        try:
            res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": row['종목코드']})
            if res.json().get('rt_cd') == '0':
                out = res.json()['output']
                results.append({'종목코드': row['종목코드'], '시간외 현재가': f"{int(float(out.get('ovtm_untp_prpr', 0))):,} 원", '시간외 등락률': f"{float(out.get('ovtm_untp_prdy_ctrt', 0)):+.2f} %", '_sort_ratio': float(out.get('ovtm_untp_prdy_ctrt', 0))})
            time.sleep(0.7) 
        except: results.append({'종목코드': row['종목코드'], '시간외 현재가': "-", '시간외 등락률': "-", '_sort_ratio': 0.0})
    return pd.DataFrame(results)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_pre_market_data(top10_df):
    if top10_df.empty: return pd.DataFrame()
    url, headers = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price", get_common_headers("FHKST01010100") 
    results = []
    for _, row in top10_df.iterrows():
        try:
            res = requests.get(url, headers=headers, params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": row['종목코드']})
            if res.json().get('rt_cd') == '0':
                out = res.json()['output']
                pr = float(out.get('antc_cnpr', 0) or 0.0)
                results.append({'종목코드': row['종목코드'], '☀️ 예상 체결가': f"{int(pr):,} 원" if pr > 0 else "대기", '☀️ 갭상승률': f"{float(out.get('antc_cntg_prdy_ctrt', 0) or 0.0):+.2f} %", '_sort_ratio': float(out.get('antc_cntg_prdy_ctrt', 0) or 0.0)})
            time.sleep(0.7) 
        except: results.append({'종목코드': row['종목코드'], '☀️ 예상 체결가': "-", '☀️ 갭상승률': "-", '_sort_ratio': 0.0})
    return pd.DataFrame(results)

# -----------------------------------------------------------------------------
# 🤖 오토 파일럿 시간 자동 연동
# -----------------------------------------------------------------------------
now_time = datetime.now(KST).time()
time_pre, time_reg, time_aft, time_end = dt_time(8, 30), dt_time(9, 0), dt_time(15, 30), dt_time(18, 0)
pre_mode = time_pre <= now_time < time_reg
after_mode = time_aft <= now_time < time_end

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=60000, limit=10000, key="auto_refresh")
except ImportError: pass

# -----------------------------------------------------------------------------
# 🚀 실시간 데이터 패치 및 필터링
# -----------------------------------------------------------------------------
df_universe = get_kis_top_trading_value_stocks()
top_10 = pd.DataFrame()
ticker_html_str = "실시간 데이터를 불러오는 중입니다..."

if not df_universe.empty:
    df_universe = df_universe[df_universe['등락률'] > -2.0].copy()
    df_universe['10분_상승예측(%)'] = ((df_universe['등락률'] * 0.5) + np.log1p(df_universe['거래대금'])).round(2)
    df_universe['테마'] = df_universe['종목명'].apply(get_theme_icon)
    df_universe['매매상태'] = df_universe.apply(lambda r: "🔥 돌파" if r['등락률'] >= 7.0 and r['거래대금'] > 50000 else ("💧 눌림" if 1.0 <= r['등락률'] < 5.0 and r['거래대금'] > 20000 else "▪️ 관망"), axis=1)
    
    top_10 = df_universe.sort_values(by='10분_상승예측(%)', ascending=False).head(10)
    
    if pre_mode:
        extra_df = fetch_pre_market_data(top_10)
        if not extra_df.empty: top_10 = pd.merge(top_10, extra_df, on='종목코드', how='left').sort_values(by='_sort_ratio', ascending=False)
    elif after_mode:
        extra_df = fetch_after_market_data(top_10)
        if not extra_df.empty: top_10 = pd.merge(top_10, extra_df, on='종목코드', how='left').sort_values(by='_sort_ratio', ascending=False)

    # 🚀 Ticker(시세 띠)용 문자열 생성
    ticker_items = []
    for _, row in top_10.iterrows():
        color = "#ef4444" if row['등락률'] > 0 else "#3b82f6" if row['등락률'] < 0 else "#ffffff"
        ticker_items.append(f"<span style='color:#fbbf24;'>{row['종목명']}</span> <span style='color:{color};'>{row['등락률']:+.2f}%</span>")
    ticker_html_str = "&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;".join(ticker_items * 3)

# -----------------------------------------------------------------------------
# [상단 1열] 지수 & 외인 전광판
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
    st.markdown(get_dynamic_metric_html("외인 선물 순매수", f"{sign}{ff_net:,} 억", "매수 우위" if ff_net > 0 else "매도 우위" if ff_net < 0 else "대기 중", status), unsafe_allow_html=True)
with c5:
    score = min(100, max(0, int(50 + (ff_net / 10))))
    st.markdown(get_dynamic_metric_html("시장 매력도", f"{score} 점", "시장 탄력도", "up" if score >= 50 else "down"), unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 🚀 역동적 애니메이션 (시세 흐름 띠 + 타이머 게이지)
# -----------------------------------------------------------------------------
st.markdown(f"""
    <div class="marquee-container">
        <div class="marquee-content">
            🔥 [하이모바일 LIVE 실시간 주도주 스캔] &nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp; {ticker_html_str}
        </div>
    </div>
    
    <div class="progress-container">
        <div id="scanProgressBar"></div>
    </div>
    
    <script>
        var startTime = Date.now();
        function updateProgress() {{
            var elapsed = Date.now() - startTime;
            var percent = (elapsed % 60000) / 60000 * 100;
            var bar = document.getElementById('scanProgressBar');
            if(bar) bar.style.width = percent + '%';
            var parentBar = window.parent.document.getElementById('scanProgressBar');
            if(parentBar) parentBar.style.width = percent + '%';
        }}
        setInterval(updateProgress, 100); 
    </script>
""", unsafe_allow_html=True)

components.html("""
    <script>
        var startTime = Date.now();
        function updateProgress() {
            var elapsed = Date.now() - startTime;
            var percent = (elapsed % 60000) / 60000 * 100;
            var bars = window.parent.document.querySelectorAll('#scanProgressBar');
            bars.forEach(function(el) { el.style.width = percent + '%'; });
        }
        setInterval(updateProgress, 100);
    </script>
""", height=0, width=0)

# -----------------------------------------------------------------------------
# 📊 커스텀 HTML 전광판 테이블 (본문)
# -----------------------------------------------------------------------------
if pre_mode: st.markdown("<div class='table-title'>🎯 장전 갭상승 예상지표 Top 10</div>", unsafe_allow_html=True)
elif after_mode: st.markdown("<div class='table-title'>🌙 시간외 단일가 수급지표 Top 10</div>", unsafe_allow_html=True)
else: st.markdown("<div class='table-title'>📈 실시간 AI 주도성 랭킹 Top 10</div>", unsafe_allow_html=True)

if not top_10.empty:
    output_dict = {
        '순위': [f"{i}위" for i in range(1, len(top_10) + 1)],
        '테마': top_10['테마'].values, '상태': top_10['매매상태'].values,
        'AI 스코어': [f"🚀 {x}점" for x in top_10['10분_상승예측(%)']],
        '종목명': top_10['종목명'].values,
        '현재가': [f"{int(x):,} 원" for x in top_10['현재가']],
        '상승률': [f"{x:+.2f} %" for x in top_10['등락률']],
    }
    
    if pre_mode and '☀️ 갭상승률' in top_10.columns:
        output_dict['☀️ 갭상승률'], output_dict['☀️ 체결가'] = top_10['☀️ 갭상승률'].values, top_10['☀️ 예상 체결가'].values
    elif after_mode and '시간외 등락률' in top_10.columns:
        output_dict['🌙 시간외 등락'], output_dict['🌙 시간외 가'] = top_10['시간외 등락률'].values, top_10['시간외 현재가'].values
        
    output_dict['거래대금(백만)'] = [f"{int(x):,}" for x in top_10['거래대금']]
    output_df = pd.DataFrame(output_dict)
    
    html_table = "<table class='custom-stock-table'><thead><tr>"
    for col in output_df.columns: html_table += f"<th>{col}</th>"
    html_table += "</tr></thead><tbody>"
    
    for _, row in output_df.iterrows():
        html_table += "<tr>"
        for col in output_df.columns:
            val = str(row[col])
            color_cls = 'flat-color'
            if '상승률' in col or '등락' in col:
                if '+' in val: color_cls = 'up-color'
                elif '-' in val: color_cls = 'down-color'
            elif '현재가' in col or '체결가' in col or '가' in col[-1:]:
                rate_col = [c for c in output_df.columns if '상승률' in c or '등락' in c][0]
                if '+' in str(row[rate_col]): color_cls = 'up-color'
                elif '-' in str(row[rate_col]): color_cls = 'down-color'

            if col == '종목명': style = "class='stock-name-cell'"
            elif col in ['현재가', '상승률', '☀️ 갭상승률', '☀️ 체결가', '🌙 시간외 등락', '🌙 시간외 가']: style = f"class='{color_cls}' style='font-size: 1.25rem; font-weight: 800;'"
            elif col == '순위': style = "style='font-size: 1.1rem; font-weight: 900; color: #555;'"
            elif col == 'AI 스코어': style = "style='font-size: 1.1rem; font-weight: bold; color: #d97706;'"
            else: style = "style='font-size: 1.05rem; font-weight: 700; color: #444;'"
            
            html_table += f"<td {style}>{val}</td>"
        html_table += "</tr>"
    html_table += "</tbody></table>"
    
    st.markdown(html_table, unsafe_allow_html=True)
else:
    st.error("데이터를 수집 중입니다. 장 시작 전이거나 네트워크 상태를 확인해주세요.")
