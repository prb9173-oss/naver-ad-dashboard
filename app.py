import streamlit as st
import datetime
import time
import hmac
import hashlib
import base64
import requests
import pandas as pd
import json  # 계정 정보를 파일에 저장하기 위해 임포트
import os  # 로컬 저장 파일 경로를 체크하기 위해 임포트

# ==========================================
# [데이터 영구 저장] accounts.json 파일 읽기/쓰기 모듈
# ==========================================
ACCOUNTS_FILE = "accounts.json"

def load_accounts():
    default_accounts = {}
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_accounts
    return default_accounts

def save_accounts(accounts):
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=4)
    except Exception as e:
        pass

# 세션 메모리에 영구 저장된 계정 정보를 동기화합니다.
if 'ad_accounts' not in st.session_state:
    st.session_state['ad_accounts'] = load_accounts()

# 입력 폼의 상태를 안정적으로 제어하기 위해 빈 세션 변수를 사전 정의합니다.
if 'input_customer_id' not in st.session_state:
    st.session_state['input_customer_id'] = ""
if 'input_api_key' not in st.session_state:
    st.session_state['input_api_key'] = ""
if 'input_secret_key' not in st.session_state:
    st.session_state['input_secret_key'] = ""
if 'reg_name' not in st.session_state:
    st.session_state['reg_name'] = ""

# 등록 시 알림 제어용 플래그 세션 변수 정의
if 'registration_success' not in st.session_state:
    st.session_state['registration_success'] = ""
if 'registration_error' not in st.session_state:
    st.session_state['registration_error'] = False


# ==========================================
# [콜백] 신규 광고 ID 등록 버튼 핸들러
# ==========================================
def register_account_callback():
    cust_id = st.session_state.get('input_customer_id', '')
    api_k = st.session_state.get('input_api_key', '')
    sec_k = st.session_state.get('input_secret_key', '')
    r_name = st.session_state.get('reg_name', '')
    
    if r_name and cust_id and api_k and sec_k:
        # 데이터 사전에 계정 정보 등록 및 로컬 파일 영구 보존
        st.session_state['ad_accounts'][r_name] = {
            "customer_id": cust_id,
            "api_key": api_k,
            "secret_key": sec_k
        }
        save_accounts(st.session_state['ad_accounts'])
        
        # 저장 성공 후 입력란 상태 클린 초기화
        st.session_state['input_customer_id'] = ""
        st.session_state['input_api_key'] = ""
        st.session_state['input_secret_key'] = ""
        st.session_state['reg_name'] = ""
        st.session_state['selected_profile'] = "광고 ID 선택"
        
        st.session_state['registration_success'] = r_name
    else:
        st.session_state['registration_error'] = True


# ==========================================
# [그리드 엔진] 브라우저 및 엑셀 드래그 복사용 표준 테이블 렌더러
# ==========================================
def convert_df_to_html_grid(df, is_summary_table=False):
    # 엑셀 드래그 복사 시 가운데 정렬 및 쉼표 서식을 안전히 상속하도록 웹 표준 <table> 요소를 빌드합니다.
    html = '<table style="width:100%; border-collapse:collapse; font-family:sans-serif; text-align:center; margin-top:5px; color:#000000 !important; border:1px solid #D0C0A0;">'
    
    # 테이블 구분 헤더(Header) 생성
    # 상단 총 합계표일 때는 좀 더 강조된 연노랑(#FFF9C4) 음영을 제공합니다.
    header_color = "#FFF9C4" if is_summary_table else "#FFFDE7"
    html += f'<thead><tr style="background-color:{header_color}; border-bottom:2px solid #CCCCCC; font-weight:bold; height:36px;">'
    for col in df.columns:
        html += f'<th style="padding:10px; border:1px solid #E0E0E0; color:#000000 !important; font-size:14px;">{col}</th>'
    html += '</tr></thead><tbody>'
    
    # 데이터 행(Rows) 렌더링 루프
    for i, row in df.iterrows():
        row_style = "background-color:#FFFDE7;" if is_summary_table else ""
        html += f'<tr style="{row_style} border-bottom:1px solid #E5E5E5; height:32px;">'
        
        for col in df.columns:
            val = row[col]
            # 수치형 값 포맷 세분화
            if isinstance(val, (int, float)):
                if "클릭률" in col:
                    formatted_val = f"{val:.2f}%"
                else:
                    formatted_val = f"{int(val):,}"
            else:
                formatted_val = str(val)
                
            html += f'<td style="padding:8px; border:1px solid #E0E0E0; color:#000000 !important; font-size:13px;">{formatted_val}</td>'
        html += '</tr>'
        
    html += '</tbody></table>'
    return html


