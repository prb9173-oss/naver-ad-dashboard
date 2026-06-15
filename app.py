# 필요한 라이브러리를 불러옵니다.
import streamlit as st  # 웹 앱 개발을 위한 스트림릿 라이브러리
import datetime  # 날짜 계산을 위한 라이브러리
import time  # API 요청 시간 기록을 위한 라이브러리
import hmac  # 네이버 API 서명 생성을 위한 HMAC 알고리즘 라이브러리
import hashlib  # 해시 생성을 위한 라이브러리
import base64  # 문자열 인코딩을 위한 라이브러리
import requests  # HTTP API 요청을 보내기 위한 라이브러리
import pandas as pd  # 데이터를 표 형태로 처리하기 위한 판다스 라이브러리

# ==========================================
# [디자인 정의] 미니멀 & 연노랑(Pale Yellow) 포인트 CSS 설정
# ==========================================
# 깔끔한 화이트 바탕에 시각적 피로를 줄인 은은한 연노랑(#FFFDE7, #FFF9C4) 포인트 컬러를 적용합니다.
st.set_page_config(page_title="인하우스 마케팅 주간 데이터 추출기", layout="centered")

st.markdown("""
    <style>
    /* 웹 앱의 기본 배경을 부드러운 화이트 톤으로 지정 */
    .stApp {
        background-color: #FFFFFF;
    }
    
    /* 사이드바 영역의 배경 색상 조정 */
    section[data-testid="stSidebar"] {
        background-color: #FAFAFA;
        border-right: 1px solid #E0E0E0;
    }
    
    /* [데이터 불러오기] 버튼의 디자인 - 연노랑 포인트 및 볼드 처리 */
    div.stButton > button {
        background-color: #FFFDE7 !important; /* 은은한 연노랑 배경 */
        color: #333333 !important; /* 어두운 차콜색 글자 */
        border: 1px solid #E0E0E0 !important; /* 연한 테두리 */
        border-radius: 6px !important; /* 부드러운 둥근 모서리 */
        padding: 0.6rem 1.5rem !important;
        font-weight: bold !important; /* 글자 두껍게 */
        transition: all 0.3s ease;
    }
    
    /* 버튼에 마우스를 올렸을 때(Hover) 조금 더 선명한 연노랑으로 변경 */
    div.stButton > button:hover {
        background-color: #FFF9C4 !important;
        border: 1px solid #BDBDBD !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); /* 미세한 그림자 효과 */
    }
    
    /* 텍스트 입력창들의 경계선 색상을 통일하여 차분한 느낌 부여 */
    .stTextInput>div>div>input {
        border-color: #E0E0E0 !important;
    }
    </style>
""", unsafe_allow_html=True)


# ==========================================
# [날짜 계산] 지난주 월요일 ~ 지난주 일요일 자동 계산
# ==========================================
# 오늘 날짜를 가져옵니다.
today = datetime.date.today()

# 오늘 요일을 정수로 구합니다 (월요일=0, 화요일=1, ..., 일요일=6)
current_weekday = today.weekday()

# 지난주 월요일 계산: 오늘 날짜에서 (오늘의 요일 번호 + 7일)을 뺍니다.
# 예: 오늘이 월요일(0)이면 7일 전, 수요일(2)이면 9일 전으로 이동해 지난주 월요일을 정확히 찾습니다.
last_monday = today - datetime.timedelta(days=current_weekday + 7)

# 지난주 일요일 계산: 지난주 월요일로부터 6일 후를 지정합니다.
last_sunday = last_monday + datetime.timedelta(days=6)


# ==========================================
# [네이버 검색광고 API 인증 함수]
# ==========================================
# 네이버 검색광고 API 호출을 위해 매 요청마다 고유한 HMAC-SHA256 서명을 생성합니다.
def make_signature(timestamp, method, uri, secret_key):
    # 타임스탬프, HTTP 메소드, 요청 URI를 마침표(.)로 결합하여 메시지를 만듭니다.
    message = f"{timestamp}.{method}.{uri}"
    # 비밀키와 메시지를 사용해 SHA256 해시 기반의 HMAC 서명을 생성합니다.
    hash_obj = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    # 서명 값을 Base64 문자열로 인코딩하여 반환합니다.
    return base64.b64encode(hash_obj.digest()).decode("utf-8")

