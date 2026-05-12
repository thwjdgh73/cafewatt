import streamlit as st
import pandas as pd
import requests
from datetime import time, datetime

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except Exception:
    FOLIUM_AVAILABLE = False


# =========================================================
# Page Config
# =========================================================

st.set_page_config(
    page_title="CafeWatt",
    page_icon="☕",
    layout="wide"
)


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.main-title {
    font-size: 38px;
    font-weight: 900;
    margin-bottom: 4px;
    color: #2B2118;
}

.sub-title {
    font-size: 16px;
    color: #6B5E52;
    margin-bottom: 18px;
}

.section-title {
    font-size: 22px;
    font-weight: 800;
    color: #2B2118;
    margin-top: 8px;
    margin-bottom: 12px;
}

.card {
    padding: 18px;
    border-radius: 18px;
    background-color: #FAF7F2;
    border: 1px solid #EEE4D6;
    margin-bottom: 14px;
}

.card-white {
    padding: 18px;
    border-radius: 18px;
    background-color: #FFFFFF;
    border: 1px solid #EEEEEE;
    margin-bottom: 14px;
}

.card-soft {
    padding: 16px;
    border-radius: 16px;
    background-color: #FFF8EA;
    border: 1px solid #F1DEB8;
    margin-bottom: 12px;
}

.metric-title {
    font-size: 13px;
    color: #7A6D61;
    font-weight: 700;
    margin-bottom: 6px;
}

.metric-value {
    font-size: 28px;
    font-weight: 900;
    color: #2B2118;
    line-height: 1.25;
    word-break: keep-all;
}

.metric-value-small {
    font-size: 22px;
    font-weight: 900;
    color: #2B2118;
    line-height: 1.35;
    word-break: keep-all;
}

.metric-caption {
    font-size: 13px;
    color: #7A6D61;
    margin-top: 8px;
}

.good {
    color: #177245;
    font-weight: 800;
}

.warning {
    color: #B56A00;
    font-weight: 800;
}

.danger {
    color: #B00020;
    font-weight: 800;
}

.neutral {
    color: #444444;
    font-weight: 800;
}

.small-text {
    font-size: 13px;
    color: #777777;
}