# ==========================================
# [그리드 엔진] 엑셀 '주변 서식에 맞추기' 연동 텍스트 추출 가공 모듈
# ==========================================
def dataframe_to_tsv_string(df):
    # 엑셀이 가장 정확하게 표 데이터를 파싱할 수 있는 탭 구분(TSV) 플레인 텍스트 스트링을 생성합니다.
    lines = []
    for _, row in df.iterrows():
        row_vals = []
        for col in df.columns:
            val = row[col]
            if isinstance(val, (int, float)):
                if "클릭률" in col:
                    formatted_val = f"{val:.2f}%"
                else:
                    formatted_val = f"{int(val):,}"
            else:
                formatted_val = str(val)
            row_vals.append(formatted_val)
        lines.append("\t".join(row_vals))
    return "\n".join(lines)


# 💡 [신규 개발] 고대비 일괄 복사 컴포넌트 템플릿 제어 모듈
def render_table_and_button_html(df, title, is_summary_table=False):
    table_html = convert_df_to_html_grid(df, is_summary_table)
    tsv_text = dataframe_to_tsv_string(df)
    
    # 각 지표 컴포넌트 간의 고유 키 바인딩을 위한 고유 ID를 부여합니다.
    unique_id = str(int(time.time() * 1000)) + str(abs(hash(title)))
    
    # 💡 [피드백 반영] 이스케이프 문자 충돌을 완벽 방지하고 고대비(2px solid #000000)를 수립한 버튼 코드입니다.
    html_code = f"""
    <div style="font-family:sans-serif; color:#000000 !important; background-color:#FFFFFF; padding:5px;">
        {table_html}
        <button id="btn-{unique_id}" onclick="copyText()" style="
            background-color: #FFFDE7 !important;
            color: #000000 !important;
            border: 2px solid #000000 !important;
            border-radius: 6px !important;
            padding: 10px 16px !important;
            font-size: 13px !important;
            font-weight: bold !important;
            cursor: pointer !important;
            width: 100% !important;
            margin-top: 10px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
            text-align: center !important;
            display: block !important;
            transition: all 0.2s;
        " onmouseover="this.style.backgroundColor='#FFF9C4'" onmouseout="this.style.backgroundColor='#FFFDE7'">
            📋 이 표 데이터 복사하기 (주변 서식 맞춤)
        </button>
        <textarea id="area-{unique_id}" style="position:absolute; left:-9999px; width:1px; height:1px;">{tsv_text}</textarea>
    </div>
    
    <script>
    function copyText() {{
        try {{
            var text = document.getElementById('area-{unique_id}').value;
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(function() {{
                    showCopied();
                }}).catch(function(err) {{
                    fallbackCopy();
                }});
            }} else {{
                fallbackCopy();
            }}
        }} catch (e) {{
            fallbackCopy();
        }}
    }}
    
    function fallbackCopy() {{
        var copyText = document.getElementById('area-{unique_id}');
        copyText.select();
        copyText.setSelectionRange(0, 99999);
        document.execCommand('copy');
        showCopied();
    }}
    
    function showCopied() {{
        var btn = document.getElementById('btn-{unique_id}');
        btn.innerHTML = '✅ 복사 완료 (엑셀에 바로 붙여넣으세요)';
        btn.style.backgroundColor = '#C8E6C9'; 
        btn.style.borderColor = '#4CAF50';
        btn.style.color = '#000000';
        setTimeout(function() {{
            btn.innerHTML = '📋 이 표 데이터 복사하기 (주변 서식 맞춤)';
            btn.style.backgroundColor = '#FFFDE7';
            btn.style.borderColor = '#000000';
        }}, 2000);
    }}
    </script>
    """
    return html_code


