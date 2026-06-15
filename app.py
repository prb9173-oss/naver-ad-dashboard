import streamlit as st
import datetime
import time
import hmac
import hashlib
import base64
import requests
import pandas as pd

# ==========================================
# [디자인 정의] 배경은 밝은 화이트, 글씨만 선명한 블랙으로 강제 세팅 (CSS)
# ==========================================
st.set_page_config(page_title="인하우스 마케팅 주간 데이터 추출기", layout="centered")

st.markdown("""
    <style>
    /* 1. 메인 컨텐츠 영역의 배경을 완전히 밝은 흰색(#FFFFFF)으로 강제 고정합니다. */
    .stApp {
        background-color: #FFFFFF !important;
    }
    
    /* 2. 사이드바 영역의 배경을 부드럽고 밝은 연회색(#F8F9FA)으로 지정합니다. */
    section[data-testid="stSidebar"] {
        background-color: #F8F9FA !important;
        border-right: 1px solid #E0E0E0 !important;
    }
    
    /* 3. 레이아웃 컨테이너(div)는 건드리지 않고, 순수 '글씨/텍스트' 요소들만 검은색(#000000)으로 지정합니다. */
    p, span, label, h1, h2, h3, h4, h5, h6, li, strong, th, td {
        color: #000000 !important;
    }
    
    /* 4. 스트림릿 마크다운 및 입력창 위젯들의 라벨 색상을 진하고 선명하게 처리합니다. */
    .stMarkdown, [data-testid="stWidgetLabel"] p, .stCaptionContainer p {
        color: #000000 !important;
        font-weight: 500;
    }
    
    /* 5. 사이드바와 입력 상자 타이틀의 글씨 두께를 강조합니다. */
    .stTextInput label p, .stSelectbox label p, .stDateInput label p, [data-testid="stSidebar"] label p {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    
    /* 6. 입력창 내부의 글자색도 흰색 배경에 검은색 글씨로 고정합니다. */
    input, select, textarea, div[data-baseweb="select"] {
        color: #000000 !important;
        background-color: #FFFFFF !important;
    }
    
    /* 7. 데이터프레임(표) 내부 텍스트 색상을 검은색으로 고정합니다. */
    .stDataFrame div {
        color: #000000 !important;
    }
    
    /* 8. 주요 강조 포인트인 [상세데이터 가져오기] 단추를 은은한 연노랑(#FFFDE7)으로 디자인합니다. */
    div.stButton > button {
        background-color: #FFFDE7 !important;
        color: #000000 !important;
        border: 1px solid #C0B090 !important;
        border-radius: 6px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: bold !important;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #FFF9C4 !important;
        border: 1px solid #999999 !important;
    }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# [날짜 계산] 오늘 기준 지난주 월요일 ~ 지난주 일요일 자동 계산
# ==========================================
today = datetime.date.today()
current_weekday = today.weekday()  # 오늘 요일 (월요일=0, ... 일요일=6)
last_monday = today - datetime.timedelta(days=current_weekday + 7)  # 지난주 월요일
last_sunday = last_monday + datetime.timedelta(days=6)  # 지난주 일요일


# ==========================================
# [인증] 네이버 검색광고 API 전용 HMAC 서명 생성 모듈
# ==========================================
def make_signature(timestamp, method, uri, secret_key):
    message = f"{timestamp}.{method}.{uri}"
    hash_obj = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
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
# [가상 테스트 데이터] API 입력 없이 흐름 파악을 위한 데이터 백업본
# ==========================================
def get_mock_campaigns(ad_type):
    if ad_type == '검색광고':
        return [{"nccCampaignId": "camp-sh-01", "name": "[검색] 브랜드_공식_캠페인"},
                {"nccCampaignId": "camp-sh-02", "name": "[검색] 핵심제품_검색광고"}]
    elif ad_type == '플레이스광고':
        return [{"nccCampaignId": "camp-pl-01", "name": "[플레이스] 강남직영점_홍보캠페인"}]
    else:
        return [{"nccCampaignId": "camp-pc-01", "name": "[파워컨텐츠] 네이버카페_조회캠페인"}]

def get_mock_adgroups(campaign_id):
    if campaign_id == "camp-sh-01":
        return [{"nccAdgroupId": "grp-sh-01-a", "name": "PC_대표브랜드_광고그룹"},
                {"nccAdgroupId": "grp-sh-01-b", "name": "모바일_대표브랜드_광고그룹"}]
    elif campaign_id == "camp-sh-02":
        return [{"nccAdgroupId": "grp-sh-02-a", "name": "인기상품_카테고리_광고그룹"}]
    elif campaign_id == "camp-pl-01":
        return [{"nccAdgroupId": "grp-pl-01-a", "name": "지역기반_플레이스_광고그룹"}]
    else:
        return [{"nccAdgroupId": "grp-pc-01-a", "name": "리뷰_콘텐츠_매칭_광고그룹"}]

def get_mock_daily_stats(adgroup_id, start_date, end_date):
    date_list = []
    curr = start_date
    while curr <= end_date:
        date_list.append(curr)
        curr += datetime.timedelta(days=1)
    
    import random
    random.seed(hash(adgroup_id) + int(start_date.strftime("%Y%m%d")))
    
    rows = []
    for d in date_list:
        imp = random.randint(4000, 15000)
        clk = random.randint(80, 350)
        cost = clk * random.randint(500, 900)
        ctr = round((clk / imp) * 100, 2) if imp > 0 else 0.0
        cpc = int(cost / clk) if clk > 0 else 0
        
        rows.append({
            "날짜": d.strftime("%Y-%m-%d"),
            "노출수": imp,
            "클릭수": clk,
            "클릭률(%)": ctr,
            "평균 CPC": cpc,
            "총비용": cost
        })
    return pd.DataFrame(rows)


# ==========================================
# [네이버 API 통신 모듈]
# ==========================================
def fetch_campaigns(customer_id, api_key, secret_key, ad_type):
    BASE_URL = "https://api.searchad.naver.com"
    uri = "/ncc/campaigns"
    headers = get_header("GET", uri, api_key, secret_key, customer_id)
    response = requests.get(f"{BASE_URL}{uri}", headers=headers)
    if response.status_code != 200:
        st.error(f"캠페인 데이터 연동에 실패했습니다. (HTTP {response.status_code})")
        return []
    
    campaigns = response.json()
    type_mapping = {'검색광고': 'WEB_SITE', '플레이스광고': 'PLACE', '파워컨텐츠광고': 'POWER_CONTENT'}
    target_type = type_mapping.get(ad_type, 'WEB_SITE')
    return [c for c in campaigns if c.get('campaignTp') == target_type]

def fetch_adgroups(customer_id, api_key, secret_key, campaign_id):
    BASE_URL = "https://api.searchad.naver.com"
    uri = "/ncc/adgroups"
    params = {'nccCampaignId': campaign_id}
    headers = get_header("GET", uri, api_key, secret_key, customer_id)
    response = requests.get(f"{BASE_URL}{uri}", params=params, headers=headers)
    if response.status_code != 200:
        st.error(f"광고그룹 데이터 연동에 실패했습니다. (HTTP {response.status_code})")
        return []
    return response.json()

def fetch_daily_stats(customer_id, api_key, secret_key, adgroup_id, start_date, end_date):
    BASE_URL = "https://api.searchad.naver.com"
    uri = "/stats"
    # 상세 데이터 조회를 위해 단일 광고그룹 ID('id')와 일자별 분리 파라미터('timeIncrement': '1')를 제공합니다.
    params = {
        'id': adgroup_id,
        'fields': '["impCnt","clkCnt","ctr","cpc","salesAmt"]',
        'timeRange': f'{{"since":"{start_date}","until":"{end_date}"}}',
        'timeIncrement': '1'
    }
    headers = get_header("GET", uri, api_key, secret_key, customer_id)
    response = requests.get(f"{BASE_URL}{uri}", params=params, headers=headers)
    if response.status_code != 200:
        st.error(f"일자별 상세 데이터 연동 실패 (HTTP {response.status_code})")
        return None
        
    stats_json = response.json()
    data_rows = []
    
    if 'data' in stats_json:
        for stat in stats_json['data']:
            dt = stat.get('date', '')
            imp = int(stat.get('impCnt', 0))
            clk = int(stat.get('clkCnt', 0))
            ctr = float(stat.get('ctr', 0.0))
            cpc = int(stat.get('cpc', 0))
            cost = int(stat.get('salesAmt', 0))
            
            data_rows.append({
                "날짜": dt,
                "노출수": imp,
                "클릭수": clk,
                "클릭률(%)": ctr,
                "평균 CPC": cpc,
                "총비용": cost
            })
            
    if data_rows:
        return pd.DataFrame(data_rows)
    return None


# ==========================================
# [사용자 레이아웃 구성]
# ==========================================
st.subheader("인하우스 마케팅 주간 데이터 추출기")
st.caption("사이드바에 API 정보를 먼저 입력하면, 해당 계정에 맞는 광고 캠페인 및 광고그룹 선택창이 단계별로 드러납니다.")

# 사이드바 입력창 세팅
st.sidebar.markdown("### 🔑 API 계정 인증 정보")
secret_customer_id = st.secrets.get("CUSTOMER_ID", "")
secret_api_key = st.secrets.get("API_KEY", "")
secret_secret_key = st.secrets.get("SECRET_KEY", "")

input_customer_id = st.sidebar.text_input("CUSTOMER_ID", value=secret_customer_id, placeholder="예: 1234567")
input_api_key = st.sidebar.text_input("액세스 라이선스 (API KEY)", value=secret_api_key, type="password", placeholder="Access Key")
input_secret_key = st.sidebar.text_input("비밀키 (SECRET_KEY)", value=secret_secret_key, type="password", placeholder="Secret Key")

# 필수 인증 정보 검사
has_keys = (input_customer_id != "") and (input_api_key != "") and (input_secret_key != "")

is_test_mode = False

# ⚠️ [동작 제어] 키 정보가 채워져 있지 않다면 메인 화면을 가로막고 입력을 유도합니다.
if not has_keys:
    st.info("👈 왼쪽 사이드바에 API 키 정보 3가지를 정확히 채워 넣어 주세요.")
    
    # 가상으로 동작 방식을 빠르게 테스트할 수 있는 보조 장치
    is_test_mode = st.checkbox("⚙️ 테스트 모드로 화면 먼저 써보기 (네이버 API 인증 정보가 없을 시 체크)")
    if not is_test_mode:
        st.stop()  # 키가 없고 테스트 모드도 체크하지 않았다면 여기서 정지합니다.

st.markdown("---")

# 📅 조회 날짜 입력 영역 (조회 주간 설정)
col_date1, col_date2 = st.columns(2)
with col_date1:
    start_date = st.date_input("조회 시작일 (월요일 권장)", value=last_monday)
with col_date2:
    end_date = st.date_input("조회 종료일 (일요일 권장)", value=last_sunday)

formatted_start = start_date.strftime("%Y-%m-%d")
formatted_end = end_date.strftime("%Y-%m-%d")

# 🛠️ [조건 제어] API 키 입력 시에만 활성화되는 순차 필터링 영역
st.markdown("### 🗂️ 광고 구성 단계별 선택")

# 1. 광고 유형 선택
selected_ad_type = st.selectbox("1. 광고그룹 유형을 선택해 주세요.", ['검색광고', '플레이스광고', '파워컨텐츠광고'])

# 2. 캠페인 조회 및 선택
with st.spinner("해당 유형의 캠페인 목록을 가져오는 중..."):
    if is_test_mode:
        campaign_list = get_mock_campaigns(selected_ad_type)
    else:
        campaign_list = fetch_campaigns(input_customer_id, input_api_key, input_secret_key, selected_ad_type)

if not campaign_list:
    st.warning("⚠️ 해당 광고 유형에 활성화된 캠페인이 존재하지 않습니다.")
    st.stop()

# 셀렉트박스 편의를 위해 매핑 사전 구성
camp_options = {c['nccCampaignId']: c['name'] for c in campaign_list}
selected_camp_id = st.selectbox("2. 캠페인을 지정해 주세요.", options=list(camp_options.keys()), format_func=lambda x: camp_options[x])

# 3. 광고그룹 조회 및 선택
with st.spinner("지정된 캠페인 하위의 광고그룹 목록을 가져오는 중..."):
    if is_test_mode:
        adgroup_list = get_mock_adgroups(selected_camp_id)
    else:
        adgroup_list = fetch_adgroups(input_customer_id, input_api_key, input_secret_key, selected_camp_id)

if not adgroup_list:
    st.warning("⚠️ 선택하신 캠페인 하위에 광고그룹이 한 개도 생성되어 있지 않습니다.")
    st.stop()

# 광고그룹 매핑 사전 구성
adg_options = {g['nccAdgroupId']: g['name'] for g in adgroup_list}
selected_adg_id = st.selectbox("3. 분석할 상세 광고그룹을 지정해 주세요.", options=list(adg_options.keys()), format_func=lambda x: adg_options[x])

st.markdown("###")

# ==========================================
# [실행] 월요일~일요일 일별 상세 성과 및 주간 종합 데이터 도출
# ==========================================
if st.button("📊 상세데이터 가져오기"):
    with st.spinner("일별 통계 데이터셋을 계산하고 있습니다..."):
        if is_test_mode:
            raw_df = get_mock_daily_stats(selected_adg_id, start_date, end_date)
        else:
            raw_df = fetch_daily_stats(
                input_customer_id, input_api_key, input_secret_key, 
                selected_adg_id, formatted_start, formatted_end
            )
            
        if raw_df is not None and not raw_df.empty:
            # 월요일 ~ 일요일 성과 총합계(Sum) 행 생성 연산
            total_imp = raw_df["노출수"].sum()
            total_clk = raw_df["클릭수"].sum()
            total_cost = raw_df["총비용"].sum()
            
            # 종합 클릭률 및 종합 평균 CPC 산출
            total_ctr = round((total_clk / total_imp) * 100, 2) if total_imp > 0 else 0.0
            total_cpc = int(total_cost / total_clk) if total_clk > 0 else 0
            
            # 합계 데이터프레임 구조 생성
            sum_row = pd.DataFrame([{
                "날짜": "합계",
                "노출수": total_imp,
                "클릭수": total_clk,
                "클릭률(%)": total_ctr,
                "평균 CPC": total_cpc,
                "총비용": total_cost
            }])
            
            # 일주일 지표 바로 밑단에 합계 행 병합 처리
            final_report_df = pd.concat([raw_df, sum_row], ignore_index=True)
            
            # 가독성을 위해 스트림릿 표 컴포넌트로 데이터 반환
            st.dataframe(final_report_df, use_container_width=True)
            
            st.success("✅ 상세 조회가 정상 처리되었습니다! 위 테이블의 행 데이터를 긁어 복사한 뒤 엑셀 시트에 바로 붙여넣으실 수 있습니다.")
        else:
            st.error("데이터 통신에 문제가 발생하였거나 지정된 날짜 범위 내에 성과 이력이 확인되지 않습니다.")
