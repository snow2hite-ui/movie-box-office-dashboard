
import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ==================================================
# 1. 기본 화면 설정
# ==================================================
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/"
    "webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)


# ==================================================
# 2. 한국 시간 기준으로 어제 날짜 계산
# ==================================================
def get_yesterday():
    # 서버가 어느 시간대에 있든 한국 시간을 기준으로 계산합니다.
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_now.date() - timedelta(days=1)

    # API에는 YYYYMMDD 형식으로 전달합니다.
    target_date = yesterday.strftime("%Y%m%d")

    # 화면에는 읽기 편한 날짜 형식으로 표시합니다.
    display_date = yesterday.strftime("%Y년 %m월 %d일")

    weekdays = [
        "월요일", "화요일", "수요일", "목요일",
        "금요일", "토요일", "일요일",
    ]
    weekday = weekdays[yesterday.weekday()]

    return target_date, display_date, weekday


# ==================================================
# 3. 숫자 문자열을 숫자로 변환
# ==================================================
def to_number(value):
    # API의 숫자는 문자열로 오므로 정수로 바꿉니다.
    # 값이 없거나 숫자가 아니면 0으로 처리합니다.
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def format_count(value):
    # 천 단위 쉼표를 붙여 읽기 쉽게 표시합니다.
    return f"{int(value):,}"


# ==================================================
# 4. KOBIS API 호출
# ==================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_boxoffice(target_date, api_key):
    # API 키는 코드에 적지 않고 secrets에서 전달받습니다.
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": target_date,
        },
        timeout=30,
    )

    # HTTP 오류가 있으면 예외가 발생합니다.
    response.raise_for_status()

    # JSON 응답으로 변환합니다.
    data = response.json()

    # 중요: 인증키가 틀려도 HTTP 200일 수 있으므로
    # HTTP 상태 코드만으로 성공 여부를 판단하지 않습니다.
    if "faultInfo" in data:
        fault = data["faultInfo"]

        error_code = fault.get("errorCode", "알 수 없음")
        error_message = fault.get("message", "오류 메시지 없음")

        raise ValueError(
            f"KOBIS API 오류 ({error_code}): {error_message}"
        )

    # 정상 응답에 박스오피스 결과가 있는지 확인합니다.
    result = data.get("boxOfficeResult")

    if not isinstance(result, dict):
        raise ValueError(
            "API 응답에 boxOfficeResult가 없습니다. "
            "KOBIS API 응답 형식을 확인해 주세요."
        )

    movie_list = result.get("dailyBoxOfficeList")

    if not isinstance(movie_list, list):
        raise ValueError(
            "일별 영화 목록을 찾을 수 없습니다. "
            "KOBIS 응답의 dailyBoxOfficeList를 확인해 주세요."
        )

    if len(movie_list) == 0:
        raise ValueError(
            "해당 날짜의 영화 목록이 비어 있습니다. "
            "집계 자료가 아직 등록되지 않았거나 "
            "API 응답에 데이터가 없는지 확인해 주세요."
        )

    return result


# ==================================================
# 5. 앱 제목과 조회 날짜
# ==================================================
st.title("🎬 어제의 박스오피스")

target_date, display_date, weekday = get_yesterday()

st.markdown(
    f"### 📅 {display_date} {weekday}"
)
st.caption(
    "영화진흥위원회(KOBIS) 일별 박스오피스 · "
    "한국 시간 기준 어제 집계"
)


# ==================================================
# 6. 인증키 확인
# ==================================================
try:
    # Streamlit Cloud에서는 앱 설정의 Secrets에
    # KOBIS_KEY를 등록해 주세요.
    api_key = st.secrets["KOBIS_KEY"]

    if not str(api_key).strip():
        st.error(
            "KOBIS_KEY가 비어 있습니다. "
            "Streamlit Cloud의 앱 설정 → Secrets에서 "
            "인증키를 등록해 주세요."
        )
        st.stop()

except (KeyError, FileNotFoundError):
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정 → Secrets에 "
        "아래 항목을 추가해 주세요.\n\n"
        'KOBIS_KEY = "발급받은_인증키"'
    )
    st.stop()


# ==================================================
# 7. 데이터 조회
# ==================================================
try:
    with st.spinner("어제의 박스오피스를 조회하고 있습니다..."):
        result = fetch_boxoffice(target_date, str(api_key))

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버 응답 시간이 초과되었습니다. "
        "잠시 후 다시 실행해 주세요."
    )
    st.info(
        "확인할 사항: 인터넷 연결, KOBIS 서버 상태, "
        "네트워크 응답 지연 여부"
    )
    st.stop()