# 💡 [신규 개발] 동적 높이를 계산하여 아이프레임 스크롤바가 없는 깔끔한 레이아웃을 계산합니다.
def get_table_iframe_height(df, is_summary=False):
    row_count = len(df)
    if is_summary:
        return 170
    else:
        calc_height = 36 + (32 * row_count) + 95
        return max(calc_height, 120)


# 💡 [신규 개발] 마스터 복사 컴포넌트 렌더러 함수
def render_table_with_copy_btn(df, title, is_summary_table=False):
    st.markdown(f"##### {title}")
    html_content = render_table_and_button_html(df, title, is_summary_table)
    iframe_height = get_table_iframe_height(df, is_summary_table)
    # 아이프레임 가상 샌드박스로 브라우저 클립보드 차단 우회
    st.components.v1.html(html_content, height=iframe_height, scrolling=False)


# ==========================================
# [사이드바 설계 및 동적 바인딩 콜백]
# ==========================================
st.sidebar.markdown("### 📁 1. 광고 ID(계정) 선택")

available_accounts = list(st.session_state['ad_accounts'].keys())
options_list = ["광고 ID 선택"] + available_accounts

def update_inputs_from_profile():
    prof = st.session_state.get('selected_profile')
    if prof == "광고 ID 선택":
        st.session_state['input_customer_id'] = ""
        st.session_state['input_api_key'] = ""
        st.session_state['input_secret_key'] = ""
    elif prof and prof in st.session_state['ad_accounts']:
        keys = st.session_state['ad_accounts'][prof]
        st.session_state['input_customer_id'] = keys["customer_id"]
        st.session_state['input_api_key'] = keys["api_key"]
        st.session_state['input_secret_key'] = keys["secret_key"]

if 'selected_profile' not in st.session_state:
    st.session_state['selected_profile'] = "광고 ID 선택"
    update_inputs_from_profile()

selected_profile = st.sidebar.selectbox(
    "관리 중인 계정을 선택하시면 저장된 API 키를 자동으로 불러옵니다.", 
    options=options_list,
    key='selected_profile',
    on_change=update_inputs_from_profile
)

if st.sidebar.button("🗑️ 선택된 광고 ID 삭제"):
    if selected_profile != "광고 ID 선택":
        del st.session_state['ad_accounts'][selected_profile]
        save_accounts(st.session_state['ad_accounts'])
        st.session_state['selected_profile'] = "광고 ID 선택"
        update_inputs_from_profile()
        st.sidebar.success(f"'{selected_profile}' 계정이 목록에서 성공적으로 삭제되었습니다.")
        time.sleep(0.5)
        st.rerun()
    else:
        st.sidebar.error("기본 안내 가이드 문구('광고 ID 선택')는 삭제할 수 없습니다.")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔑 2. API 인증 키 관리")

st.sidebar.text_input("CUSTOMER_ID", key="input_customer_id")
st.sidebar.text_input("액세스 라이선스 (API KEY)", type="password", key="input_api_key")
st.sidebar.text_input("비밀키 (SECRET_KEY)", type="password", key="input_secret_key")

st.sidebar.markdown("---")
st.sidebar.markdown("### ➕ 3. 새로운 광고 ID(계정) 등록")

st.sidebar.text_input("신규 계정 별칭", placeholder="예: 인하우스 패션몰 C", key="reg_name")

# 등록 콜백 바인딩
st.sidebar.button("💾 위 정보로 광고 ID 등록", on_click=register_account_callback)

if st.session_state['registration_success']:
    st.sidebar.success(f"'{st.session_state['registration_success']}' 계정이 추가되었으며, 기입창이 초기화되었습니다.")
    st.session_state['registration_success'] = ""
    time.sleep(0.5)
    st.rerun()

if st.session_state['registration_error']:
    st.sidebar.error("모든 칸과 별칭을 채운 후 등록을 눌러주세요.")
    st.session_state['registration_error'] = False


