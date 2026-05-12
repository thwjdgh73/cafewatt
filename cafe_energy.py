import streamlit as st
import pandas as pd
import requests
from datetime import time

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except Exception:
    FOLIUM_AVAILABLE = False


st.set_page_config(
    page_title="CafeWatt",
    page_icon="☕",
    layout="wide"
)


# =============================
# 기본 스타일
# =============================

st.markdown("""
<style>
.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 4px;
}
.sub-title {
    font-size: 16px;
    color: #666;
    margin-bottom: 20px;
}
.card {
    padding: 18px;
    border-radius: 16px;
    background-color: #f8f8f8;
    border: 1px solid #eeeeee;
    margin-bottom: 12px;
}
.metric-title {
    font-size: 14px;
    color: #777;
}
.metric-value {
    font-size: 26px;
    font-weight: 800;
    line-height: 1.25;
    word-break: keep-all;
}
.metric-value-small {
    font-size: 21px;
    font-weight: 800;
    line-height: 1.35;
    word-break: keep-all;
}
.good {
    color: #1f7a3f;
    font-weight: 700;
}
.warning {
    color: #b26a00;
    font-weight: 700;
}
.danger {
    color: #b00020;
    font-weight: 700;
}
.small-text {
    font-size: 13px;
    color: #777;
}
.location-box {
    padding: 14px 16px;
    border-radius: 14px;
    background-color: #fff7ec;
    border: 1px solid #f1dfc6;
    margin-top: 10px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


# =============================
# 기준 데이터
# =============================

BENCHMARKS = {
    "일반 카페": {
        "monthly_kwh_per_m2": 28,
        "kwh_per_operating_hour": 5.5,
        "normal_bill_min": 300000,
        "normal_bill_max": 550000,
        "contract_power_low": 10,
        "contract_power_high": 20,
        "description": "음료 중심 카페 기준"
    },
    "베이커리 카페": {
        "monthly_kwh_per_m2": 55,
        "kwh_per_operating_hour": 10.5,
        "normal_bill_min": 600000,
        "normal_bill_max": 1100000,
        "contract_power_low": 20,
        "contract_power_high": 35,
        "description": "오븐, 냉동고, 쇼케이스 포함 기준"
    }
}


# =============================
# 표시 함수
# =============================

def won(value):
    return f"{int(value):,}원"


def kwh(value):
    return f"{value:,.0f} kWh"


def pct(value):
    return f"{value:+.1f}%"


def grade_from_ratio(ratio):
    if ratio < 0.85:
        return "낮음", "good"
    elif ratio <= 1.15:
        return "평균 수준", "good"
    elif ratio <= 1.35:
        return "높음", "warning"
    else:
        return "매우 높음", "danger"


def score_from_ratio(ratio):
    if ratio <= 0.85:
        return 88
    elif ratio <= 1.0:
        return 78
    elif ratio <= 1.15:
        return 68
    elif ratio <= 1.35:
        return 55
    else:
        return 42


def metric_card(title, value, caption=None, small=False):
    value_class = "metric-value-small" if small else "metric-value"

    caption_html = ""
    if caption:
        caption_html = f"<p class='small-text'>{caption}</p>"

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">{title}</div>
        <div class="{value_class}">{value}</div>
        {caption_html}
    </div>
    """, unsafe_allow_html=True)


# =============================
# 세션 기본값
# =============================

if "selected_location_label" not in st.session_state:
    st.session_state["selected_location_label"] = "서울특별시 강남구 테헤란로"

if "latitude" not in st.session_state:
    st.session_state["latitude"] = 37.5013

if "longitude" not in st.session_state:
    st.session_state["longitude"] = 127.0396


# =============================
# Kakao API Key 정리 함수
# =============================

def get_clean_kakao_key():
    """
    Kakao REST API Key를 안전하게 가져옵니다.

    중요:
    secrets.toml에는 실제 REST API Key만 넣어야 합니다.
    KakaoAK는 코드에서 자동으로 붙입니다.
    """

    raw_key = st.secrets.get("KAKAO_REST_API_KEY", "")

    if raw_key is None:
        raw_key = ""

    key = str(raw_key).strip()

    if key.startswith("KakaoAK"):
        key = key.replace("KakaoAK", "", 1).strip()

    if not key:
        return None, "Kakao REST API Key가 비어 있습니다. .streamlit/secrets.toml 또는 Streamlit Cloud Secrets를 확인하세요."

    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return None, "Kakao REST API Key에 한글 또는 잘못된 문자가 들어 있습니다. 실제 REST API Key만 입력해야 합니다."

    return key, None


