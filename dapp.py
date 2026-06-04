import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta, timezone, time as dt_time
import FinanceDataReader as fdr
import io
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

# 📺 40대 이상 타겟: HTS 느낌의 신뢰감 있는 묵직한 컬러 및 동적 애니메이션 CSS
st.markdown("""
<style>
    /* 상하좌우 여백 최적화 */
    .block-container { padding-top: 0.5rem !important; padding-bottom: 0.5rem !important; padding-left: 1rem !important; padding-right: 1rem !important; max-width: 100%; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="column"] { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }

    /* 🔴 유튜브 방어용 라이브 깜빡임 애니메이션 */
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.2; } 100% { opacity: 1; } }
    .live-indicator { color: #dc2626; font-weight: 900; animation: blink 1.5s infinite; }

    /* 🏢 회사명 및 타이틀 */
    .company-sub { font-size: 1.3rem !important; color: #1e3a8a !important; font-weight: 900; text-align: left; margin-bottom: -5px; letter-spacing: -0.5px;}

    /* 🕒 큼직한 디지털 시계 (HTS 스타일) */
    .center-clock-container { text-align: center; margin-top: -20px; margin-bottom: 10px; }
    #clockDisplay { font-size: 2.2rem !important; font-weight: 900 !important; color: #fbbf24 !important; background-color: #0f172a !important; padding: 5px 30px; border-radius: 8px; letter-spacing: 3px; border: 2px solid #334155; }

    /* 🎯 테이블 헤더 타이틀 */
    .table-title { font-size: 1.8rem !important; font-weight: 900 !important; color: #1e3a8a !important; margin-top: 10px; margin-bottom: 5px; text-align: center; letter-spacing: -1px; }

    /* ✨ 40대 타겟: 큼직하고 묵직한 HTS 전광판 테이블 */
    .custom-stock-table { width: 100%; border-collapse: separate; border-spacing: 0; text-align: center; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.15); border: 1px solid #cbd5e1; }
    .custom-stock-table thead tr { background-color: #0f172a; color: #ffffff; border-bottom: 3px solid #fbbf24; }

    .custom-stock-table th { padding: 15px 10px; font-size: 1.3rem; font-weight: 800; border-bottom: 2px solid #fbbf24; }
    .custom-stock-table td { padding: 14px 10px; border-bottom: 1px solid #e2e8f0; line-height: 1.4; }
    .custom-stock-table tbody tr:hover { background-color: #fef08a !important; transition: background-color 0.3s; } /* 마우스 오버 효과로 동적 느낌 추가 */

    /* 가독성을 높인 진한 폰트 컬러 */
    .stock-name-cell { font-size: 2.4rem; font-weight: 900; color: #000000; letter-spacing: -1.5px; text-shadow: 1px 1px 0px rgba(0,0,0,0.05); } 
    .up-color { color: #dc2626 !important; font-weight: 900 !important; } /* 진한 빨강 */
    .down-color { color: #2563eb !important; font-weight: 900 !important; } /* 진한 파랑 */
    .flat-color { color: #475569 !important; font-weight: 900 !important; } 

    /* 🚀 역동적인 시세 전광판 */
    .marquee-container { width: 100%; overflow: hidden; background-color: #1e293b; color: white; padding: 12px 0; border-radius: 6px; margin-bottom: 10px; border-left: 5px solid #fbbf24; white-space: nowrap; position: relative;}
    .marquee-content { display: inline-block; animation: scroll-left 30s linear infinite; font-size: 1.5rem; font-weight: 800; }
    @keyframes scroll-left { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }

    /* ⏱️ 30초 갱신 게이지 바 (동적인 화면을 위해 두껍게) */
    .progress-container { width: 100%; background-color: #cbd5e1; border-radius: 4px; height: 10px; margin-bottom: 10px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.2); }
    #scanProgressBar { height: 100%; background: linear-gradient(90deg, #2563eb, #fbbf24, #dc2626); width: 0%; transition: width 0.1s linear; }

    /* 🛡️ 유튜브 면책 조항 및 가이드 패널 */
    .youtube-disclaimer {
        background-color: #f8fafc; border: 3px solid #cbd5e1; border-left: 8px solid #dc2626; border-radius: 8px; 
        padding: 15px 20px; margin-top: 15px; font-size: 1.2rem; color: #1e293b; 
        display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .guide-box { width: 65%; }
    .warning-box { width: 33%; text-align: right; background-color: #fee2e2; padding: 10px; border-radius: 6px; border: 1px solid #fca5a5;}
</style>
""", unsafe_allow_html=True)