# ==========================================
# [메인 제어] 플레이스 통계 및 결과 표 도출
# ==========================================
st.subheader("인하우스 마케팅 주간 데이터 추출기")
st.caption("사이드바에서 등록한 계정은 로컬에 영구 보존됩니다. 브라우저 텍스트 테이블 양식이 직접 화면에 그리드로 그려지므로, 드래그 복사 시 쉼표와 중앙 정렬이 보존됩니다.")

# 계정 선택 가이드 노출
if selected_profile == "광고 ID 선택" or not selected_profile:
    st.info("👈 왼쪽 사이드바에서 조회 및 제어할 광고 ID(계정)를 먼저 선택해 주세요.")
    st.stop()

# 가상 모드 작동 여부 결정
is_test_mode = ("mock" in st.session_state['input_customer_id'].lower()) or (st.session_state['input_customer_id'] == "")

# 조회 범위 입력 상자
col_date1, col_date2 = st.columns(2)
with col_date1:
    start_date = st.date_input("조회 시작일 (월요일)", value=last_monday)
with col_date2:
    end_date = st.date_input("조회 종료일 (일요일)", value=last_sunday)

st.markdown("### 🗂&nbsp;&nbsp;광고 구성 단계별 선택")

# 광고유형의 선택 순서 (플레이스광고 ➡️ 파워링크광고 ➡️ 파워컨텐츠광고)
selected_ad_type = st.selectbox(
    "1. 광고그룹 유형을 선택해 주세요.", 
    ['플레이스광고', '파워링크광고', '파워컨텐츠광고']
)

if is_test_mode:
    campaign_list = get_mock_campaigns(selected_ad_type)
else:
    campaign_list = fetch_campaigns(
        st.session_state['input_customer_id'], 
        st.session_state['input_api_key'], 
        st.session_state['input_secret_key'], 
        selected_ad_type
    )

if not campaign_list:
    st.warning("⚠️ 선택하신 유형에 부합하는 캠페인이 확인되지 않습니다.")
    st.stop()

camp_options = {c['nccCampaignId']: c['name'] for c in campaign_list}
selected_camp_id = st.selectbox("2. 캠페인을 지정해 주세요.", options=list(camp_options.keys()), format_func=lambda x: camp_options[x])

if is_test_mode:
    adgroup_list = get_mock_adgroups(selected_camp_id)
else:
    adgroup_list = fetch_adgroups(
        st.session_state['input_customer_id'], 
        st.session_state['input_api_key'], 
        st.session_state['input_secret_key'], 
        selected_camp_id
    )

if not adgroup_list:
    st.warning("⚠️ 지정된 캠페인 하위에 개설된 광고그룹이 존재하지 않습니다.")
    st.stop()

adg_options = {g['nccAdgroupId']: g['name'] for g in adgroup_list}
selected_adg_id = st.selectbox("3. 상세 광고그룹을 지정해 주세요.", options=list(adg_options.keys()), format_func=lambda x: adg_options[x])


# '평균 광고 노출 입찰가' 가이드 연동
if selected_ad_type == '플레이스광고':
    avg_bid_val = None
    if not is_test_mode:
        avg_bid_val = fetch_place_avg_bid(
            st.session_state['input_customer_id'], 
            st.session_state['input_api_key'], 
            st.session_state['input_secret_key'], 
            selected_adg_id
        )
    else:
        avg_bid_val = 1460
        
    if avg_bid_val is not None:
        st.info(f"💡 **같은 지역 동종 업종 광고들의 평균 광고 노출 입찰가 참고하기 도움말**\n\n"
                f"**평균 광고 노출 입찰가 : {avg_bid_val:,}**")

st.markdown("---")

# 플레이스광고일 때는 키워드 탭 완전 차단 격리
if selected_ad_type == '플레이스광고':
    show_daily_detail = st.button("📊 일별 상세데이터 가져오기")
    show_keyword_rank = False
else:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        show_daily_detail = st.button("📊 일별 상세데이터 가져오기")
    with col_btn2:
        show_keyword_rank = st.button("🔑 키워드별 성과(상위 10개) 가져오기")

st.markdown("###")