# =============================
# 카카오 주소 검색 API
# =============================

def get_coordinates_from_kakao(address_query):
    """
    카카오 Local API를 사용해 한국 주소를 위도와 경도로 변환합니다.
    """

    if not address_query or not address_query.strip():
        return {
            "success": False,
            "message": "주소를 입력하세요.",
            "results": []
        }

    kakao_key, key_error = get_clean_kakao_key()

    if key_error:
        return {
            "success": False,
            "message": key_error,
            "results": []
        }

    url = "https://dapi.kakao.com/v2/local/search/address.json"

    headers = {
        "Authorization": f"KakaoAK {kakao_key}"
    }

    params = {
        "query": address_query.strip(),
        "analyze_type": "similar"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        if response.status_code == 401:
            return {
                "success": False,
                "message": "Kakao API 인증에 실패했습니다. REST API Key가 맞는지 확인하세요.",
                "results": []
            }

        if response.status_code == 403:
            return {
                "success": False,
                "message": "Kakao API 접근이 거부되었습니다. Kakao Developers에서 Local API 사용 설정을 확인하세요.",
                "results": []
            }

        response.raise_for_status()
        data = response.json()

        documents = data.get("documents", [])

        if not documents:
            return {
                "success": False,
                "message": "검색 결과가 없습니다. 도로명 주소나 구체적인 주소로 다시 입력하세요.",
                "results": []
            }

        results = []

        for item in documents:
            address_name = item.get("address_name", "")
            road_address = item.get("road_address")
            address = item.get("address")

            display_address = address_name

            if road_address and road_address.get("address_name"):
                display_address = road_address.get("address_name")
            elif address and address.get("address_name"):
                display_address = address.get("address_name")

            longitude = float(item.get("x"))
            latitude = float(item.get("y"))

            results.append({
                "label": display_address,
                "latitude": latitude,
                "longitude": longitude
            })

        return {
            "success": True,
            "message": "검색 성공",
            "results": results
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": f"Kakao API 요청 실패: {e}",
            "results": []
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"주소 검색 처리 중 오류: {e}",
            "results": []
        }


# =============================
# Open Meteo 날씨 API
# =============================

def get_weather_open_meteo(latitude, longitude):
    """
    Open Meteo API에서 현재 외기온도, 외기습도, 풍속을 가져옵니다.
    """

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": "Asia/Seoul"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        current = data.get("current", {})

        return {
            "success": True,
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "raw": data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "raw": None
        }


# =============================
# 지도 함수
# =============================

def show_location_map(latitude, longitude, label):
    """
    지도 표시 및 클릭 위치 반영.
    streamlit-folium이 없으면 st.map으로 대체합니다.
    """

    if FOLIUM_AVAILABLE:
        m = folium.Map(
            location=[latitude, longitude],
            zoom_start=16
        )

        folium.Marker(
            [latitude, longitude],
            tooltip=label,
            popup=label
        ).add_to(m)

        map_data = st_folium(
            m,
            width=None,
            height=360,
            key="cafewatt_map"
        )

        clicked = map_data.get("last_clicked") if map_data else None

        if clicked:
            clicked_lat = float(clicked["lat"])
            clicked_lng = float(clicked["lng"])

            lat_changed = abs(clicked_lat - st.session_state["latitude"]) > 0.000001
            lng_changed = abs(clicked_lng - st.session_state["longitude"]) > 0.000001

            if lat_changed or lng_changed:
                st.session_state["latitude"] = clicked_lat
                st.session_state["longitude"] = clicked_lng
                st.session_state["selected_location_label"] = "지도에서 선택한 위치"
                st.rerun()

    else:
        map_df = pd.DataFrame([{
            "lat": latitude,
            "lon": longitude
        }])

        st.map(map_df, latitude="lat", longitude="lon", zoom=15)
        st.info("지도 클릭 기능을 사용하려면 requirements.txt에 folium, streamlit-folium을 추가하세요.")


# =============================
# 계약전력 진단 함수
# =============================

def contract_power_diagnosis(store_type, contract_power, estimated_peak_kw):
    benchmark = BENCHMARKS[store_type]
    low = benchmark["contract_power_low"]
    high = benchmark["contract_power_high"]

    if contract_power == 0:
        return (
            "정보 부족",
            "계약전력을 입력하면 기본요금 부담과 전력 여유를 간단히 진단할 수 있습니다.",
            "warning"
        )

    usage_ratio = estimated_peak_kw / contract_power if contract_power > 0 else 0

    if usage_ratio >= 0.9:
        return (
            "전력 여유 낮음",
            "현재 장비 구성에서는 피크 시간대 전력 여유가 낮을 수 있습니다. 냉방기, 커피머신, 제빙기, 오븐의 동시 사용을 분산하는 것이 좋습니다.",
            "danger"
        )

    if usage_ratio <= 0.5 and contract_power > high:
        return (
            "계약전력 과다 가능성",
            "현재 입력된 장비 기준으로는 계약전력이 다소 높을 가능성이 있습니다. 실제 최대 사용량을 확인한 뒤 계약전력 조정을 검토할 수 있습니다.",
            "warning"
        )

    if low <= contract_power <= high:
        return (
            "대체로 적정",
            "현재 업종과 규모 기준으로 계약전력이 일반적인 범위에 있습니다. 다만 실제 피크 사용량 확인이 필요합니다.",
            "good"
        )

    return (
        "확인 필요",
        "계약전력은 장비 구성과 동시 사용률에 따라 달라집니다. 전기기사 또는 한전 상담을 통해 실제 적정성을 확인하는 것이 좋습니다.",
        "warning"
    )


# =============================
# 추천 조치 함수
# =============================

def calculate_recommendations(
    store_type,
    monthly_kwh,
    monthly_bill,
    area_m2,
    monthly_hours,
    indoor_temp,
    outdoor_temp,
    plug_kwh_month,
    after_hours_ratio,
    contract_status,
    has_showcase,
    has_ice_machine,
    has_oven,
    refrigerator_count,
    ac_count
):
    recommendations = []

    benchmark = BENCHMARKS[store_type]
    kwh_per_m2 = monthly_kwh / area_m2
    ratio_area = kwh_per_m2 / benchmark["monthly_kwh_per_m2"]

    if ratio_area > 1.15:
        recommendations.append(
            "같은 업종과 면적 기준보다 전력 사용량이 높은 편입니다. 냉방 설정, 영업시간 외 장비 사용, 냉장 장비 상태를 우선 점검하세요."
        )

    if indoor_temp < 24:
        recommendations.append(
            "영업시간 평균 실내온도가 낮은 편입니다. 고객 쾌적성을 해치지 않는 범위에서 냉방 설정온도를 1도 높이는 것을 검토하세요."
        )
    elif indoor_temp > 27 and outdoor_temp > 28:
        recommendations.append(
            "실내온도가 높은 편입니다. 에너지 절감보다 고객 쾌적성과 냉방 성능 점검이 먼저 필요할 수 있습니다."
        )

    if plug_kwh_month > 0 and after_hours_ratio >= 25:
        recommendations.append(
            "스마트플러그에 연결된 장비의 영업시간 외 사용 비중이 높습니다. 폐점 후 자동 종료 또는 운전 스케줄 점검이 필요합니다."
        )

    if contract_status in ["전력 여유 낮음", "계약전력 과다 가능성"]:
        recommendations.append(
            "계약전력은 기본요금과 운영 안정성에 영향을 줍니다. 최근 최대 사용 패턴을 확인한 뒤 조정 여부를 검토하세요."
        )

    if has_showcase or refrigerator_count >= 2:
        recommendations.append(
            "쇼케이스나 냉장 장비가 많은 매장은 24시간 전력 사용 비중이 커질 수 있습니다. 냉장고 뒤쪽 방열 공간, 문 패킹, 설정온도를 점검하세요."
        )

    if has_ice_machine:
        recommendations.append(
            "제빙기는 여름철 전력 사용 증가에 영향을 줄 수 있습니다. 폐점 후 운전 상태와 주변 온도를 확인하세요."
        )

    if has_oven or store_type == "베이커리 카페":
        recommendations.append(
            "오븐과 냉방이 동시에 작동하면 피크 전력이 커질 수 있습니다. 오븐 예열과 냉방 피크 시간이 겹치지 않도록 운영하세요."
        )

    if ac_count >= 2:
        recommendations.append(
            "에어컨이 여러 대인 경우 동시에 강하게 켜기보다 구역별로 순차 운전하면 피크 부담을 줄일 수 있습니다."
        )

    if not recommendations:
        recommendations.append(
            "현재 입력값 기준으로 큰 이상 신호는 강하지 않습니다. 월별 사용량과 실내온도 변화를 계속 기록하면 더 정확한 진단이 가능합니다."
        )

    return recommendations[:4]


# =============================
# 헤더
# =============================

st.markdown('<div class="main-title">☕ CafeWatt</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">카페와 베이커리 카페의 전기요금, 실내환경, 장비 사용 패턴을 바탕으로 에너지 낭비 가능성을 쉽게 진단합니다.</div>',
    unsafe_allow_html=True
)

st.info(
    "CafeWatt는 전기요금 고지서의 월 사용량과 요금, 매장 정보, 날씨 데이터를 바탕으로 "
    "같은 업종과 규모 대비 전기를 많이 쓰는지 간단히 진단하는 MVP 앱입니다."
)


# =============================
# 메인 화면: 주소 기반 날씨 API
# =============================

st.subheader("매장 위치와 현재 날씨")

weather_input_col, weather_result_col = st.columns([1.05, 1.95])

with weather_input_col:
    address_query = st.text_input(
        "매장 주소",
        value=st.session_state["selected_location_label"],
        help="예시: 서울특별시 강남구 테헤란로, 서울 마포구 홍익로, 부산 해운대구"
    )

    search_weather = st.button("주소로 위치와 날씨 불러오기", use_container_width=True)

    if search_weather:
        geo_data = get_coordinates_from_kakao(address_query)

        if geo_data["success"] and geo_data["results"]:
            first_result = geo_data["results"][0]

            st.session_state["selected_location_label"] = first_result["label"]
            st.session_state["latitude"] = first_result["latitude"]
            st.session_state["longitude"] = first_result["longitude"]

            st.success("주소 검색 성공")
            st.rerun()

        else:
            st.warning(f"주소를 찾지 못했습니다. {geo_data['message']}")

    st.markdown(f"""
    <div class="location-box">
        <b>현재 기준 위치</b><br>
        {st.session_state["selected_location_label"]}<br>
        <span class="small-text">
        위도: {st.session_state["latitude"]:.6f}<br>
        경도: {st.session_state["longitude"]:.6f}
        </span>
    </div>
    """, unsafe_allow_html=True)

latitude = st.session_state["latitude"]
longitude = st.session_state["longitude"]
selected_location_label = st.session_state["selected_location_label"]

weather_data = get_weather_open_meteo(latitude, longitude)

outdoor_temp = 28.0
outdoor_humidity = 60
wind_speed = 0

with weather_result_col:
    map_col, current_weather_col = st.columns([1.25, 1])

    with map_col:
        show_location_map(latitude, longitude, selected_location_label)

    with current_weather_col:
        if weather_data["success"] and weather_data["temperature"] is not None:
            outdoor_temp = float(weather_data["temperature"])
            outdoor_humidity = float(weather_data["humidity"]) if weather_data["humidity"] is not None else 55
            wind_speed = float(weather_data["wind_speed"]) if weather_data["wind_speed"] is not None else 0

            metric_card("현재 외기온도", f"{outdoor_temp:.1f}°C")
            metric_card("현재 외기습도", f"{outdoor_humidity:.0f}%")
            metric_card("풍속", f"{wind_speed:.1f} m/s")

            st.caption(f"날씨 기준 위치: {selected_location_label}")

        else:
            st.warning("날씨 데이터를 불러오지 못했습니다. 기본값을 사용합니다.")

st.divider()


# =============================
# 사이드바 입력
# =============================

st.sidebar.header("1. 매장 기본 정보")

store_type = st.sidebar.selectbox(
    "업종 선택",
    ["일반 카페", "베이커리 카페"]
)

area_pyeong = st.sidebar.number_input(
    "매장 면적",
    min_value=5.0,
    max_value=100.0,
    value=20.0,
    step=1.0,
    help="평 단위로 입력하세요."
)

area_m2 = area_pyeong * 3.3058

open_time = st.sidebar.time_input("오픈 시간", value=time(9, 0))
close_time = st.sidebar.time_input("마감 시간", value=time(22, 0))
business_days = st.sidebar.slider("월 영업일수", 15, 31, 28)

open_hours = close_time.hour + close_time.minute / 60 - (open_time.hour + open_time.minute / 60)

if open_hours <= 0:
    open_hours = 12

monthly_hours = open_hours * business_days

st.sidebar.divider()

st.sidebar.header("2. 전기요금 정보")

monthly_kwh = st.sidebar.number_input(
    "월 전력사용량",
    min_value=100,
    max_value=20000,
    value=1800,
    step=100,
    help="전기요금 고지서의 kWh 값을 입력하세요."
)

monthly_bill = st.sidebar.number_input(
    "월 전기요금",
    min_value=10000,
    max_value=5000000,
    value=420000,
    step=10000,
    help="최근 월 전기요금을 입력하세요."
)

contract_power = st.sidebar.number_input(
    "계약전력",
    min_value=0.0,
    max_value=100.0,
    value=15.0,
    step=1.0,
    help="모르면 0으로 입력하세요."
)

st.sidebar.divider()

st.sidebar.header("3. 카페 장비 정보")

has_showcase = st.sidebar.checkbox("쇼케이스 있음", value=True)
has_ice_machine = st.sidebar.checkbox("제빙기 있음", value=True)
has_oven = st.sidebar.checkbox("오븐 있음", value=(store_type == "베이커리 카페"))

refrigerator_count = st.sidebar.slider("냉장고 또는 냉동고 개수", 0, 10, 2)
ac_count = st.sidebar.slider("에어컨 대수", 0, 10, 2)

st.sidebar.divider()

st.sidebar.header("4. 실내환경")

indoor_temp = st.sidebar.slider("영업시간 평균 실내온도", 18.0, 32.0, 25.5, 0.5)
indoor_humidity = st.sidebar.slider("평균 실내습도", 20, 90, 55)

st.sidebar.divider()

st.sidebar.header("5. 스마트플러그 장비")

plug_device = st.sidebar.selectbox(
    "스마트플러그 연결 장비",
    ["없음", "쇼케이스 냉장고", "제빙기", "소형 냉장고", "공기청정기", "복합기", "기타 장비"]
)

plug_kwh_day = 0
after_hours_ratio = 0

if plug_device != "없음":
    plug_kwh_day = st.sidebar.number_input(
        "연결 장비 하루 사용량",
        min_value=0.0,
        max_value=100.0,
        value=4.5,
        step=0.5,
        help="스마트플러그에서 확인한 하루 전력사용량을 입력하세요."
    )

    after_hours_ratio = st.sidebar.slider(
        "영업시간 외 사용 비중",
        0,
        100,
        25
    )

plug_kwh_month = plug_kwh_day * business_days


# =============================
# 계산
# =============================

benchmark = BENCHMARKS[store_type]

kwh_per_m2 = monthly_kwh / area_m2
kwh_per_hour = monthly_kwh / monthly_hours if monthly_hours > 0 else 0
price_per_kwh = monthly_bill / monthly_kwh if monthly_kwh > 0 else 0

ratio_area = kwh_per_m2 / benchmark["monthly_kwh_per_m2"]
ratio_hour = kwh_per_hour / benchmark["kwh_per_operating_hour"]

area_grade, area_class = grade_from_ratio(ratio_area)
hour_grade, hour_class = grade_from_ratio(ratio_hour)

energy_score = score_from_ratio((ratio_area + ratio_hour) / 2)

base_peak = area_pyeong * 0.55 if store_type == "일반 카페" else area_pyeong * 1.1
device_extra = 0

if has_showcase:
    device_extra += 0.8

if has_ice_machine:
    device_extra += 0.8

if has_oven:
    device_extra += 4.0

device_extra += refrigerator_count * 0.3
device_extra += ac_count * 1.2

estimated_peak_kw = max(6, base_peak + device_extra)

contract_status, contract_message, contract_class = contract_power_diagnosis(
    store_type,
    contract_power,
    estimated_peak_kw
)

recommendations = calculate_recommendations(
    store_type,
    monthly_kwh,
    monthly_bill,
    area_m2,
    monthly_hours,
    indoor_temp,
    outdoor_temp,
    plug_kwh_month,
    after_hours_ratio,
    contract_status,
    has_showcase,
    has_ice_machine,
    has_oven,
    refrigerator_count,
    ac_count
)

estimated_saving_low = monthly_bill * 0.05
estimated_saving_high = monthly_bill * 0.15

if energy_score < 55:
    estimated_saving_low = monthly_bill * 0.08
    estimated_saving_high = monthly_bill * 0.22


# =============================
# 메인 결과
# =============================

result_col1, result_col2, result_col3, result_col4 = st.columns([1, 1, 1, 1.35])

with result_col1:
    metric_card("종합 에너지 점수", f"{energy_score}점")

with result_col2:
    metric_card("월 전력사용량", kwh(monthly_kwh))

with result_col3:
    metric_card("월 전기요금", won(monthly_bill))

with result_col4:
    metric_card(
        "예상 절감 금액",
        f"{won(estimated_saving_low)}<br>~ {won(estimated_saving_high)}",
        "현재 입력값 기준 월 예상 범위",
        small=True
    )

st.caption(f"날씨 기준 위치: {selected_location_label}")

st.divider()


# =============================
# 진단 요약
# =============================

left, right = st.columns([1.2, 1])

with left:
    st.subheader("CafeWatt 진단 요약")

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">업종 기준</div>
        <div class="metric-value">{store_type}</div>
        <p>{benchmark["description"]}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">면적당 전력사용량</div>
        <div class="metric-value">{kwh_per_m2:.1f} kWh/㎡</div>
        <p>업종 평균 대비 <span class="{area_class}">{area_grade}</span> 입니다. 평균 대비 {pct((ratio_area - 1) * 100)} 수준입니다.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">운영시간당 전력사용량</div>
        <div class="metric-value">{kwh_per_hour:.1f} kWh/hour</div>
        <p>운영시간 기준으로는 <span class="{hour_class}">{hour_grade}</span> 입니다. 평균 대비 {pct((ratio_hour - 1) * 100)} 수준입니다.</p>
    </div>
    """, unsafe_allow_html=True)

with right:
    st.subheader("계약전력 간단 진단")

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">현재 계약전력</div>
        <div class="metric-value">{contract_power:.0f} kW</div>
        <p>추정 피크부하: 약 {estimated_peak_kw:.1f} kW</p>
        <p>진단: <span class="{contract_class}">{contract_status}</span></p>
        <p>{contract_message}</p>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("실내환경 진단")

    if indoor_temp < 24:
        temp_status = "과냉방 가능성"
        temp_class = "warning"
        temp_msg = "실내온도가 낮은 편입니다. 설정온도를 1도 높이는 것만으로도 냉방 전력 절감 여지가 있습니다."
    elif indoor_temp <= 26.5:
        temp_status = "적정 범위"
        temp_class = "good"
        temp_msg = "현재 실내온도는 고객 쾌적성과 에너지 사용 측면에서 비교적 적정한 범위입니다."
    else:
        temp_status = "냉방 부족 가능성"
        temp_class = "warning"
        temp_msg = "실내온도가 높은 편입니다. 냉방 효율, 출입문 개방, 실외기 상태를 확인하세요."

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">영업시간 평균 실내온도</div>
        <div class="metric-value">{indoor_temp:.1f}°C</div>
        <p>진단: <span class="{temp_class}">{temp_status}</span></p>
        <p>{temp_msg}</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()


# =============================
# 카페 장비 요약
# =============================

st.subheader("카페 장비 구성 요약")

device_col1, device_col2, device_col3, device_col4, device_col5 = st.columns(5)

with device_col1:
    st.metric("쇼케이스", "있음" if has_showcase else "없음")

with device_col2:
    st.metric("제빙기", "있음" if has_ice_machine else "없음")

with device_col3:
    st.metric("오븐", "있음" if has_oven else "없음")

with device_col4:
    st.metric("냉장 냉동 장비", f"{refrigerator_count}개")

with device_col5:
    st.metric("에어컨", f"{ac_count}대")

if has_oven and store_type == "일반 카페":
    st.warning("오븐이 있는 경우 일반 카페보다 베이커리 카페에 가까운 전력 패턴이 나타날 수 있습니다.")

st.divider()


# =============================
# 날씨 분석
# =============================

st.subheader("날씨와 냉방 부담")

weather_col1, weather_col2, weather_col3, weather_col4 = st.columns(4)

with weather_col1:
    st.metric("외기온도", f"{outdoor_temp:.1f}°C")

with weather_col2:
    st.metric("외기습도", f"{outdoor_humidity:.0f}%")

with weather_col3:
    st.metric("풍속", f"{wind_speed:.1f} m/s")

with weather_col4:
    st.metric("실내외 온도차", f"{indoor_temp - outdoor_temp:+.1f}°C")

if outdoor_temp >= 30 and indoor_temp <= 24:
    st.warning("외기온도가 높은데 실내온도가 낮게 유지되고 있습니다. 냉방 전력 사용이 커질 가능성이 있습니다.")
elif outdoor_temp >= 30 and indoor_temp > 27:
    st.warning("외기온도와 실내온도가 모두 높은 편입니다. 냉방 성능이나 출입문 개방으로 인한 냉방 손실을 확인하세요.")
else:
    st.success("현재 날씨 조건에서는 냉방 부담이 과도하게 높게 나타나지는 않습니다.")

st.divider()


# =============================
# 스마트플러그 분석
# =============================

st.subheader("스마트플러그 장비 분석")

if plug_device == "없음":
    st.info("스마트플러그가 연결되지 않았습니다. 쇼케이스 냉장고, 제빙기, 소형 냉장고 중 하나를 연결하면 장비별 사용 패턴을 확인할 수 있습니다.")
else:
    device_cost = plug_kwh_month * price_per_kwh
    after_hours_kwh = plug_kwh_month * after_hours_ratio / 100
    after_hours_cost = after_hours_kwh * price_per_kwh

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("연결 장비", plug_device)

    with c2:
        st.metric("월 예상 사용량", kwh(plug_kwh_month))

    with c3:
        st.metric("월 예상 비용", won(device_cost))

    with c4:
        st.metric("영업 외 비용", won(after_hours_cost))

    if after_hours_ratio >= 30:
        st.warning(
            f"{plug_device}의 영업시간 외 사용 비중이 {after_hours_ratio}%입니다. "
            "필수 운전 장비인지 확인하고, 불필요한 운전이라면 자동 종료나 스케줄 조정을 검토하세요."
        )
    else:
        st.success(
            f"{plug_device}의 영업시간 외 사용 비중은 {after_hours_ratio}%입니다. "
            "현재는 큰 낭비 신호가 강하게 보이지 않습니다."
        )

st.divider()


# =============================
# 추천 조치
# =============================

st.subheader("CafeWatt 추천 조치")

for idx, rec in enumerate(recommendations, start=1):
    st.markdown(f"**{idx}. {rec}**")

st.divider()


# =============================
# 요약
# =============================

st.subheader("CafeWatt 요약")

if ratio_area > 1.15 or ratio_hour > 1.15:
    summary = (
        f"사장님의 {store_type}는 같은 업종과 유사 규모 기준보다 전력 사용량이 높은 편입니다. "
        "냉방 설정, 냉장 장비, 영업시간 외 사용량을 우선 점검하는 것이 좋습니다."
    )
elif ratio_area < 0.85 and ratio_hour < 0.85:
    summary = (
        f"사장님의 {store_type}는 같은 업종과 유사 규모 기준보다 전력 사용량이 낮은 편입니다. "
        "다만 실내 쾌적성이 떨어지지 않는지 함께 확인하는 것이 좋습니다."
    )
else:
    summary = (
        f"사장님의 {store_type}는 업종 평균과 비슷한 전력 사용 수준입니다. "
        "스마트플러그 장비와 계약전력을 점검하면 추가 절감 여지를 찾을 수 있습니다."
    )

st.success(summary)


# =============================
# 진단 기준 안내
# =============================

with st.expander("CafeWatt 진단 기준 안내"):
    st.write("""
    CafeWatt는 카페와 베이커리 카페의 기본 에너지 진단용 MVP입니다.

    현재 결과는 입력값과 간단한 업종 기준값을 바탕으로 계산됩니다.
    실제 서비스에서는 공공데이터, 실제 사용자 데이터, 센서 데이터가 누적되면서 업종 평균 기준을 계속 개선해야 합니다.

    계약전력 진단은 사전 참고용입니다.
    실제 계약전력 변경은 한전, 전기공사업체, 전기기사와 확인해야 합니다.

    스마트플러그 분석은 연결된 특정 장비의 사용량만 보여줍니다.
    매장 전체 전력사용량은 월 전력사용량 입력값을 기준으로 판단합니다.

    주소 검색은 카카오 Local API를 사용하고, 날씨 데이터는 Open Meteo API를 사용합니다.
    """)

st.caption("CafeWatt MVP 0.4 | 카페 전기요금 진단 AI")