# 🏢 상단: 라이브 깜빡임 + 회사명
st.markdown("<div class='company-sub'><span class='live-indicator'>● LIVE</span> 주식회사 하이모바일 실시간 수급 스캐너</div>",
            unsafe_allow_html=True)

# 🕒 디지털 시계 (스크립트)
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

            // iframe 밖의 시계도 동기화 (Streamlit 특성 고려)
            var parentClock = window.parent.document.getElementById('clockDisplay');
            if (parentClock) parentClock.innerText = timeString;
        }
        setInterval(updateClock, 1000);
        updateClock();
    </script>
""", unsafe_allow_html=True)

KST = timezone(timedelta(hours=9))

THEME_DICT = {
    "🤖 로봇": ["두산로보틱스", "레인보우로보틱스", "뉴로메카", "에스피지", "로보티즈", "이랜시스", "로보스타"],
    "💾 반도체": ["한미반도체", "SK하이닉스", "삼성전자", "HPSP", "이수페타시스", "제우스", "리노공업", "디아이"],
    "🔋 2차전지": ["에코프로", "에코프로비엠", "포스코홀딩스", "POSCO홀딩스", "LG에너지솔루션", "금양"],
    "🧬 바이오": ["알테오젠", "HLB", "삼성바이오로직스", "셀트리온", "삼천당제약", "리가켐바이오"],
    "⚡ 전력기기": ["HD현대일렉트릭", "LS일렉트릭", "효성중공업", "제룡전기", "일진전기"],
    "💄 화장품": ["실리콘투", "브이티", "코스메카코리아", "씨앤씨인터내셔널", "아모레퍼시픽"]
}


def get_theme_icon(stock_name):
    for theme, keywords in THEME_DICT.items():
        if any(keyword in stock_name for keyword in keywords): return theme
    return "▪️ 개별주"


@st.cache_resource(ttl=3600 * 20)
def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(f"{URL_BASE}/oauth2/tokenP", headers=headers, data=json.dumps(body))
        return res.json()["access_token"]
    except:
        return None


def get_common_headers(tr_id):
    token = get_access_token()
    if not token: token = get_access_token()
    return {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appKey": APP_KEY,
            "appSecret": APP_SECRET, "tr_id": tr_id}


# -----------------------------------------------------------------------------
# 🤖 오토 파일럿 및 30초 리셋 설정 (핵심 변경점)
# -----------------------------------------------------------------------------
now_time = datetime.now(KST).time()
time_pre, time_reg, time_aft, time_end = dt_time(8, 30), dt_time(9, 0), dt_time(15, 30), dt_time(18, 0)
pre_mode = time_pre <= now_time < time_reg
after_mode = time_aft <= now_time < time_end

try:
    from streamlit_autorefresh import st_autorefresh

    # 30,000ms = 30초 주기로 화면 전체 새로고침
    st_autorefresh(interval=30000, limit=10000, key="auto_refresh")
except ImportError:
    pass


@st.cache_data(ttl=15)  # 30초 리셋에 맞춰 캐시 주기도 짧게 변경
def get_kis_top_trading_value_stocks():
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/volume-rank"
    headers = get_common_headers("FHPST01710000")
    df_list = []
    for params in [{"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000",
                    "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111",
                    "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "10000", "FID_INPUT_PRICE_2": "80000",
                    "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""},
                   {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171", "FID_INPUT_ISCD": "0000",
                    "FID_DIV_CLS_CODE": "1", "FID_BLNG_CLS_CODE": "0", "FID_TRGT_CLS_CODE": "111111111",
                    "FID_TRGT_EXLS_CLS_CODE": "111111", "FID_INPUT_PRICE_1": "80000", "FID_INPUT_PRICE_2": "2000000",
                    "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""}]:
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.json().get('rt_cd') == '0': df_list.append(pd.DataFrame(res.json()['output'])[
                                                                  ['hts_kor_isnm', 'mksc_shrn_iscd', 'stck_prpr',
                                                                   'prdy_ctrt', 'acml_tr_pbmn']])
        except:
            continue
    if not df_list: return pd.DataFrame()
    df = pd.concat(df_list, ignore_index=True)
    df.columns = ['종목명', '종목코드', '현재가', '등락률', '거래대금']
    df = df[~df['종목명'].str.contains('|'.join(
        ['KODEX', 'TIGER', 'KBSTAR', 'ACE', 'ARIRANG', 'HANARO', 'KOSEF', 'SOL', 'TIMEFOLIO', 'WOORI', '히어로즈', '마이티',
         '스팩', 'ETN']), case=False, regex=True)]
    df['현재가'], df['등락률'], df['거래대금'] = pd.to_numeric(df['현재가'], errors='coerce'), pd.to_numeric(df['등락률'],
                                                                                                errors='coerce'), pd.to_numeric(
        df['거래대금'], errors='coerce') / 1000000
    return df.sort_values(by='거래대금', ascending=False).drop_duplicates(subset=['종목코드']).dropna()


# 데이터 처리 로직 (외인, 지수, 장전/장후 데이터)
@st.cache_data(ttl=15)
def get_foreign_investor_trend():
    session, token = requests.Session(), get_access_token()
    if not token: return 0.0
    try:
        res = session.get(
            "https://openapivts.koreainvestment.com:29443/uapi/domestic-future/v1/quotation/inquire-investor-trend",
            headers={"content-type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY,
                     "appsecret": APP_SECRET, "tr_id": "FHUFT01010000"},
            params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": "000"}, timeout=4)
        if res.status_code == 200:
            for data in res.json().get("output1", []):
                if "외국인" in data.get("invst_vo", ""):
                    val = float(data.get("ntby_pamt", 0)) / 100000000
                    if val != 0.0: return round(val, 1)
    except:
        pass
    return 0.0


@st.cache_data(ttl=30)
def get_market_indices_v2():
    end_date, start_date = datetime.now(KST).strftime('%Y-%m-%d'), (datetime.now(KST) - timedelta(days=20)).strftime(
        '%Y-%m-%d')
    try:
        ks, kq = fdr.DataReader('KS11', start_date, end_date), fdr.DataReader('KQ11', start_date, end_date)
    except:
        ks, kq = pd.DataFrame(), pd.DataFrame()
    try:
        usd = fdr.DataReader('USD/KRW', start_date, end_date)
    except:
        usd = pd.DataFrame()
    return ks, kq, usd


# 커스텀 지수 박스 렌더링
def get_dynamic_metric_html(title, value_str, delta_str, status="up"):
    if status == "up":
        bg_color = "#fee2e2"; border_color = "#dc2626"; text_color = "#991b1b"
    elif status == "down":
        bg_color = "#dbeafe"; border_color = "#2563eb"; text_color = "#1e40af"
    else:
        bg_color = "#f1f5f9"; border_color = "#64748b"; text_color = "#334155"

    return f"""
    <div style="background-color: {bg_color}; border-left: 6px solid {border_color}; border-radius: 6px; padding: 4px 6px; text-align: center; line-height: 1.1; margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 0.85rem; color: #475569; font-weight: 800;">{title}</div>
        <div style="font-size: 1.3rem; color: {text_color}; font-weight: 900; margin: 2px 0;">{value_str}</div>
        <div style="font-size: 0.85rem; color: {text_color}; font-weight: 800;">{delta_str}</div>
    </div>
    """


def display_index_metric_custom(df, title):
    if df.empty or 'Close' not in df.columns:
        st.markdown(get_dynamic_metric_html(title, "N/A", "데이터 없음", "flat"), unsafe_allow_html=True);
        return
    df_clean = df['Close'].dropna()
    if len(df_clean) == 0:
        st.markdown(get_dynamic_metric_html(title, "N/A", "데이터 없음", "flat"), unsafe_allow_html=True);
        return
    current_val = df_clean.iloc[-1]
    prev_val = df_clean.iloc[-2] if len(df_clean) > 1 else current_val
    delta = current_val - prev_val
    delta_percent = (delta / prev_val) * 100 if prev_val != 0 else 0
    if np.isnan(delta) or np.isnan(delta_percent): delta, delta_percent = 0.0, 0.0
    status = "up" if delta > 0 else "down" if delta < 0 else "flat"
    sign = "+" if delta > 0 else ""
    st.markdown(
        get_dynamic_metric_html(title, f"{current_val:,.2f}", f"{sign}{delta:,.2f} ({sign}{delta_percent:.2f}%)",
                                status), unsafe_allow_html=True)


# 🚀 실시간 데이터 패치
df_universe = get_kis_top_trading_value_stocks()
top_10 = pd.DataFrame()
ticker_html_str = "실시간 주도주 데이터를 스캔하고 있습니다..."

if not df_universe.empty:
    df_universe = df_universe[df_universe['등락률'] > -2.0].copy()
    df_universe['10분_상승예측(%)'] = ((df_universe['등락률'] * 0.5) + np.log1p(df_universe['거래대금'])).round(2)
    df_universe['테마'] = df_universe['종목명'].apply(get_theme_icon)
    df_universe['매매상태'] = df_universe.apply(lambda r: "🔥 돌파" if r['등락률'] >= 7.0 and r['거래대금'] > 50000 else (
        "💧 눌림" if 1.0 <= r['등락률'] < 5.0 and r['거래대금'] > 20000 else "▪️ 관망"), axis=1)

    top_10 = df_universe.sort_values(by='10분_상승예측(%)', ascending=False).head(10)

    ticker_items = []
    for _, row in top_10.iterrows():
        color = "#ef4444" if row['등락률'] > 0 else "#60a5fa" if row['등락률'] < 0 else "#ffffff"
        ticker_items.append(
            f"<span style='color:#fbbf24;'>{row['종목명']}</span> <span style='color:{color};'>{row['등락률']:+.2f}%</span>")
    ticker_html_str = "&nbsp;&nbsp;&nbsp;&nbsp;⭐&nbsp;&nbsp;&nbsp;&nbsp;".join(ticker_items * 4)

# -----------------------------------------------------------------------------
# [상단 1열] 지수 & 외인 전광판
# -----------------------------------------------------------------------------
ks_df, kq_df, usd_df = get_market_indices_v2()
if 'foreign_futures_net' not in st.session_state: st.session_state.foreign_futures_net = get_foreign_investor_trend()
ff_net = st.session_state.foreign_futures_net

c1, c2, c3, c4, c5 = st.columns(5)
with c1: display_index_metric_custom(ks_df, "KOSPI 종합")
with c2: display_index_metric_custom(kq_df, "KOSDAQ 종합")
with c3: display_index_metric_custom(usd_df, "원/달러 환율")
with c4:
    status = "up" if ff_net > 0 else "down" if ff_net < 0 else "flat"
    sign = "+" if ff_net > 0 else ""
    st.markdown(get_dynamic_metric_html("외국인 선물 순매수", f"{sign}{ff_net:,} 억",
                                        "매수 우위" if ff_net > 0 else "매도 우위" if ff_net < 0 else "대기 중", status),
                unsafe_allow_html=True)
with c5:
    score = min(100, max(0, int(50 + (ff_net / 10))))
    st.markdown(get_dynamic_metric_html("시장 탄력 스코어", f"{score} 점", "수급 강도", "up" if score >= 50 else "down"),
                unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 🚀 역동적 애니메이션 (시세 흐름 띠 + 30초 타이머 게이지)
# -----------------------------------------------------------------------------
st.markdown(f"""
    <div class="marquee-container">
        <div class="marquee-content">
            <span class="live-indicator">🔴 실시간 수급 포착</span> &nbsp;&nbsp;&nbsp;&nbsp; {ticker_html_str}
        </div>
    </div>
    <div class="progress-container"><div id="scanProgressBar"></div></div>
    <script>
        var startTime = Date.now();
        function updateProgress() {{
            var elapsed = Date.now() - startTime;
            // 30,000ms (30초) 주기로 게이지 바 리셋
            var percent = (elapsed % 30000) / 30000 * 100;
            var bar = document.getElementById('scanProgressBar');
            if(bar) bar.style.width = percent + '%';

            var parentBar = window.parent.document.getElementById('scanProgressBar');
            if(parentBar) parentBar.style.width = percent + '%';
        }}
        setInterval(updateProgress, 100); 
    </script>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 📊 커스텀 HTML 전광판 테이블 (본문)