# ==========================================
# [액션 1] 일별 상세데이터 그리드 분할 가로 나열(HTML) 출력
# ==========================================
if show_daily_detail:
    with st.spinner("일자별 성과 데이터를 분석 중..."):
        if is_test_mode:
            raw_df = get_mock_daily_stats(selected_adg_id, start_date, end_date)
        else:
            raw_df = fetch_daily_stats(
                st.session_state['input_customer_id'], 
                st.session_state['input_api_key'], 
                st.session_state['input_secret_key'], 
                selected_adg_id, 
                start_date, 
                end_date
            )
            
        if raw_df is not None and not raw_df.empty:
            total_imp = raw_df["노출수"].sum()
            total_clk = raw_df["클릭수"].sum()
            total_cost = raw_df["총비용"].sum()
            
            total_ctr = round((total_clk / total_imp) * 100, 2) if total_imp > 0 else 0.0
            total_cpc = int(total_cost / total_clk) if total_clk > 0 else 0
            
            # (1) 최상단 종합 요약 "합계표" 구성
            summary_df = pd.DataFrame([{
                "총 노출수": total_imp,
                "총 클릭수": total_clk,
                "평균 클릭률(%)": total_ctr,
                "평균 CPC": total_cpc,
                "총비용 합계": total_cost
            }])
            
            # (2) 노출수와 클릭수 정보 성과표 (날짜 열 제거)
            imp_clk_df = raw_df[["노출수", "클릭수"]].copy()
            
            # (3) 일자별 평균 CPC 표 구성 (날짜 열 제거)
            cpc_df = raw_df[["평균 CPC"]].copy()
            
            # (4) 일자별 총비용 표 구성 (날짜 열 제거)
            cost_df = raw_df[["총비용"]].copy()
            
            # 💡 최상단 요약 "합계표"는 전체 가로 너비를 넓게 채워 렌더링 및 텍스트 전용 복사 단축 버튼을 매핑합니다.
            render_table_with_copy_btn(summary_df, "🏆 주간 총 합계표", is_summary_table=True)
            
            st.markdown("###") # 레이아웃 공백 보정
            
            # 세 개의 일별 데이터를 가로(side-by-side) 구조로 나란히 나열합니다.
            col1, col2, col3 = st.columns(3)
            
            # 💡 세 가로 열의 모든 지표 표 명칭을 '일별 데이터'로 통일하여 매핑합니다.
            with col1:
                render_table_with_copy_btn(imp_clk_df, "📊 일별 데이터")
                
            with col2:
                render_table_with_copy_btn(cpc_df, "💵 일별 데이터")
                
            with col3:
                render_table_with_copy_btn(cost_df, "💰 일별 데이터")
            
            st.success("✅ 조회가 완료되었습니다! 표 바로 밑단에 준비된 검정색 테두리의 복사하기 단축버튼을 누르시면, 단 한 번의 조작으로 엑셀 시트에 값과 콤마 형태 그대로 깨끗하게 안착합니다.")
        else:
            st.error("해당 광고그룹에 해당하는 일별 상세 통계 정보가 부존재합니다.")


# ==========================================
# [액션 2] 상위 키워드 지표 그리드(HTML) 출력 (파워링크, 파워컨텐츠 유형 전용)
# ==========================================
if show_keyword_rank:
    with st.spinner("가장 성과가 뛰어난 상위 10개 키워드 지표를 추적하는 중..."):
        if is_test_mode:
            kw_df = get_mock_keyword_stats(selected_adg_id, selected_ad_type, start_date, end_date)
        else:
            kw_df = fetch_keyword_stats(
                st.session_state['input_customer_id'], 
                st.session_state['input_api_key'], 
                st.session_state['input_secret_key'], 
                selected_adg_id, 
                start_date, 
                end_date, 
                selected_ad_type
            )
            
        if kw_df is not None and not kw_df.empty:
            render_table_with_copy_btn(kw_df, "📊 키워드별 검색어 성과 (클릭수 상위 10개)", is_summary_table=False)
            st.success("✅ 키워드 성과 보고서 출력이 완료되었습니다! 엑셀 양식에 맞춰 복사해서 사용해 보세요.")
        else:
            st.warning("⚠️ 해당 광고그룹 내에서 수집 가능한 키워드 실적 지표가 존재하지 않습니다.")