# API 호출에 필요한 공통 헤더 정보를 반환하는 함수입니다.
def get_header(method, uri, api_key, secret_key, customer_id):
    # 밀리초 단위의 현재 타임스탬프를 문자열로 만듭니다.
    timestamp = str(int(time.time() * 1000))
    # 서명을 생성합니다.
    signature = make_signature(timestamp, method, uri, secret_key)
    # 필수 규격에 맞춰 헤더 딕셔너리를 구성합니다.
    return {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Timestamp': timestamp,
        'X-API-KEY': api_key,
        'X-Customer': str(customer_id),
        'X-Signature': signature
    }


# ==========================================
# [샘플 데이터 정의] API 키가 없거나 에러 발생 시 노출되는 백업 데이터
# ==========================================
def get_mock_data(ad_type):
    # 선택된 탭(광고 유형)에 맞춰 현실적인 모의 성과 데이터를 반환합니다.
    if ad_type == '검색광고':
        data = [
            {"캠페인명(또는 키워드)": "[검색] 브랜드_공식_키워드", "노출수": 150230, "클릭수": 4520, "클릭률(%)": 3.01, "CPC": 520, "총비용": 2350400},
            {"캠페인명(또는 키워드)": "[검색] 핵심제품_키워드_노출", "노출수": 84500, "클릭수": 1280, "클릭률(%)": 1.51, "CPC": 840, "총비용": 1075200},
            {"캠페인명(또는 키워드)": "[검색] 카테고리_경쟁사_대비", "노출수": 42100, "클릭수": 340, "클릭률(%)": 0.81, "CPC": 1200, "총비용": 408000},
        ]
    elif ad_type == '플레이스광고':
        data = [
            {"캠페인명(또는 키워드)": "[플레이스] 본점_주변상권_검색", "노출수": 52300, "클릭수": 1040, "클릭률(%)": 1.99, "CPC": 450, "총비용": 468000},
            {"캠페인명(또는 키워드)": "[플레이스] 가맹점_지역명_노출", "노출수": 38400, "클릭수": 812, "클릭률(%)": 2.11, "CPC": 420, "총비용": 341040},
        ]
    else:  # 파워컨텐츠광고
        data = [
            {"캠페인명(또는 키워드)": "[파워컨텐츠] 블로그_정보성_리뷰배포", "노출수": 24100, "클릭수": 510, "클릭률(%)": 2.12, "CPC": 650, "총비용": 331500},
            {"캠페인명(또는 키워드)": "[파워컨텐츠] 카페_사용기_확산", "노출수": 18200, "클릭수": 320, "클릭률(%)": 1.76, "CPC": 610, "총비용": 195200},
        ]
    # 사용자가 바로 드래그 복사할 수 있도록 데이터프레임으로 변환하여 돌려줍니다.
    return pd.DataFrame(data)


