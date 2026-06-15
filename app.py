import streamlit as st
import datetime
import time
import hmac
import hashlib
import base64
import requests
import pandas as pd

# ==========================================
# [설정] 웹 페이지 타이틀 및 연노랑 테마 디자인 (CSS)
# ==========================================
st.set_page_config(page_title="인하우스 마케팅 주간 데이터 추출기", layout="centered")

st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
    }
    section[data-testid="stSidebar"] {
        background-color: #FAFAFA;
        border-right: 1px solid #E0E0E0;
    }
    div.stButton > button {
        background-color: #FFFDE7 !important;
        color: #333333 !important;
        border: 1px solid #E0E0E0 !important;
        border-radius: 6px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: bold !important;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #FFF9C4 !important;
        border: 1px solid #BDBDBD !important;
    }
    .stTextInput>div>div>input {
        border-color: #E0E0E0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# [날짜] 오늘 기준 지난주 월요일 ~ 지난주 일요일 계산
# ==========================================
today = datetime.date.today()
current_weekday = today.weekday()  # 월요일=0, ... 일요일=6
last_monday = today - datetime.timedelta(days=current_weekday + 7)
last_sunday = last_monday + datetime.timedelta(days=6)

# ==========================================
# [인증] 네이버 검색광고 API 전용 HMAC 서명 도구
# ==========================================
def make_signature(timestamp, method, uri, secret_key):
    message = f"{timestamp}.{method}.{uri}"
    hash_obj = hmac.new(
        secret_key.encode("utf-8"), 
        message.encode("utf-8"), 
        hashlib.sha256
    )
    return base64.b64encode(hash_obj.digest()).decode("utf-8")

def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(int(time.time() * 1000))
    signature = make_signature(timestamp, method, uri, secret_key)
    return {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Timestamp': timestamp,
        'X-API-KEY': api_key,
        'X-Customer': str(customer_id),
        'X-Signature': signature
    }

# ==========================================
# [백업] API 입력 값이 없거나 연결 실패 시 보여줄 샘플 데이터
# ==========================================
def get_mock_data(ad_type):
    if ad_type == '검색광고':
        data = [
            {"캠페인명(또는 키워드)": "[검색] 브랜드_공식_키워드", "노출수": 150230, "클릭수": 4520, "클릭률(%)": 3.01, "CPC": 520, "총비용": 2350400},
            {"캠페인명(또는 키워드)": "[검색] 핵심제품_키워드_노출", "노출수": 84500, "클릭수": 1280, "클릭률(%)": 1.51, "CPC": 840, "총비용": 1075200},
        ]
    elif ad_type == '플레이스광고':
        data = [
            {"캠페인명(또는 키워드)": "[플레이스] 본점_주변상권_검색", "노출수": 52300, "클릭수": 1040, "클릭률(%)": 1.99, "CPC": 450, "총비용": 468000},
        ]
    else:
        data = [
            {"캠페인명(또는 키워드)": "[파워컨텐츠] 블로그_정보성_리뷰배포", "노출수": 24100, "클릭수": 510, "클릭률(%)": 2.12, "CPC": 650, "총비용": 331500},
        ]
    return pd.DataFrame(data)

# ==========================================
# [API 호출 메인 엔진]
# ==========================================
def fetch_naver_ad_data(customer_id, api_key, secret_key, start_date, end_date, ad_type):
    if not customer_id or not api_key or not secret_key:
        st.info("💡 API 인증 정보가 입력되지 않아 샘플(예시) 데이터를 표시합니다. 키를 정상 입력하면 실제 데이터가 조회됩니다.")
        return get_mock_data(ad_type)
    
    try:
        BASE_URL = "https://api.searchad.naver.com"
        
        # Step 1: 전체 캠페인 목록 받아오기
        campaign_uri = "/ncc/campaigns"
        headers = get_header("GET", campaign_uri, api_key, secret_key, customer_id)
        
        response = requests.get(f"{BASE_URL}{campaign_uri}", headers=headers)
        
        if response.status_code != 200:
            st.error(f"❌ 캠페인 조회 실패 (HTTP {response.status_code})")
            st.code(response.text)
            return get_mock_data(ad_type)
            
        campaigns = response.json()
        
        type_mapping = {
            '검색광고': 'WEB_SITE',
            '플레이스광고': 'PLACE',
            '파워컨텐츠광고': 'POWER_CONTENT'
        }
        target_type = type_mapping.get(ad_type, 'WEB_SITE')
        filtered_campaigns = [c for c in campaigns if c.get('campaignTp') == target_type]
        
        if not filtered_campaigns:
            st.warning(f"⚠️ '{ad_type}' 유형의 활성화된 캠페인이 존재하지 않습니다.")
            return pd.DataFrame(columns=["캠페인명(또는 키워드)", "노출수", "클릭수", "클릭률(%)", "CPC", "총비용"])

        campaign_ids = [c.get('nccCampaignId') for c in filtered_campaigns]
        camp_id_to_name = {c.get('nccCampaignId'): c.get('name') for c in filtered_campaigns}
        
        # Step 2: 다중 캠페인 ID를 한 번에 통계 API(/stats)로 Bulk 요청
        stats_uri = "/stats"
        stats_headers = get_header("GET", stats_uri, api_key, secret_key, customer_id)
        
        params = {
            'ids': campaign_ids,
            'fields': '["impCnt","clkCnt","ctr","cpc","salesAmt"]',
            'timeRange': f'{{"since":"{start_date}","until":"{end_date}"}}'
        }
        
        stats_response = requests.get(f"{BASE_URL}{stats_uri}", params=params, headers=stats_headers)
        
        if stats_response.status_code != 200:
            st.error(f"❌ 통계 데이터 조회 실패 (HTTP {stats_response.status_code})")
            st.code(stats_response.text)
            return get_mock_data(ad_type)
            
        stats_json = stats_response.json()
        data_rows = []
        
        if 'data' in stats_json:
            for stat in stats_json['data']:
                stat_id = stat.get('id')
                camp_name = camp_id_to_name.get(stat_id, "알 수 없는 캠페인")
                
                imp = int(stat.get('impCnt', 0))
                clk = int(stat.get('clkCnt', 0))
                ctr = float(stat.get('ctr', 0.0))
                cpc = int(stat.get('cpc', 0))
                cost = int(stat.get('salesAmt', 0))
                
                data_rows.append({
                    "캠페인명(또는 키워드)": camp_name,
                    "노출수": imp,
                    "클릭수": clk,
                    "클릭률(%)": ctr,
                    "CPC": cpc,
                    "총비용": cost
                })
                
        if not data_rows:
            st.warning("선택하신 기간 동안 성과 데이터가 집계되지 않았습니다.")
            return pd.DataFrame(columns=["캠페인명(또는 키워드)", "노출수", "클릭수", "클릭률(%)", "CPC", "총비용"])
            
        df = pd.DataFrame(data_rows)
        cols = ["캠페인명(또는 키워드)", "노출수", "클릭수", "클릭률(%)", "CPC", "총비용"]
        return df[cols]
        
    except Exception as e:
        st.error(f"⚠️ 시스템 오류가 발생하여 샘플 데이터로 복구되었습니다: {str(e)}")
        return get_mock_data(ad_type)

# ==========================================
# [화면 구성]
# ==========================================
st.subheader("인하우스 마케팅 주간 데이터 추출기")
st.caption("네이버 검색광고 API 연동을 통해 매주 정돈된 마케팅 지표를 즉시 복사하여 엑셀 양식에 붙여넣을 수 있습니다.")

# 사이드바 입력 컴포넌트 구성
st.sidebar.markdown("### 🔑 API 계정 인증 정보")

# 스트림릿 클라우드의 'Secrets' 시스템에 키를 등록해 놓았다면 가져오고, 없으면 공백처리합니다.
secret_customer_id = st.secrets.get("CUSTOMER_ID", "")
secret_api_key = st.secrets.get("API_KEY", "")
secret_secret_key = st.secrets.get("SECRET_KEY", "")

# Secrets가 비어 있을 경우 사용자가 직접 화면 사이드바에 타이핑하여 채울 수 있습니다.
input_customer_id = st.sidebar.text_input("CUSTOMER_ID", value=secret_customer_id, placeholder="예: 1234567")
input_api_key = st.sidebar.text_input("액세스 라이선스 (API KEY)", value=secret_api_key, type="password", placeholder="발급받은 Access Key")
input_secret_key = st.sidebar.text_input("비밀키 (SECRET_KEY)", value=secret_secret_key, type="password", placeholder="발급받은 Secret Key")

# 메인 날짜 범위 선택
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("조회 시작일", value=last_monday)
with col2:
    end_date = st.date_input("조회 종료일", value=last_sunday)

formatted_start = start_date.strftime("%Y-%m-%d")
formatted_end = end_date.strftime("%Y-%m-%d")

# 광고 종류 선택을 위한 상단 탭 구성
tabs = st.tabs(['검색광고', '플레이스광고', '파워컨텐츠광고'])

for idx, tab_name in enumerate(['검색광고', '플레이스광고', '파워컨텐츠광고']):
    with tabs[idx]:
        st.write(f"📊 **{tab_name}** 성과 통계 데이터")
        
        if st.button(f"{tab_name} 데이터 불러오기", key=f"btn_{idx}"):
            with st.spinner("네이버 광고 API로부터 최신 통계 지표를 수집 중입니다..."):
                result_df = fetch_naver_ad_data(
                    customer_id=input_customer_id,
                    api_key=input_api_key,
                    secret_key=input_secret_key,
                    start_date=formatted_start,
                    end_date=formatted_end,
                    ad_type=tab_name
                )
                
                st.dataframe(result_df, use_container_width=True)
                st.success("✅ 조회 완료! 마우스 드래그 혹은 우측 상단 메뉴를 통해 엑셀에 바로 붙여넣기 하실 수 있습니다.")
