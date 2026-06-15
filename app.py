import streamlit as st
import datetime
import time
import hmac
import hashlib
import base64
import requests
import pandas as pd

# ==========================================
# [디자인 정의] 가독성을 높인 연노랑 포인트 및 완벽한 셀렉트박스 시인성 확보 (CSS)
# ==========================================
st.set_page_config(page_title="인하우스 마케팅 주간 데이터 추출기", layout="centered")

st.markdown("""
    <style>
    /* 1. 전체 컨테이너 배경을 밝은 화이트로 설정 */
    .stApp {
        background-color: #FFFFFF !important;
    }
    
    /* 2. 사이드바 영역의 배경을 연회색으로 처리 */
    section[data-testid="stSidebar"] {
        background-color: #F8F9FA !important;
        border-right: 1px solid #E0E0E0 !important;
    }
    
    /* 3. 불필요한 div 전역 색상 강제를 제거하고, 순수 문자열 요소들만 검정색으로 제어 */
    p, span, label, h1, h2, h3, h4, h5, h6, li, strong, th, td {
        color: #000000 !important;
    }
    
    /* 4. 마크다운 및 캡션 영역 검은색 명시 */
    .stMarkdown, [data-testid="stWidgetLabel"] p, .stCaptionContainer p {
        color: #000000 !important;
        font-weight: 500;
    }
    
    /* 5. 입력폼 제목 글자 강조 */
    .stTextInput label p, .stSelectbox label p, .stDateInput label p, [data-testid="stSidebar"] label p {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    
    /* ⚠️ [중요 수치 변경] 셀렉트박스 및 드롭다운 활성화 시 글자색과 배경색이 겹치지 않게 완전 분리 */
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #CCCCCC !important;
    }
    /* 드롭다운 리스트 팝업 레이어 */
    div[data-baseweb="popover"] {
        background-color: #FFFFFF !important;
    }
    /* 드롭다운 안의 개별 선택지들 */
    div[role="listbox"] div, li[role="option"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    /* 마우스 호버 시에 선택 항목만 은은한 연노랑으로 하이라이트 */
    li[role="option"]:hover, div[role="option"]:hover {
        background-color: #FFF9C4 !important;
        color: #000000 !important;
    }
    
    /* 6. 데이터 추출 실행 단추 스타일 정의 (연노랑 포인트) */
    div.stButton > button {
        background-color: #FFFDE7 !important;
        color: #000000 !important;
        border: 1px solid #C0B090 !important;
        border-radius: 6px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: bold !important;
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #FFF9C4 !important;
        border: 1px solid #888888 !important;
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
# [인증] 네이버 검색광고 API 서명 빌더
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
# [가상 테스트 데이터] API 키 누락 시 원활한 흐름 확인용 백업 모듈
# ==========================================
def get_mock_campaigns(ad_type):
    if ad_type == '검색광고':
        return [{"nccCampaignId": "camp-sh-01", "name": "[검색] 브랜드_공식_캠페인"},
                {"nccCampaignId": "camp-sh-02", "name": "[검색] 메인제품_검색광고"}]
    elif ad_type == '플레이스광고':
        return [{"nccCampaignId": "camp-pl-01", "name": "[플레이스] 강남직영점_홍보"}]
    else:
        return [{"nccCampaignId": "camp-pc-01", "name": "[파워컨텐츠] 리뷰컨텐츠_홍보"}]

def get_mock_adgroups(campaign_id):
    if campaign_id == "camp-sh-01":
        return [{"nccAdgroupId": "grp-sh-01-a", "name": "PC_대표브랜드_광고그룹"},
                {"nccAdgroupId": "grp-sh-01-b", "name": "모바일_대표브랜드_광고그룹"}]
    elif campaign_id == "camp-sh-02":
        return [{"nccAdgroupId": "grp-sh-02-a", "name": "인기상품_카테고리_광고그룹"}]
    elif campaign_id == "camp-pl-01":
        return [{"nccAdgroupId": "grp-pl-01-a", "name": "지역기반_플레이스_광고그룹"}]
    else:
        return [{"nccAdgroupId": "grp-pc-01-a", "name": "리뷰_블로그_광고그룹"}]

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

def get_mock_keyword_stats(adgroup_id):
    import random
    random.seed(hash(adgroup_id))
    
    # 해당 광고그룹 하위에 매핑될 법한 실감 나는 가상 키워드 생성
    keywords = ["마케팅 대행사", "데이터 분석", "광고 가이드", "보고서 엑셀", "스마트스토어 홍보", 
                "주간 성과표", "블로그마케팅", "지역 소상공인 광고", "인하우스 마케터", "파워링크 단가", 
                "매출 증대 비결", "광고 성과 측정", "SNS 마케팅 전략"]
    
    selected_kws = random.sample(keywords, min(len(keywords), 10))
    rows = []
    for kw in selected_kws:
        imp = random.randint(1000, 8000)
        clk = random.randint(5, 120)
        rows.append({
            "키워드명": kw,
            "노출수": imp,
            "클릭수": clk
        })
    df = pd.DataFrame(rows)
    # 클릭수가 높은 순서대로 상위 10개 키워드만 취사선택
    df = df.sort_values(by="클릭수", ascending=False).head(10).reset_index(drop=True)
    return df


# ==========================================
# [네이버 API 통신 모듈]
# ==========================================
def fetch_campaigns(customer_id, api_key, secret_key, ad_type):
    BASE_URL = "https://api.searchad.naver.com"
    uri = "/ncc/campaigns"
    headers = get_header("GET", uri, api_key, secret_key, customer_id)
    response = requests.get(f"{BASE_URL}{uri}", headers=headers)
    if response.status_code != 200:
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
        return []
    return response.json()

def fetch_daily_stats(customer_id, api_key, secret_key, adgroup_id, start_date, end_date):
    BASE_URL = "https://api.searchad.naver.com"
    uri = "/stats"
    params = {
        'id': adgroup_id,
        'fields': '["impCnt","clkCnt","ctr","cpc","salesAmt"]',
        'timeRange': f'{{"since":"{start_date}","until":"{end_date}"}}',
        'timeIncrement': '1'
    }
    headers = get_header("GET", uri, api_key, secret_key, customer_id)
    response = requests.get(f"{BASE_URL}{uri}", params=params, headers=headers)
    if response.status_code != 200:
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

# 광고그룹 내 키워드 목록 및 성과 데이터 조회 API 함수
def fetch_keyword_stats(customer_id, api_key, secret_key, adgroup_id, start_date, end_date):
    BASE_URL = "https://api.searchad.naver.com"
    
    # 1. 광고그룹 하위 키워드 리스트 조회
    kw_list_uri = "/ncc/keywords"
    kw_params = {'nccAdgroupId': adgroup_id}
    kw_headers = get_header("GET", kw_list_uri, api_key, secret_key, customer_id)
    kw_response = requests.get(f"{BASE_URL}{kw_list_uri}", params=kw_params, headers=kw_headers)
    
    if kw_response.status_code != 200:
        return None
        
    keywords = kw_response.json()
    if not keywords:
        return None
        
    # 키워드 매핑 테이블 가공
    kw_ids = [k.get('nccKeywordId') for k in keywords]
    kw_map = {k.get('nccKeywordId'): k.get('keyword') for k in keywords}
    
    # 2. 키워드별 일괄 성과(Stats) 요청 (안정성을 위해 최대 50개씩 나누어 조회)
    stats_uri = "/stats"
    data_rows = []
    chunk_size = 50
    for i in range(0, len(kw_ids), chunk_size):
        chunk_ids = kw_ids[i:i+chunk_size]
        params = {
            'ids': chunk_ids,
            'fields': '["impCnt","clkCnt"]',
            'timeRange': f'{{"since":"{start_date}","until":"{end_date}"}}'
        }
        headers = get_header("GET", stats_uri, api_key, secret_key, customer_id)
        response = requests.get(f"{BASE_URL}{stats_uri}", params=params, headers=headers)
        
        if response.status_code == 200:
            stats_json = response.json()
            if 'data' in stats_json:
                for stat in stats_json['data']:
                    kw_id = stat.get('id')
                    kw_name = kw_map.get(kw_id, "알 수 없는 키워드")
                    imp = int(stat.get('impCnt', 0))
                    clk = int(stat.get('clkCnt', 0))
                    data_rows.append({
                        "키워드명": kw_name,
                        "노출수": imp,
                        "클릭수": clk
                    })
                    
    if data_rows:
        df = pd.DataFrame(data_rows)
        # 클릭수 기준으로 내림차순 정렬하여 상위 10개만 골라내기
        df = df.sort_values(by="클릭수", ascending=False).head(10).reset_index(drop=True)
        return df
    return None


# ==========================================
# [사용자 레이아웃 구성]
# ==========================================
st.subheader("인하우스 마케팅 주간 데이터 추출기")
st.caption("사이드바에 API 계정키를 적은 뒤 광고 대상을 차례대로 지정하시면 표 중앙 정렬 및 가독성이 보완된 리포트를 수집할 수 있습니다.")

# 사이드바 셋업
st.sidebar.markdown("### 🔑 API 계정 인증 정보")
secret_customer_id = st.secrets.get("CUSTOMER_ID", "")
secret_api_key = st.secrets.get("API_KEY", "")
secret_secret_key = st.secrets.get("SECRET_KEY", "")

input_customer_id = st.sidebar.text_input("CUSTOMER_ID", value=secret_customer_id, placeholder="예: 1234567")
input_api_key = st.sidebar.text_input("액세스 라이선스 (API KEY)", value=secret_api_key, type="password", placeholder="Access Key")
input_secret_key = st.sidebar.text_input("비밀키 (SECRET_KEY)", value=secret_secret_key, type="password", placeholder="Secret Key")

has_keys = (input_customer_id != "") and (input_api_key != "") and (input_secret_key != "")

is_test_mode = False

if not has_keys:
    st.info("👈 왼쪽 사이드바에 API 인증 정보 입력이 완료되면 기능들이 순서대로 보입니다.")
    is_test_mode = st.checkbox("⚙️ 테스트 모드로 가상 실행하기 (네이버 API 키가 아직 없을 때 체크)")
    if not is_test_mode:
        st.stop()

st.markdown("---")

# 날짜 조정 영역
col_date1, col_date2 = st.columns(2)
with col_date1:
    start_date = st.date_input("조회 시작일 (월요일 권장)", value=last_monday)
with col_date2:
    end_date = st.date_input("조회 종료일 (일요일 권장)", value=last_sunday)

formatted_start = start_date.strftime("%Y-%m-%d")
formatted_end = end_date.strftime("%Y-%m-%d")

# 광고 선택 패널
st.markdown("### 🗂️ 광고 구성 단계별 선택")

selected_ad_type = st.selectbox("1. 광고그룹 유형을 선택해 주세요.", ['검색광고', '플레이스광고', '파워컨텐츠광고'])

# 캠페인 로드
if is_test_mode:
    campaign_list = get_mock_campaigns(selected_ad_type)
else:
    campaign_list = fetch_campaigns(input_customer_id, input_api_key, input_secret_key, selected_ad_type)

if not campaign_list:
    st.warning("⚠️ 선택하신 광고 유형에 생성된 캠페인이 없습니다.")
    st.stop()

camp_options = {c['nccCampaignId']: c['name'] for c in campaign_list}
selected_camp_id = st.selectbox("2. 캠페인을 지정해 주세요.", options=list(camp_options.keys()), format_func=lambda x: camp_options[x])

# 광고그룹 로드
if is_test_mode:
    adgroup_list = get_mock_adgroups(selected_camp_id)
else:
    adgroup_list = fetch_adgroups(input_customer_id, input_api_key, input_secret_key, selected_camp_id)

if not adgroup_list:
    st.warning("⚠️ 선택하신 캠페인 하위에 설계된 광고그룹이 없습니다.")
    st.stop()

adg_options = {g['nccAdgroupId']: g['name'] for g in adgroup_list}
selected_adg_id = st.selectbox("3. 분석할 상세 광고그룹을 지정해 주세요.", options=list(adg_options.keys()), format_func=lambda x: adg_options[x])

st.markdown("---")

# 기능 구분을 위해 가로 정렬된 2개 단추 제공
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    show_daily_detail = st.button("📊 일별 상세데이터 가져오기")

with col_btn2:
    show_keyword_rank = st.button("🔑 키워드별 성과(상위 10개) 가져오기")

st.markdown("###")

# ==========================================
# [실행 제어 1] 일별 상세데이터 수집 프로세스
# ==========================================
if show_daily_detail:
    with st.spinner("일자별 성과 테이블을 분석하고 있습니다..."):
        if is_test_mode:
            raw_df = get_mock_daily_stats(selected_adg_id, start_date, end_date)
        else:
            raw_df = fetch_daily_stats(
                input_customer_id, input_api_key, input_secret_key, 
                selected_adg_id, formatted_start, formatted_end
            )
            
        if raw_df is not None and not raw_df.empty:
            total_imp = raw_df["노출수"].sum()
            total_clk = raw_df["클릭수"].sum()
            total_cost = raw_df["총비용"].sum()
            
            total_ctr = round((total_clk / total_imp) * 100, 2) if total_imp > 0 else 0.0
            total_cpc = int(total_cost / total_clk) if total_clk > 0 else 0
            
            sum_row = pd.DataFrame([{
                "날짜": "합계",
                "노출수": total_imp,
                "clic_k": total_clk, # 내부 가공 임시 키
                "클릭수": total_clk,
                "클릭률(%)": total_ctr,
                "평균 CPC": total_cpc,
                "총비용": total_cost
            }])
            
            final_report_df = pd.concat([raw_df, sum_row], ignore_index=True)
            
            # 💡 [중앙 배치 및 천 단위 구분 기호] 스트림릿 내장 컬럼 제어로 수식 정렬을 강제 지정합니다.
            st.dataframe(
                final_report_df, 
                use_container_width=True,
                column_config={
                    "날짜": st.column_config.TextColumn(alignment="center"),
                    "노출수": st.column_config.NumberColumn(alignment="center", format="%,d"),
                    "클릭수": st.column_config.NumberColumn(alignment="center", format="%,d"),
                    "클릭률(%)": st.column_config.NumberColumn(alignment="center", format="%.2f%%"),
                    "평균 CPC": st.column_config.NumberColumn(alignment="center", format="%,d 원"),
                    "총비용": st.column_config.NumberColumn(alignment="center", format="%,d 원"),
                }
            )
            st.success("✅ 일별 수집이 종료되었습니다. 표 전체를 드래그하여 엑셀에 붙여넣으실 수 있습니다.")
        else:
            st.error("지정하신 광고그룹 내에 주간 집계 내역이 부존재합니다.")

# ==========================================
# [실행 제어 2] 키워드 상위 10개 지표 수집 프로세스
# ==========================================
if show_keyword_rank:
    with st.spinner("클릭수 기준 상위 10개 핵심 키워드 성과를 추출하고 있습니다..."):
        if is_test_mode:
            kw_df = get_mock_keyword_stats(selected_adg_id)
        else:
            kw_df = fetch_keyword_stats(
                input_customer_id, input_api_key, input_secret_key, 
                selected_adg_id, formatted_start, formatted_end
            )
            
        if kw_df is not None and not kw_df.empty:
            # 💡 [중앙 배치 및 천 단위 구분 기호] 키워드 리포트용 포맷 정렬 처리
            st.dataframe(
                kw_df,
                use_container_width=True,
                column_config={
                    "키워드명": st.column_config.TextColumn(alignment="center"),
                    "노출수": st.column_config.NumberColumn(alignment="center", format="%,d"),
                    "클릭수": st.column_config.NumberColumn(alignment="center", format="%,d"),
                }
            )
            st.success("✅ 클릭수 최우수 키워드 10개 목록 조회가 완료되었습니다.")
        else:
            st.warning("⚠️ 해당 광고그룹 내부에서 수집 가능한 키워드 성과 정보가 없습니다.")