.hero-box {
    padding: 20px;
    border-radius: 22px;
    background: linear-gradient(135deg, #FFF7E8 0%, #F8EFE2 100%);
    border: 1px solid #EEDFCB;
    margin-bottom: 18px;
}

.info-chip {
    display: inline-block;
    padding: 6px 11px;
    border-radius: 999px;
    background-color: #F1E6D8;
    color: #4B3A2E;
    font-size: 13px;
    font-weight: 700;
    margin-right: 6px;
    margin-bottom: 6px;
}

.result-badge-good {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 999px;
    background-color: #E7F5EC;
    color: #177245;
    font-size: 13px;
    font-weight: 800;
}

.result-badge-warning {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 999px;
    background-color: #FFF2D8;
    color: #B56A00;
    font-size: 13px;
    font-weight: 800;
}

.result-badge-danger {
    display: inline-block;
    padding: 7px 12px;
    border-radius: 999px;
    background-color: #FCE7EB;
    color: #B00020;
    font-size: 13px;
    font-weight: 800;
}

hr {
    margin-top: 1.2rem;
    margin-bottom: 1.2rem;
}

[data-testid="stMetricValue"] {
    font-size: 24px;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# Benchmark Data
# =========================================================

BENCHMARKS = {
    "일반 카페": {
        "monthly_kwh_per_m2": 28,
        "kwh_per_operating_hour": 5.5,
        "normal_bill_min": 300000,
        "normal_bill_max": 550000,
        "contract_power_low": 10,
        "contract_power_high": 20,
        "description": "음료 중심 카페 기준",
        "typical_devices": "커피머신, 제빙기, 쇼케이스, 냉장고, 에어컨"
    },
    "베이커리 카페": {
        "monthly_kwh_per_m2": 55,
        "kwh_per_operating_hour": 10.5,
        "normal_bill_min": 600000,
        "normal_bill_max": 1100000,
        "contract_power_low": 20,
        "contract_power_high": 35,
        "description": "오븐, 냉동고, 쇼케이스 포함 기준",
        "typical_devices": "오븐, 발효기, 냉동고, 쇼케이스, 에어컨"
    }
}


DEVICE_LOADS = {
    "쇼케이스": 0.8,
    "제빙기": 0.8,
    "오븐": 4.0,
    "냉장 냉동 장비": 0.3,
    "에어컨": 1.2,
}


# =========================================================
# Formatting Helpers
# =========================================================

def won(value):
    return f"{int(value):,}원"


def kwh(value):
    return f"{value:,.0f} kWh"


def pct(value):
    return f"{value:+.1f}%"


def safe_divide(a, b):
    if b == 0:
        return 0
    return a / b


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


def class_to_badge(css_class):
    if css_class == "good":
        return "result-badge-good"
    elif css_class == "warning":
        return "result-badge-warning"
    else:
        return "result-badge-danger"


def metric_card(title, value, caption=None, small=False):
    value_class = "metric-value-small" if small else "metric-value"
    caption_html = f"<div class='metric-caption'>{caption}</div>" if caption else ""

    st.markdown(f"""
    <div class="card-white">
        <div class="metric-title">{title}</div>
        <div class="{value_class}">{value}</div>
        {caption_html}
    </div>
    """, unsafe_allow_html=True)


def message_card(title, body, level="neutral"):
    css_class = {
        "good": "good",
        "warning": "warning",
        "danger": "danger",
        "neutral": "neutral"
    }.get(level, "neutral")

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">{title}</div>
        <p class="{css_class}">{body}</p>
    </div>
    """, unsafe_allow_html=True)


# =========================================================
# Session State
# =========================================================

if "selected_location_label" not in st.session_state:
    st.session_state["selected_location_label"] = "서울특별시 강남구 테헤란로"

if "latitude" not in st.session_state:
    st.session_state["latitude"] = 37.5013

if "longitude" not in st.session_state:
    st.session_state["longitude"] = 127.0396

if "last_search_message" not in st.session_state:
    st.session_state["last_search_message"] = ""


# =========================================================
# Kakao API
# =========================================================

def get_clean_kakao_key():
    raw_key = st.secrets.get("KAKAO_REST_API_KEY", "")

    if raw_key is None:
        raw_key = ""

    key = str(raw_key).strip()

    if key.startswith("KakaoAK"):
        key = key.replace("KakaoAK", "", 1).strip()

    if not key:
        return None, "Kakao REST API Key가 비어 있습니다. Streamlit Secrets를 확인하세요."

    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return None, "Kakao REST API Key에 한글 또는 잘못된 문자가 들어 있습니다. 실제 REST API Key만 입력해야 합니다."

    return key, None


def parse_kakao_documents(documents):
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

        x = item.get("x")
        y = item.get("y")

        if x is None or y is None:
            continue

        results.append({
            "label": display_address,
            "latitude": float(y),
            "longitude": float(x)
        })

    return results


def get_coordinates_from_kakao(address_query):
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

    headers = {
        "Authorization": f"KakaoAK {kakao_key}"
    }

    params = {
        "query": address_query.strip(),
        "analyze_type": "similar"
    }

    address_url = "https://dapi.kakao.com/v2/local/search/address.json"
    keyword_url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    try:
        response = requests.get(
            address_url,
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
                "message": "Kakao API 접근이 거부되었습니다. Kakao Developers에서 카카오맵 또는 Local API 사용 설정을 확인하세요.",
                "results": []
            }

        response.raise_for_status()
        data = response.json()
        documents = data.get("documents", [])
        results = parse_kakao_documents(documents)

        if results:
            return {
                "success": True,
                "message": "주소 검색 성공",
                "results": results
            }

        keyword_response = requests.get(
            keyword_url,
            headers=headers,
            params={"query": address_query.strip()},
            timeout=10
        )

        if keyword_response.status_code == 403:
            return {
                "success": False,
                "message": "Kakao API 접근이 거부되었습니다. Kakao Developers 설정을 확인하세요.",
                "results": []
            }

        keyword_response.raise_for_status()
        keyword_data = keyword_response.json()
        keyword_docs = keyword_data.get("documents", [])

        keyword_results = []

        for item in keyword_docs:
            place_name = item.get("place_name", "")
            address_name = item.get("road_address_name") or item.get("address_name") or place_name
            x = item.get("x")
            y = item.get("y")

            if x is None or y is None:
                continue

            label = address_name
            if place_name and place_name not in label:
                label = f"{place_name} · {address_name}"

            keyword_results.append({
                "label": label,
                "latitude": float(y),
                "longitude": float(x)
            })

        if keyword_results:
            return {
                "success": True,
                "message": "키워드 기반 위치 검색 성공",
                "results": keyword_results
            }

        return {
            "success": False,
            "message": "검색 결과가 없습니다. 도로명 주소나 구체적인 건물명을 입력하세요.",
            "results": []
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


# =========================================================
# Open Meteo API
# =========================================================

@st.cache_data(ttl=600)
def get_weather_open_meteo(latitude, longitude):
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


# =========================================================
# Map
# =========================================================

def show_location_map(latitude, longitude, label):
    if FOLIUM_AVAILABLE:
        m = folium.Map(
            location=[latitude, longitude],
            zoom_start=16,
            tiles="OpenStreetMap"
        )

        folium.CircleMarker(
            location=[latitude, longitude],
            radius=10,
            popup=label,
            tooltip=label,
            fill=True,
            fill_opacity=0.9
        ).add_to(m)

        folium.Circle(
            location=[latitude, longitude],
            radius=250,
            fill=True,
            fill_opacity=0.08
        ).add_to(m)

        map_data = st_folium(
            m,
            height=380,
            use_container_width=True,
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
                st.session_state["last_search_message"] = "지도에서 위치를 직접 선택했습니다."
                st.rerun()

    else:
        map_df = pd.DataFrame([{
            "lat": latitude,
            "lon": longitude
        }])

        st.map(map_df, latitude="lat", longitude="lon", zoom=15)
        st.info("지도 클릭 기능을 사용하려면 requirements.txt에 folium, streamlit-folium을 추가하세요.")


# =========================================================
# Diagnosis Logic
# =========================================================

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


def cooling_load_diagnosis(outdoor_temp, indoor_temp, indoor_humidity):
    temp_gap = indoor_temp - outdoor_temp

    if outdoor_temp >= 30 and indoor_temp <= 24:
        return (
            "냉방 부담 높음",
            "외기온도가 높은데 실내온도를 낮게 유지하고 있어 냉방 전력 사용이 커질 가능성이 있습니다.",
            "warning"
        )

    if outdoor_temp >= 30 and indoor_temp > 27:
        return (
            "쾌적성 위험",
            "외기온도와 실내온도가 모두 높은 편입니다. 냉방 성능, 출입문 개방, 실외기 상태를 먼저 확인하세요.",
            "danger"
        )

    if indoor_humidity >= 70:
        return (
            "습도 관리 필요",
            "실내습도가 높아 체감 쾌적성이 낮아질 수 있습니다. 제습 운전이나 환기 패턴 점검이 필요합니다.",
            "warning"
        )

    if abs(temp_gap) <= 3:
        return (
            "냉방 부담 보통",
            "현재 실내외 온도차가 크지 않아 냉방 부담이 과도하게 높게 나타나지는 않습니다.",
            "good"
        )

    return (
        "확인 필요",
        "현재 날씨와 실내 조건을 기준으로 냉방 설정과 장비 운전 패턴을 함께 확인하는 것이 좋습니다.",
        "neutral"
    )


def calculate_recommendations(
    store_type,
    monthly_kwh,
    monthly_bill,
    area_m2,
    monthly_hours,
    indoor_temp,
    indoor_humidity,
    outdoor_temp,
    plug_kwh_month,
    after_hours_ratio,
    contract_status,
    has_showcase,
    has_ice_machine,
    has_oven,
    refrigerator_count,
    ac_count,
    ratio_area,
    ratio_hour,
    price_per_kwh
):
    recommendations = []

    if ratio_area > 1.35:
        recommendations.append({
            "title": "면적 대비 전력사용량이 매우 높습니다",
            "body": "같은 업종과 면적 기준보다 전력 사용량이 높은 편입니다. 냉방 설정, 냉장 장비, 영업시간 외 장비 사용을 우선 점검하세요.",
            "impact": "high"
        })
    elif ratio_area > 1.15:
        recommendations.append({
            "title": "면적 대비 전력사용량이 높은 편입니다",
            "body": "매장 면적에 비해 월 전력사용량이 다소 높습니다. 냉장 장비 상태와 에어컨 운전 시간을 확인하세요.",
            "impact": "medium"
        })

    if ratio_hour > 1.25:
        recommendations.append({
            "title": "운영시간당 전력사용량이 높습니다",
            "body": "영업시간 동안 장비가 동시에 작동하면서 피크 전력이 커질 수 있습니다. 오븐, 제빙기, 에어컨의 동시 사용을 분산하세요.",
            "impact": "medium"
        })

    if indoor_temp < 24:
        recommendations.append({
            "title": "과냉방 가능성이 있습니다",
            "body": "영업시간 평균 실내온도가 낮은 편입니다. 고객 쾌적성을 해치지 않는 범위에서 설정온도를 1도 높이면 냉방 전력 절감 여지가 있습니다.",
            "impact": "medium"
        })
    elif indoor_temp > 27 and outdoor_temp > 28:
        recommendations.append({
            "title": "냉방 성능 점검이 필요합니다",
            "body": "실내온도가 높은 편입니다. 에너지 절감보다 고객 쾌적성과 냉방 성능 점검이 먼저 필요할 수 있습니다.",
            "impact": "high"
        })

    if indoor_humidity >= 70:
        recommendations.append({
            "title": "실내습도가 높습니다",
            "body": "습도가 높으면 같은 온도에서도 덥게 느껴질 수 있습니다. 제습 운전, 출입문 개방 시간, 환기 방식을 점검하세요.",
            "impact": "medium"
        })

    if plug_kwh_month > 0 and after_hours_ratio >= 25:
        estimated_waste = plug_kwh_month * after_hours_ratio / 100 * price_per_kwh

        recommendations.append({
            "title": "영업시간 외 장비 사용이 큽니다",
            "body": f"스마트플러그 장비의 영업시간 외 사용 비중이 높습니다. 폐점 후 자동 종료 또는 운전 스케줄 조정으로 월 약 {won(estimated_waste)} 수준의 낭비를 줄일 수 있습니다.",
            "impact": "high"
        })

    if contract_status in ["전력 여유 낮음", "계약전력 과다 가능성"]:
        recommendations.append({
            "title": "계약전력 확인이 필요합니다",
            "body": "계약전력은 기본요금과 운영 안정성에 영향을 줍니다. 최근 최대 사용 패턴을 확인한 뒤 조정 여부를 검토하세요.",
            "impact": "medium"
        })

    if has_showcase or refrigerator_count >= 2:
        recommendations.append({
            "title": "냉장 장비 상시 부하를 점검하세요",
            "body": "쇼케이스나 냉장 장비가 많은 매장은 24시간 전력 사용 비중이 커질 수 있습니다. 방열 공간, 문 패킹, 설정온도를 점검하세요.",
            "impact": "medium"
        })

    if has_ice_machine:
        recommendations.append({
            "title": "제빙기 운전 패턴을 확인하세요",
            "body": "제빙기는 여름철 전력 사용 증가에 영향을 줄 수 있습니다. 폐점 후 운전 상태와 주변 온도를 확인하세요.",
            "impact": "medium"
        })

    if has_oven or store_type == "베이커리 카페":
        recommendations.append({
            "title": "오븐과 냉방 피크를 분산하세요",
            "body": "오븐과 냉방이 동시에 작동하면 피크 전력이 커질 수 있습니다. 오븐 예열과 냉방 피크 시간이 겹치지 않도록 운영하세요.",
            "impact": "high"
        })

    if ac_count >= 2:
        recommendations.append({
            "title": "에어컨 순차 운전을 검토하세요",
            "body": "에어컨이 여러 대인 경우 동시에 강하게 켜기보다 구역별로 순차 운전하면 피크 부담을 줄일 수 있습니다.",
            "impact": "medium"
        })

    if not recommendations:
        recommendations.append({
            "title": "현재는 큰 이상 신호가 강하지 않습니다",
            "body": "월별 사용량과 실내온도 변화를 계속 기록하면 더 정확한 진단이 가능합니다.",
            "impact": "low"
        })

    impact_order = {"high": 0, "medium": 1, "low": 2}
    recommendations = sorted(recommendations, key=lambda x: impact_order.get(x["impact"], 3))

    return recommendations[:5]


def get_priority_label(impact):
    if impact == "high":
        return "우선 조치"
    elif impact == "medium":
        return "검토 필요"
    return "관찰"


def get_priority_color(impact):
    if impact == "high":
        return "danger"
    elif impact == "medium":
        return "warning"
    return "good"


# =========================================================
# Report
# =========================================================

def build_report(
    store_type,
    area_pyeong,
    monthly_kwh,
    monthly_bill,
    contract_power,
    energy_score,
    kwh_per_m2,
    kwh_per_hour,
    selected_location_label,
    outdoor_temp,
    outdoor_humidity,
    wind_speed,
    recommendations,
    summary
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    rec_text = ""
    for idx, rec in enumerate(recommendations, start=1):
        rec_text += f"{idx}. {rec['title']}\n   {rec['body']}\n\n"

    report = f"""
CafeWatt Energy Diagnosis Report
Generated at: {now}

1. Store Information
Store type: {store_type}
Area: {area_pyeong:.1f} pyeong
Location: {selected_location_label}

2. Electricity Information
Monthly electricity use: {monthly_kwh:,.0f} kWh
Monthly electricity bill: {monthly_bill:,.0f} KRW
Contract power: {contract_power:.1f} kW

3. Key Diagnosis
Energy score: {energy_score} / 100
Electricity use per area: {kwh_per_m2:.1f} kWh/m2
Electricity use per operating hour: {kwh_per_hour:.1f} kWh/hour

4. Weather
Outdoor temperature: {outdoor_temp:.1f} C
Outdoor humidity: {outdoor_humidity:.0f} %
Wind speed: {wind_speed:.1f} m/s

5. Recommendations
{rec_text}

6. Summary
{summary}

Note:
CafeWatt is an MVP diagnostic tool. Results are based on user inputs, benchmark assumptions, weather API data, and simplified equipment load assumptions.
"""
    return report


# =========================================================
# Header
# =========================================================

st.markdown('<div class="main-title">☕ CafeWatt</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">카페와 베이커리 카페의 전기요금, 실내환경, 장비 구성, 위치 기반 날씨를 연결해 에너지 사용 수준을 진단합니다.</div>',
    unsafe_allow_html=True
)

st.markdown("""
<div class="hero-box">
    <span class="info-chip">전기요금 진단</span>
    <span class="info-chip">주소 기반 날씨</span>
    <span class="info-chip">카페 장비 분석</span>
    <span class="info-chip">계약전력 점검</span>
    <span class="info-chip">절감 우선순위 추천</span>
</div>
""", unsafe_allow_html=True)


# =========================================================
# Sidebar Inputs
# =========================================================

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


# =========================================================
# Location and Weather
# =========================================================

st.markdown('<div class="section-title">매장 위치와 현재 날씨</div>', unsafe_allow_html=True)

location_col, map_col = st.columns([0.95, 1.45])

with location_col:
    address_query = st.text_input(
        "매장 주소",
        value=st.session_state["selected_location_label"],
        help="예시: 서울 관악구 남부순환로 1927, 서울특별시 강남구 테헤란로"
    )

    search_weather = st.button("주소로 위치와 날씨 불러오기", use_container_width=True)

    if search_weather:
        geo_data = get_coordinates_from_kakao(address_query)

        if geo_data["success"] and geo_data["results"]:
            first_result = geo_data["results"][0]

            st.session_state["selected_location_label"] = first_result["label"]
            st.session_state["latitude"] = first_result["latitude"]
            st.session_state["longitude"] = first_result["longitude"]
            st.session_state["last_search_message"] = geo_data["message"]

            st.rerun()

        else:
            st.session_state["last_search_message"] = geo_data["message"]

    if st.session_state["last_search_message"]:
        if "성공" in st.session_state["last_search_message"] or "선택" in st.session_state["last_search_message"]:
            st.success(st.session_state["last_search_message"])
        else:
            st.warning(st.session_state["last_search_message"])

    st.markdown(f"""
    <div class="card-soft">
        <div class="metric-title">현재 기준 위치</div>
        <b>{st.session_state["selected_location_label"]}</b><br>
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
wind_speed = 0.0

if weather_data["success"] and weather_data["temperature"] is not None:
    outdoor_temp = float(weather_data["temperature"])
    outdoor_humidity = float(weather_data["humidity"]) if weather_data["humidity"] is not None else 55
    wind_speed = float(weather_data["wind_speed"]) if weather_data["wind_speed"] is not None else 0.0

with map_col:
    show_location_map(latitude, longitude, selected_location_label)

weather_col1, weather_col2, weather_col3, weather_col4 = st.columns(4)

with weather_col1:
    metric_card("현재 외기온도", f"{outdoor_temp:.1f}°C")

with weather_col2:
    metric_card("현재 외기습도", f"{outdoor_humidity:.0f}%")

with weather_col3:
    metric_card("풍속", f"{wind_speed:.1f} m/s")

with weather_col4:
    metric_card("실내외 온도차", f"{indoor_temp - outdoor_temp:+.1f}°C")

st.divider()


# =========================================================
# Calculations
# =========================================================

benchmark = BENCHMARKS[store_type]

kwh_per_m2 = safe_divide(monthly_kwh, area_m2)
kwh_per_hour = safe_divide(monthly_kwh, monthly_hours)
price_per_kwh = safe_divide(monthly_bill, monthly_kwh)

ratio_area = safe_divide(kwh_per_m2, benchmark["monthly_kwh_per_m2"])
ratio_hour = safe_divide(kwh_per_hour, benchmark["kwh_per_operating_hour"])

area_grade, area_class = grade_from_ratio(ratio_area)
hour_grade, hour_class = grade_from_ratio(ratio_hour)

energy_score = score_from_ratio((ratio_area + ratio_hour) / 2)

base_peak = area_pyeong * 0.55 if store_type == "일반 카페" else area_pyeong * 1.1
device_extra = 0

if has_showcase:
    device_extra += DEVICE_LOADS["쇼케이스"]

if has_ice_machine:
    device_extra += DEVICE_LOADS["제빙기"]

if has_oven:
    device_extra += DEVICE_LOADS["오븐"]

device_extra += refrigerator_count * DEVICE_LOADS["냉장 냉동 장비"]
device_extra += ac_count * DEVICE_LOADS["에어컨"]

estimated_peak_kw = max(6, base_peak + device_extra)

contract_status, contract_message, contract_class = contract_power_diagnosis(
    store_type,
    contract_power,
    estimated_peak_kw
)

cooling_status, cooling_message, cooling_class = cooling_load_diagnosis(
    outdoor_temp,
    indoor_temp,
    indoor_humidity
)

recommendations = calculate_recommendations(
    store_type,
    monthly_kwh,
    monthly_bill,
    area_m2,
    monthly_hours,
    indoor_temp,
    indoor_humidity,
    outdoor_temp,
    plug_kwh_month,
    after_hours_ratio,
    contract_status,
    has_showcase,
    has_ice_machine,
    has_oven,
    refrigerator_count,
    ac_count,
    ratio_area,
    ratio_hour,
    price_per_kwh
)

estimated_saving_low = monthly_bill * 0.05
estimated_saving_high = monthly_bill * 0.15

if energy_score < 55:
    estimated_saving_low = monthly_bill * 0.08
    estimated_saving_high = monthly_bill * 0.22

elif energy_score >= 75:
    estimated_saving_low = monthly_bill * 0.03
    estimated_saving_high = monthly_bill * 0.08

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
        "스마트플러그 장비와 계약전력을 점검하면 추가 절감 가능성을 찾을 수 있습니다."
    )


# =========================================================
# Main Dashboard
# =========================================================

st.markdown('<div class="section-title">CafeWatt 핵심 진단 결과</div>', unsafe_allow_html=True)

score_col, kwh_col, bill_col, saving_col = st.columns([1, 1, 1, 1.35])

with score_col:
    metric_card("종합 에너지 점수", f"{energy_score}점", "100점에 가까울수록 효율적")

with kwh_col:
    metric_card("월 전력사용량", kwh(monthly_kwh), f"면적당 {kwh_per_m2:.1f} kWh/㎡")

with bill_col:
    metric_card("월 전기요금", won(monthly_bill), f"평균 단가 {price_per_kwh:.0f}원/kWh")

with saving_col:
    metric_card(
        "예상 절감 금액",
        f"{won(estimated_saving_low)}<br>~ {won(estimated_saving_high)}",
        "현재 입력값 기준 월 예상 범위",
        small=True
    )

st.success(summary)

st.divider()


# =========================================================
# Tabs
# =========================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "진단 요약",
    "장비와 계약전력",
    "날씨와 실내환경",
    "추천 조치",
    "리포트"
])