# ==========================================
# [데이터 불러오기 로직] API 호출 및 데이터 가공
# ==========================================
def fetch_naver_ad_data(customer_id, api_key, secret_key, start_date, end_date, ad_type):
    # 입력값 중 하나라도 없으면 샘플 데이터를 보여주도록 설정합니다.
    if not customer_id or not api_key or not secret_key:
        st.info("💡 사이드바에 API 키 정보가 입력되지 않아 샘플(예시) 데이터를 표시합니다. 키를 입력하면 실제 데이터가 조회됩니다.")
        return get_mock_data(ad_type)
    
    try:
        # 네이버 검색광고 API 기본 주소
        BASE_URL = "https://api.searchad.naver.com"
        
        # 1단계: 전체 캠페인 목록을 가져와서 이름 정보를 획득합니다.
        campaign_uri = "/ncc/campaigns"
        headers = get_header("GET", campaign_uri, api_key, secret_key, customer_id)
        
        response = requests.get(f"{BASE_URL}{campaign_uri}", headers=headers)
        
        # 통신에 실패했다면 에러를 발생시키고 샘플 데이터로 넘어갑니다.
        if response.status_code != 200:
            st.warning(f"⚠️ 네이버 API 연결에 실패하였습니다. (에러 코드: {response.status_code}) 임시 데이터를 불러옵니다.")
            return get_mock_data(ad_type)
            
        campaigns = response.json()
        
        # 선택한 탭 이름에 따라 네이버 시스템상의 캠페인 유형(WEB, PLACE, POWER_CONTENT 등)을 매핑합니다.
        type_mapping = {
            '검색광고': 'WEB',
            '플레이스광고': 'PLACE',
            '파워컨텐츠광고': 'POWER_CONTENT'
        }
        target_type = type_mapping.get(ad_type, 'WEB')
        
        # 해당 유형에 일치하는 캠페인만 골라냅니다.
        filtered_campaigns = [c for c in campaigns if c.get('campaignTp') == target_type]
        
        # 필터링된 결과가 전혀 없다면 안내를 띄우고 샘플 데이터를 보여줍니다.
        if not filtered_campaigns:
            st.info(f"선택한 '{ad_type}' 유형의 활성화된 캠페인이 확인되지 않아 샘플 데이터를 표시합니다.")
            return get_mock_data(ad_type)
            
        data_rows = []
        
        # 2단계: 필터링된 각 캠페인에 대하여 지정된 날짜 범위의 통계 데이터를 조회합니다.
        for camp in filtered_campaigns:
            camp_id = camp.get('nccCampaignId')
            camp_name = camp.get('name')
            
            stats_uri = "/stats"
            # stats API의 매개변수를 세팅합니다. fields 파라미터는 엄격히 규정된 JSON 문자열 형태여야 합니다.
            params = {
                'ids': camp_id,
                'fields': '["impCnt","clkCnt","ctr","cpc","salesAmt"]',
                'timeRange': f'{{"since":"{start_date}","until":"{end_date}"}}'
            }
            
            stats_headers = get_header("GET", stats_uri, api_key, secret_key, customer_id)
            stats_response = requests.get(f"{BASE_URL}{stats_uri}", params=params, headers=stats_headers)
            
            if stats_response.status_code == 200:
                stats_json = stats_response.json()
                # 통계 데이터가 응답 안에 안전하게 있는지 확인합니다.
                if 'data' in stats_json and len(stats_json['data']) > 0:
                    stat = stats_json['data'][0]
                    
                    # 수치 데이터를 파싱합니다 (값이 없는 경우를 대비한 기본값 설정).
                    imp = int(stat.get('impCnt', 0)) # 노출수
                    clk = int(stat.get('clkCnt', 0)) # 클릭수
                    ctr = float(stat.get('ctr', 0.0)) # 클릭률 (%)
                    cpc = int(stat.get('cpc', 0)) # 클릭당비용 (CPC)
                    cost = int(stat.get('salesAmt', 0)) # 총 소요 비용
                    
                    # 엑셀 보고서에 붙여넣기 좋게 가공하여 리스트에 추가합니다.
                    data_rows.append({
                        "캠페인명(또는 키워드)": camp_name,
                        "노출수": imp,
                        "클릭수": clk,
                        "클릭률(%)": ctr,
                        "CPC": cpc,
                        "총비용": cost
                    })
                    
        # 수집된 데이터 행이 있다면 정돈하여 반환합니다.
        if data_rows:
            df = pd.DataFrame(data_rows)
            # 사용자가 요청한 칼럼 순서대로 정렬합니다.
            cols = ["캠페인명(또는 키워드)", "노출수", "클릭수", "클릭률(%)", "CPC", "총비용"]
            return df[cols]
        else:
            st.info("선택한 날짜 범위 내에 광고 집행 실적이 존재하지 않아 샘플 데이터를 표시합니다.")
            return get_mock_data(ad_type)
            
    except Exception as e:
        # 가공 과정에서 예상하지 못한 오류가 발생해도 시스템이 꺼지지 않도록 샘플 데이터를 보장합니다.
        st.error(f"데이터 정합 오류가 감지되어 샘플 데이터를 대신 출력합니다. (내용: {str(e)})")
        return get_mock_data(ad_type)