# -----------------------------------------------------------------------------
if pre_mode:
    st.markdown("<div class='table-title'>🎯 장전 예상 체결 랭킹 Top 10</div>", unsafe_allow_html=True)
elif after_mode:
    st.markdown("<div class='table-title'>🌙 시간외 단일가 랭킹 Top 10</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='table-title'>📈 정규장 AI 수급 돌파 랭킹 Top 10</div>", unsafe_allow_html=True)

if not top_10.empty:
    output_dict = {
        '순위': [f"{i}위" for i in range(1, len(top_10) + 1)],
        '테마분류': top_10['테마'].values,
        'AI타점': top_10['매매상태'].values,
        '종목명': top_10['종목명'].values,
        '현재가': [f"{int(x):,} 원" for x in top_10['현재가']],
        '상승률': [f"{x:+.2f} %" for x in top_10['등락률']],
        '거래대금': [f"{int(x):,} 백만" for x in top_10['거래대금']]
    }

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
                if '+' in val:
                    color_cls = 'up-color'
                elif '-' in val:
                    color_cls = 'down-color'
            elif '현재가' in col or '거래대금' in col:
                rate_col = '상승률'
                if '+' in str(row[rate_col]):
                    color_cls = 'up-color'
                elif '-' in str(row[rate_col]):
                    color_cls = 'down-color'

            # 40대 타겟 폰트 사이즈 및 굵기 대폭 상향
            if col == '종목명':
                style = "class='stock-name-cell'"
            elif col in ['현재가', '상승률']:
                style = f"class='{color_cls}' style='font-size: 1.5rem; font-weight: 900;'"
            elif col == '순위':
                style = "style='font-size: 1.3rem; font-weight: 900; color: #475569;'"
            elif col == 'AI타점':
                style = "style='font-size: 1.2rem; font-weight: 900; color: #b45309;'"
            elif col == '거래대금':
                style = f"class='{color_cls}' style='font-size: 1.3rem; font-weight: 800;'"
            else:
                style = "style='font-size: 1.2rem; font-weight: 700; color: #334155;'"

            html_table += f"<td {style}>{val}</td>"
        html_table += "</tr>"
    html_table += "</tbody></table>"

    st.markdown(html_table, unsafe_allow_html=True)