# =========================================================
# Tab 1
# =========================================================

with tab1:
    left, right = st.columns([1.1, 1])

    with left:
        st.markdown('<div class="section-title">업종 기준 비교</div>', unsafe_allow_html=True)

        st.markdown(f"""
        <div class="card">
            <div class="metric-title">업종 기준</div>
            <div class="metric-value">{store_type}</div>
            <p>{benchmark["description"]}</p>
            <p class="small-text">일반 장비 구성: {benchmark["typical_devices"]}</p>
        </div>
        """, unsafe_allow_html=True)

        area_badge = class_to_badge(area_class)
        hour_badge = class_to_badge(hour_class)

        st.markdown(f"""
        <div class="card-white">
            <div class="metric-title">면적당 전력사용량</div>
            <div class="metric-value">{kwh_per_m2:.1f} kWh/㎡</div>
            <p>업종 평균 대비 <span class="{area_badge}">{area_grade}</span></p>
            <p class="small-text">평균 대비 {pct((ratio_area - 1) * 100)} 수준입니다.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="card-white">
            <div class="metric-title">운영시간당 전력사용량</div>
            <div class="metric-value">{kwh_per_hour:.1f} kWh/hour</div>
            <p>운영시간 기준 <span class="{hour_badge}">{hour_grade}</span></p>
            <p class="small-text">평균 대비 {pct((ratio_hour - 1) * 100)} 수준입니다.</p>
        </div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-title">운영 정보</div>', unsafe_allow_html=True)

        op1, op2 = st.columns(2)

        with op1:
            metric_card("매장 면적", f"{area_pyeong:.1f}평", f"{area_m2:.1f}㎡")

        with op2:
            metric_card("월 운영시간", f"{monthly_hours:.0f}시간", f"{business_days}일 운영")

        op3, op4 = st.columns(2)

        with op3:
            metric_card("일 운영시간", f"{open_hours:.1f}시간", f"{open_time.strftime('%H:%M')} ~ {close_time.strftime('%H:%M')}")

        with op4:
            metric_card("전기 단가", f"{price_per_kwh:.0f}원/kWh", "요금 ÷ 사용량 기준")

        chart_df = pd.DataFrame({
            "항목": ["면적 기준", "운영시간 기준"],
            "업종 평균 대비 비율": [ratio_area, ratio_hour]
        })

        st.bar_chart(
            chart_df,
            x="항목",
            y="업종 평균 대비 비율",
            use_container_width=True
        )

        st.caption("1.0은 업종 평균 수준을 의미합니다.")


# =========================================================
# Tab 2
# =========================================================

with tab2:
    st.markdown('<div class="section-title">장비 구성과 피크부하 추정</div>', unsafe_allow_html=True)

    device_col1, device_col2, device_col3, device_col4, device_col5 = st.columns(5)

    with device_col1:
        metric_card("쇼케이스", "있음" if has_showcase else "없음")

    with device_col2:
        metric_card("제빙기", "있음" if has_ice_machine else "없음")

    with device_col3:
        metric_card("오븐", "있음" if has_oven else "없음")

    with device_col4:
        metric_card("냉장 냉동 장비", f"{refrigerator_count}개")

    with device_col5:
        metric_card("에어컨", f"{ac_count}대")

    left, right = st.columns([1, 1])

    with left:
        st.markdown(f"""
        <div class="card">
            <div class="metric-title">추정 피크부하</div>
            <div class="metric-value">{estimated_peak_kw:.1f} kW</div>
            <p class="small-text">입력된 장비 구성과 매장 면적을 바탕으로 단순 추정한 값입니다.</p>
        </div>
        """, unsafe_allow_html=True)

        device_load_df = pd.DataFrame({
            "구분": ["기본부하", "장비 추가부하"],
            "추정 kW": [base_peak, device_extra]
        })

        st.bar_chart(device_load_df, x="구분", y="추정 kW", use_container_width=True)

    with right:
        badge = class_to_badge(contract_class)

        st.markdown(f"""
        <div class="card">
            <div class="metric-title">계약전력 진단</div>
            <div class="metric-value">{contract_power:.0f} kW</div>
            <p>진단: <span class="{badge}">{contract_status}</span></p>
            <p>{contract_message}</p>
        </div>
        """, unsafe_allow_html=True)

        if has_oven and store_type == "일반 카페":
            st.warning("오븐이 있는 경우 일반 카페보다 베이커리 카페에 가까운 전력 패턴이 나타날 수 있습니다.")


# =========================================================
# Tab 3
# =========================================================

with tab3:
    st.markdown('<div class="section-title">날씨와 실내환경 진단</div>', unsafe_allow_html=True)

    env_col1, env_col2, env_col3, env_col4 = st.columns(4)

    with env_col1:
        metric_card("외기온도", f"{outdoor_temp:.1f}°C")

    with env_col2:
        metric_card("실내온도", f"{indoor_temp:.1f}°C")

    with env_col3:
        metric_card("실내습도", f"{indoor_humidity:.0f}%")

    with env_col4:
        metric_card("실내외 온도차", f"{indoor_temp - outdoor_temp:+.1f}°C")

    cooling_badge = class_to_badge(cooling_class if cooling_class != "neutral" else "warning")

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">냉방 부담 진단</div>
        <div class="metric-value-small">{cooling_status}</div>
        <p>{cooling_message}</p>
    </div>
    """, unsafe_allow_html=True)

    env_df = pd.DataFrame({
        "항목": ["외기온도", "실내온도", "실내습도"],
        "값": [outdoor_temp, indoor_temp, indoor_humidity]
    })

    st.dataframe(env_df, use_container_width=True, hide_index=True)

    st.caption(f"날씨 기준 위치: {selected_location_label}")


