import streamlit as st
import datetime
import time
import hmac
import hashlib
import base64
import requests
import pandas as pd

# ==========================================
# [초기화] 광고 ID(계정) 프로필 저장을 위한 세션 상태 세팅
# ==========================================
# 처음 웹페이지에 접속했을 때 예시용 테스트 프로필 2개를 기본 탑재합니다.
if 'ad_accounts' not in st.session_state:
    st.session_state['ad_accounts'] = {
        "가상 계정 A (검색광고 테스트용)": {
            "customer_id": "MOCK_CUSTOMER_SEARCH",
            "api_key": "mock_api_key_111111",
            "secret_key": "mock_secret_key_111111"
        },
        "가상 계정 B (플레이스 테스트용)": {
            "customer_id": "MOCK_CUSTOMER_PLACE",
            "api_key": "mock_api_key_222222",
            "secret_key": "mock_secret_key_222222"
        }
    }

# ==========================================
# [디자인 정의] 배경은 밝게, 선택상자 텍스트 겹침 완화 (CSS)
# ==========================================
st.set_page_config(page_title="인하우스 마케팅 주간 데이터 추출기", layout="centered")

st.markdown("""
    <style>
    /* 메인 화면 전체 화이트 배경 강제 */
    .stApp {
        background-color: #FFFFFF !important;
    }
    
    /* 사이드바 영역의 은은한 연회색 지정 */
    section[data-testid="stSidebar"] {
        background-color: #F8F9FA !important;
        border-right: 1px solid #E0E0E0 !important;
    }
    
    /* 텍스트 요소들 선명한 검정색 지정 */
    p, span, label, h1, h2, h3, h4, h5, h6, li, strong, th, td {
        color: #000000 !important;
    }
    
    /* 인풋 라벨 영역 글자 강조 */
    .stTextInput label p, .stSelectbox label p, .stDateInput label p, [data-testid="stSidebar"] label p {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    
    /* 셀렉트박스 드롭다운 팝업 레이아웃 및 텍스트 겹침 방지 */
    div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 1px solid #CCCCCC !important;
    }
    div[data-baseweb="popover"] {
        background-color: #FFFFFF !important;
    }
    div[role="listbox"] div, li[role="option"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    li[role="option"]:hover, div[role="option"]:hover {
        background-color: #FFF9C4 !important;
        color: #000000 !important;
    }
    
    /* 은은한 연노랑(#FFFDE7) 컬러 포인트를 준 액션 버튼 */
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
current_weekday = today.weekday()  # 월요일=0, ... 일요일=6
last_monday = today - datetime.timedelta(days=current_weekday + 7)  # 지난주 월요일
last_sunday = last_monday + datetime.timedelta(days=6)  # 지난주 일요일


# ==========================================
# [인증] 네이버 검색광고 API HMAC 서명 빌더
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
# [가상 데이터 공급] 시연용 흐름을 위한 모의 데이터셋 생성기
# ==========================================
def get_mock_campaigns(ad_type):
    if ad_type == '검색광고':
        return [{"nccCampaignId": "camp-sh-01", "name": "[검색] 브랜드_공식_캠페인"},
                {"nccCampaignId": "camp-sh-02", "name": "[검색] 파워링크_제품홍보"}]
    elif ad_type == '플레이스광고':
        return [{"nccCampaignId": "camp-pl-01", "name": "[플레이스] 강남직영점_스마트플레이스"}]
    else:
        return [{"nccCampaignId": "camp-pc-01", "name": "[파워컨텐츠] 블로그_정보제공_캠페인"}]

def get_mock_adgroups(campaign_id):
    if campaign_id == "camp-sh-01":
        return [{"nccAdgroupId": "grp-sh-01-a", "name": "PC_브랜드명_검색그룹"},
                {"nccAdgroupId": "grp-sh-01-b", "name": "모바일_브랜드명_검색그룹"}]
    elif campaign_id == "camp-sh-02":
        return [{"nccAdgroupId": "grp-sh-02-a", "name": "제품군_키워드확장_그룹"}]
    elif campaign_id == "camp-pl-01":
        # 플레이스 광고그룹에는 가상의 기본 입찰가(bidAmt) 필드를 심어 둡니다.
        return [{"nccAdgroupId": "grp-pl-01-a", "name": "지역상권_강남역_플레이스", "bidAmt": 1250}]
    else:
        return [{"nccAdgroupId": "grp-pc-01-a", "name": "리뷰체험단_매칭_광고그룹"}]

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
    keywords = ["마케팅 대행사", "데이터 분석", "광고 가이드", "보고서 엑셀", "스마트스토어 홍보", 
                "주간 성과표", "블로그마케팅", "지역 소상공인 광고", "인하우스 마케터"]
    
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
    df = df.sort_values(by="클릭수", ascending=False).head(10).reset_index(drop=True)
    return df


# ==========================================
# [네이버 API 연동 엔진]
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

def fetch_keyword_stats(customer_id, api_key, secret_key, adgroup_id, start_date, end_date):
    BASE_URL = "https://api.searchad.naver.com"
    kw_list_uri = "/ncc/keywords"
    kw_params = {'nccAdgroupId': adgroup_id}
    kw_headers = get_header("GET", kw_list_uri, api_key, secret_key, customer_id)
    kw_response = requests.get(f"{BASE_URL}{kw_list_uri}", params=kw_params, headers=kw_headers)
    
    if kw_response.status_code != 200:
        return None
        
    keywords = kw_response.json()
    if not keywords:
        return None
        
    kw_ids = [k.get('nccKeywordId') for k in keywords]
    kw_map = {k.get('nccKeywordId'): k.get('keyword') for k in keywords}
    
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
        df = df.sort_values(by="클릭수", ascending=False).head(10).reset_index(drop=True)
        return df
    return None


# ==========================================
# [사이드바 설계] 프로필 선택 및 동적 API 키 로드
# ==========================================
st.sidebar.markdown("### 📁 1. 광고 ID(계정) 선택")

# 현재 등록되어 있는 계정 이름 목록 추출
available_accounts = list(st.session_state['ad_accounts'].keys())

# 사이드바 최상단에 계정 선택 상자 배치
selected_profile = st.sidebar.selectbox(
    "관리 중인 계정을 선택하시면 저장된 API 키를 자동으로 불러옵니다.", 
    options=available_accounts
)

# 선택된 계정의 크리덴셜 정보 가져오기
active_keys = st.session_state['ad_accounts'][selected_profile]

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔑 2. API 인증 키 관리")

# 계정 전환 시 기본 입력값이 선택된 프로필 정보로 동적 연동됩니다.
input_customer_id = st.sidebar.text_input("CUSTOMER_ID", value=active_keys["customer_id"])
input_api_key = st.sidebar.text_input("액세스 라이선스 (API KEY)", value=active_keys["api_key"], type="password")
input_secret_key = st.sidebar.text_input("비밀키 (SECRET_KEY)", value=active_keys["secret_key"], type="password")

st.sidebar.markdown("---")
st.sidebar.markdown("### ➕ 3. 새로운 광고 ID(계정) 등록")

# 실무 대행 업무 시 마케터가 신규 계정을 등록하여 저장할 수 있는 컴포넌트
reg_name = st.sidebar.text_input("신규 계정 별칭", placeholder="예: 인하우스 패션몰 C")

if st.sidebar.button("💾 위 정보로 광고 ID 등록"):
    if reg_name and input_customer_id and input_api_key and input_secret_key:
        # 입력한 정보를 기반으로 로컬 세션 사전에 등록
        st.session_state['ad_accounts'][reg_name] = {
            "customer_id": input_customer_id,
            "api_key": input_api_key,
            "secret_key": input_secret_key
        }
        st.sidebar.success(f"'{reg_name}' 계정이 광고 ID 목록에 추가되었습니다!")
        time.sleep(0.5)
        st.rerun()  # 화면을 새로고침하여 상단 셀렉트박스에 즉시 반영시킵니다.
    else:
        st.sidebar.error("모든 칸과 별칭을 채운 후 저장을 눌러주세요.")


# ==========================================
# [메인 화면 로직 및 입찰가 정보 분기]
# ==========================================
st.subheader("인하우스 마케팅 주간 데이터 추출기")
st.caption("사이드바에서 광고 ID를 생성하여 관리할 수 있으며, 플레이스 광고 조회 시 입찰가 맞춤형 지표를 확인합니다.")

# 계정 키 안에 'mock' 단어가 포함되어 있거나 비어 있다면 자동으로 가상 데이터 시뮬레이션 모드를 가동합니다.
is_test_mode = ("mock" in input_customer_id.lower()) or (input_customer_id == "")

# 조회 날짜 수립
col_date1, col_date2 = st.columns(2)
with col_date1:
    start_date = st.date_input("조회 시작일 (월요일 권장)", value=last_monday)
with col_date2:
    end_date = st.date_input("조회 종료일 (일요일 권장)", value=last_sunday)

formatted_start = start_date.strftime("%Y-%m-%d")
formatted_end = end_date.strftime("%Y-%m-%d")

# 광고 셀렉터 배치
st.markdown("### 🗂&nbsp;&nbsp;광고 구성 단계별 선택")

selected_ad_type = st.selectbox("1. 광고그룹 유형을 선택해 주세요.", ['검색광고', '플레이스광고', '파워컨텐츠광고'])

# 캠페인 동적 조회
if is_test_mode:
    campaign_list = get_mock_campaigns(selected_ad_type)
else:
    campaign_list = fetch_campaigns(input_customer_id, input_api_key, input_secret_key, selected_ad_type)

if not campaign_list:
    st.warning("⚠️ 선택하신 유형에 부합하는 캠페인이 확인되지 않습니다.")
    st.stop()

camp_options = {c['nccCampaignId']: c['name'] for c in campaign_list}
selected_camp_id = st.selectbox("2. 캠페인을 지정해 주세요.", options=list(camp_options.keys()), format_func=lambda x: camp_options[x])

# 광고그룹 동적 조회
if is_test_mode:
    adgroup_list = get_mock_adgroups(selected_camp_id)
else:
    adgroup_list = fetch_adgroups(input_customer_id, input_api_key, input_secret_key, selected_camp_id)

if not adgroup_list:
    st.warning("⚠️ 지정된 캠페인 하위에 개설된 광고그룹이 존재하지 않습니다.")
    st.stop()

adg_options = {g['nccAdgroupId']: g['name'] for g in adgroup_list}
selected_adg_id = st.selectbox("3. 상세 광고그룹을 지정해 주세요.", options=list(adg_options.keys()), format_func=lambda x: adg_options[x])


# 💡 [조건부 요구사항] 만약 유형이 '플레이스광고'라면 '평균 광고 노출 입찰가'를 전면 노출합니다.
if selected_ad_type == '플레이스광고':
    # 매치되는 광고그룹 객체 찾기
    matched_adg = next((g for g in adgroup_list if g.get('nccAdgroupId') == selected_adg_id), None)
    if matched_adg:
        # 네이버 플레이스 광고그룹에는 기본 입찰가(bidAmt)를 가져오거나 없으면 기본값 적용
        bid_value = matched_adg.get('bidAmt', 100)
        if is_test_mode and bid_value == 100:
            bid_value = 1350  # 테스트용 시각화 입찰액 보정
            
        st.info(f"📍 **플레이스 광고 특화 지표** | 해당 광고그룹의 평균 광고 노출 입찰가: **{bid_value:,} 원**")

st.markdown("---")

# 실행 제어판 분할
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    show_daily_detail = st.button("📊 일별 상세데이터 가져오기")
with col_btn2:
    show_keyword_rank = st.button("🔑 키워드별 성과(상위 10개) 가져오기")

st.markdown("###")


# ==========================================
# [액션 1] 일별 상세데이터 추출 프로세스
# ==========================================
if show_daily_detail:
    with st.spinner("일자별 집계 성과 데이터를 수집하는 중..."):
        if is_test_mode:
            raw_df = get_mock_daily_stats(selected_adg_id, start_date, end_date)
        else:
            raw_df = fetch_daily_stats(
                input_customer_id, input_api_key, input_secret_key, 
                selected_adg_id, formatted_start, formatted_end
            )
            
        if raw_df is not None and not raw_df.empty:
            # 주간 통계 총합 연산
            total_imp = raw_df["노출수"].sum()
            total_clk = raw_df["클릭수"].sum()
            total_cost = raw_df["총비용"].sum()
            
            total_ctr = round((total_clk / total_imp) * 100, 2) if total_imp > 0 else 0.0
            total_cpc = int(total_cost / total_clk) if total_clk > 0 else 0
            
            sum_row = pd.DataFrame([{
                "날짜": "합계",
                "노출수": total_imp,
                "클릭수": total_clk,
                "클릭률(%)": total_ctr,
                "평균 CPC": total_cpc,
                "총비용": total_cost
            }])
            
            final_report_df = pd.concat([raw_df, sum_row], ignore_index=True)
            
            # 💡 [중앙 정렬 및 천 단위 컴마] 표를 드래그할 때 엑셀로 가장 매끄럽게 호환되도록 구성합니다.
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
            st.success("✅ 조회가 종료되었습니다. 위 행들을 복사하여 엑셀 시트에 바로 입력하실 수 있습니다.")
        else:
            st.error("지정된 날짜 범위 내에 수집 가능한 통계 리포트가 없습니다.")


# ==========================================
# [액션 2] 키워드 상위 10개 실적 추출 프로세스
# ==========================================
if show_keyword_rank:
    with st.spinner("클릭수 우수 핵심 키워드 10종을 분석 중..."):
        if is_test_mode:
            kw_df = get_mock_keyword_stats(selected_adg_id)
        else:
            kw_df = fetch_keyword_stats(
                input_customer_id, input_api_key, input_secret_key, 
                selected_adg_id, formatted_start, formatted_end
            )
            
        if kw_df is not None and not kw_df.empty:
            # 💡 [중앙 정렬 및 천 단위 컴마 적용] 키워드 지표 렌더링
            st.dataframe(
                kw_df,
                use_container_width=True,
                column_config={
                    "키워드명": st.column_config.TextColumn(alignment="center"),
                    "노출수": st.column_config.NumberColumn(alignment="center", format="%,d"),
                    "클릭수": st.column_config.NumberColumn(alignment="center", format="%,d"),
                }
            )
            st.success("✅ 상위 성과 키워드 조회가 완료되었습니다.")
        else:
            st.warning("⚠️ 광고그룹 내에 가용 가능한 검색 키워드 성과 정보가 없습니다.")