else:
    st.error("데이터를 수집 중입니다. 네트워크 상태를 확인해주세요.")

# -----------------------------------------------------------------------------
# 🛡️ [유튜브 정책 방어용] 면책 조항 및 시청자 안내 패널
# -----------------------------------------------------------------------------
st.markdown("""
<div class="youtube-disclaimer">
    <div class="guide-box">
        <div style="font-size: 1.3rem; font-weight: 900; color: #1e3a8a; margin-bottom: 8px;">📊 하이모바일 AI 수급 스캐너 보는 법</div>
        <ul style="margin: 0; padding-left: 20px; line-height: 1.6; font-weight: 700; color: #334155;">
            <li><b>🔥 돌파:</b> 거래대금 500억 이상 유입되며 <span style="color:#dc2626;">+7% 이상 급등</span>하는 강한 추세 종목입니다.</li>
            <li><b>💧 눌림:</b> 거래대금 유입 후 <span style="color:#dc2626;">+1~5% 구간</span>에서 에너지를 모으는 종목입니다.</li>
            <li><b>화면 갱신:</b> 본 화면은 증권사 API를 통해 <b>매 30초마다</b> 실시간으로 자동 갱신됩니다.</li>
        </ul>
    </div>
    <div class="warning-box">
        <div style="font-size: 1.1rem; font-weight: 900; color: #991b1b; margin-bottom: 5px;">⚠️ 투자 유의사항 (Disclaimer)</div>
        <div style="font-size: 0.95rem; font-weight: 700; color: #7f1d1d; line-height: 1.4;">
            본 방송은 AI가 데이터를 단순 수집하여 보여주는 화면으로 <b>투자를 권유하지 않습니다.</b><br>
            모든 투자의 최종 책임은 <b>투자자 본인</b>에게 있습니다.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