except requests.exceptions.HTTPError as e:
    st.error(f"KOBIS 서버에서 HTTP 오류가 발생했습니다: {e}")
    st.info(
        "확인할 사항: API 주소, KOBIS 서버 상태, "
        "요청 제한 또는 접근 오류 여부"
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(f"KOBIS API 요청에 실패했습니다: {e}")
    st.info(
        "확인할 사항: 인터넷 연결, API 주소, "
        "KOBIS 서버 접근 가능 여부"
    )
    st.stop()

except ValueError as e:
    st.error(str(e))
    st.info(
        "확인할 사항:\n"
        "- KOBIS_KEY가 올바르게 등록되어 있는지\n"
        "- API 인증키가 유효한지\n"
        "- 해당 날짜의 일별 박스오피스 자료가 있는지\n"
        "- KOBIS API 응답에 오류 정보가 포함되었는지"
    )
    st.stop()

except Exception as e:
    st.error(f"예상하지 못한 오류가 발생했습니다: {e}")
    st.info(
        "앱 로그와 KOBIS API 응답을 확인해 주세요."
    )
    st.stop()


# ==================================================
# 8. 영화 목록을 표로 만들기
# ==================================================
movies = result["dailyBoxOfficeList"]

df = pd.DataFrame(movies)

# 화면에 필요한 열이 모두 있는지 확인합니다.
required_columns = [
    "rank",
    "movieNm",
    "openDt",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    st.error(
        "API 응답에 필요한 항목이 없습니다: "
        + ", ".join(missing_columns)
    )
    st.info(
        "KOBIS API 응답 형식이 변경되었는지 확인해 주세요."
    )
    st.stop()

# API의 숫자 문자열을 실제 숫자로 변환합니다.
numeric_columns = [
    "rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"
]

for col in numeric_columns:
    if col in df.columns:
        df[col] = df[col].map(to_number)

# 순위 순서로 정렬합니다.
df = df.sort_values("rank").reset_index(drop=True)

# 영화명이 없는 항목은 제거합니다.
df = df[
    df["movieNm"].fillna("").astype(str).str.strip() != ""
].copy()

if df.empty:
    st.error(
        "영화 목록을 불러왔지만 표시할 영화가 없습니다."
    )
    st.info(
        "KOBIS에서 해당 날짜의 집계가 완료되었는지, "
        "API 응답에 영화명이 포함되어 있는지 확인해 주세요."
    )
    st.stop()


# ==================================================
# 9. 1위 영화 지표 카드 세 장
# ==================================================
first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        "영화명",
        str(first_movie["movieNm"]),
    )

with card2:
    st.metric(
        "당일 관객수",
        f"{format_count(first_movie['audiCnt'])}명",
    )

with card3:
    st.metric(
        "누적 관객수",
        f"{format_count(first_movie['audiAcc'])}명",
    )


# ==================================================
# 10. 관객수 상위 5편 막대그래프
# ==================================================
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .sort_values("audiCnt", ascending=True)
)

# 가로 막대그래프라 영화명이 길어도 읽기 편합니다.
chart_df = top5[["movieNm", "audiCnt"]].copy()
chart_df = chart_df.rename(
    columns={
        "movieNm": "영화명",
        "audiCnt": "당일 관객수",
    }
)

st.bar_chart(
    chart_df.set_index("영화명"),
    x_label="영화명",
    y_label="당일 관객수(명)",
    horizontal=True,
)


# ==================================================
# 11. 전체 박스오피스 표
# ==================================================
st.subheader("📋 일별 박스오피스 전체 순위")

# 날짜가 없는 경우에는 '정보 없음'으로 표시합니다.
df["openDt"] = df["openDt"].fillna("").replace("", "정보 없음")

table_df = pd.DataFrame({
    "순위": df["rank"],
    "영화명": df["movieNm"],
    "개봉일": df["openDt"],
    "관객수": df["audiCnt"].map(format_count),
    "누적관객": df["audiAcc"].map(format_count),
    "스크린수": df["scrnCnt"].map(format_count),
})

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
)

# API에서 제공하는 집계 기간을 표시합니다.
show_range = result.get("showRange", target_date)

st.caption(
    f"집계 기간: {show_range} · "
    f"표시 영화 수: {len(table_df)}편 · "
    "자료 출처: 영화진흥위원회 KOBIS 오픈API"
)

# 화면에서 새로고침을 쉽게 할 수 있도록 버튼을 제공합니다.
if st.button("🔄 데이터 다시 조회"):
    fetch_boxoffice.clear()
    st.rerun()