# =========================================================
# Tab 4
# =========================================================

with tab4:
    st.markdown('<div class="section-title">CafeWatt 추천 조치</div>', unsafe_allow_html=True)

    for idx, rec in enumerate(recommendations, start=1):
        impact = rec["impact"]
        label = get_priority_label(impact)
        color = get_priority_color(impact)
        badge = class_to_badge(color)

        st.markdown(f"""
        <div class="card-white">
            <div class="metric-title">추천 {idx}</div>
            <div class="metric-value-small">{rec["title"]}</div>
            <p><span class="{badge}">{label}</span></p>
            <p>{rec["body"]}</p>
        </div>
        """, unsafe_allow_html=True)

    st.info("추천 조치는 입력값 기반의 우선순위입니다. 실제 절감 효과는 장비 효율, 사용 패턴, 전기요금제, 계절에 따라 달라질 수 있습니다.")


# =========================================================
# Tab 5
# =========================================================

with tab5:
    st.markdown('<div class="section-title">진단 리포트 다운로드</div>', unsafe_allow_html=True)

    report_text = build_report(
        store_type,
        area_pyeong,
        monthly_kwh,
        monthly_bill,
        contract_power,
        energy_score,
        kwh_per_m2,
        kwh_per_hour,
        selected_location_label,
        outdoor_temp,
        outdoor_humidity,
        wind_speed,
        recommendations,
        summary
    )

    st.text_area(
        "리포트 미리보기",
        report_text,
        height=420
    )

    file_name = f"CafeWatt_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

    st.download_button(
        label="리포트 다운로드",
        data=report_text,
        file_name=file_name,
        mime="text/plain",
        use_container_width=True
    )


# =========================================================
# Footer
# =========================================================

st.divider()

with st.expander("CafeWatt 진단 기준 안내"):
    st.write("""
    CafeWatt는 카페와 베이커리 카페의 기본 에너지 진단용 MVP입니다.

    현재 결과는 입력값, 간단한 업종 기준값, 위치 기반 날씨 데이터, 장비 구성 가정을 바탕으로 계산됩니다.
    실제 서비스에서는 공공데이터, 실제 사용자 데이터, 센서 데이터가 누적되면서 업종 평균 기준과 절감 예측 정확도를 계속 개선해야 합니다.

    계약전력 진단은 사전 참고용입니다.
    실제 계약전력 변경은 한전, 전기공사업체, 전기기사와 확인해야 합니다.

    스마트플러그 분석은 연결된 특정 장비의 사용량만 보여줍니다.
    매장 전체 전력사용량은 월 전력사용량 입력값을 기준으로 판단합니다.

    주소 검색은 Kakao Local API를 사용하고, 날씨 데이터는 Open Meteo API를 사용합니다.
    """)

st.caption("CafeWatt MVP 0.5 | 카페 전기요금 진단 AI")