# ==========================================
# [사용자 인터페이스 (UI) 레이아웃 구성]
# ==========================================

# 1. 메인 타이틀 영역 설정 (미니멀하고 단정하게 구성)
st.subheader("인하우스 마케팅 주간 데이터 추출기")
st.caption("네이버 검색광고 API를 사용해 쉽고 빠르게 주간 성과를 수집하고 엑셀에 복사해보세요.")

# 2. 사이드바 영역 구성 (계정 접속 및 API 인증 정보 입력)
st.sidebar.markdown("### 🔑 API 계정 인증 정보")
st.sidebar.caption("네이버 검색광고 시스템 > 도구 > API 사용관리 탭에서 확인 가능한 키 값을 입력해 주세요.")

input_customer_id = st.sidebar.text_input("CUSTOMER_ID", placeholder="예: 1234567")
input_api_key = st.sidebar.text_input("액세스 라이선스 (API KEY)", type="password", placeholder="발급받은 Access Key")
input_secret_key = st.sidebar.text_input("비밀키 (SECRET_KEY)", type="password", placeholder="발급받은 Secret Key")

# 3. 메인 화면 - 날짜 필터 영역 구성
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    # 기본값으로 이전 주 월요일이 들어가도록 입력 상자를 만듭니다.
    start_date = st.date_input("조회 시작일", value=last_monday)

with col2:
    # 기본값으로 이전 주 일요일이 들어가도록 입력 상자를 만듭니다.
    end_date = st.date_input("조회 종료일", value=last_sunday)

# 날짜 포맷팅을 네이버 API 표준 규격인 'YYYY-MM-DD' 문자열로 변환합니다.
formatted_start_date = start_date.strftime("%Y-%m-%d")
formatted_end_date = end_date.strftime("%Y-%m-%d")

# 4. 메인 화면 - 광고 유형 탭 분할
tabs = st.tabs(['검색광고', '플레이스광고', '파워컨텐츠광고'])

# 각 탭에 맞게 불러오기 액션을 매핑합니다.
for idx, tab_name in enumerate(['검색광고', '플레이스광고', '파워컨텐츠광고']):
    with tabs[idx]:
        st.write(f"📊 **{tab_name}** 성과 통계 데이터 리포트")
        
        # 버튼을 누르면 API 호출이 시작되고 화면에 반영됩니다.
        if st.button(f"{tab_name} 데이터 불러오기", key=f"btn_{idx}"):
            with st.spinner("네이버 검색광고 서버에서 데이터를 수집하는 중입니다..."):
                # API 호출 함수를 실행하고 결과 데이터를 받아옵니다.
                result_df = fetch_naver_ad_data(
                    customer_id=input_customer_id,
                    api_key=input_api_key,
                    secret_key=input_secret_key,
                    start_date=formatted_start_date,
                    end_date=formatted_end_date,
                    ad_type=tab_name
                )
                
                # 사용자가 마우스로 간편히 긁어 갈 수 있도록 표(st.dataframe) 형태로 데이터를 뿌려줍니다.
                # use_container_width=True 옵션으로 공간에 맞춰 깔끔하게 배치합니다.
                st.dataframe(result_df, use_container_width=True)
                
                # 원클릭으로 손쉽게 복사해서 엑셀에 수치 형식 그대로 붙여 넣을 수 있도록 팁을 제공합니다.
                st.success("✅ 조회가 완료되었습니다! 위의 표 전체를 드래그하거나 우측 상단의 다운로드 기능으로 엑셀에 바로 붙여넣기 하실 수 있습니다.")

st.markdown("---")
st.caption("⚠️ API 호출 시 네트워크 상태 또는 네이버 광고 플랫폼의 일시적 순위 집계 지연으로 인해 수치 조회에 수 초 가량 소요될 수 있습니다.")