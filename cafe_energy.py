import streamlit as st
import pandas as pd
import requests
from datetime import time, datetime
from io import BytesIO

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except Exception:
    FOLIUM_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import simpleSplit
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


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
.good { color: #177245; font-weight: 800; }
.warning { color: #B56A00; font-weight: 800; }
.danger { color: #B00020; font-weight: 800; }
.neutral { color: #444444; font-weight: 800; }
.small-text { font-size: 13px; color: #777777; }
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
.equipment-row {
    padding: 10px 12px;
    border-radius: 14px;
    background-color: #FFFFFF;
    border: 1px solid #EFE7DB;
    margin-bottom: 8px;
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
# Base Assumptions
# =========================================================

BASE_BENCHMARK = {
    "monthly_kwh_per_operating_hour": 6.2,
    "monthly_kwh_per_m2_reference": 32,
    "contract_power_low": 10,
    "contract_power_high": 25,
    "description": "카페 기본 운영 기준. 베이커리 성격은 오븐, 발효기, 냉동고 등 장비 구성으로 자동 반영합니다."
}

MANAGEMENT_TIERS = {
    "free": {
        "name": "Free",
        "price": "0원",
        "target": "1회 진단, 간단 리포트",
        "label": "무료 진단 권장"
    },
    "basic": {
        "name": "Basic",
        "price": "월 9,900원 ~ 14,900원",
        "target": "소형, 일반 카페",
        "label": "정기 점검 권장"
    },
    "pro": {
        "name": "Pro",
        "price": "월 29,000원 ~ 39,000원",
        "target": "중형, 베이커리형, 장비 많은 카페",
        "label": "유료 관리 검토"
    },
    "business": {
        "name": "Business",
        "price": "매장당 월 49,000원 이상",
        "target": "다점포, 프랜차이즈",
        "label": "다점포 관리 검토"
    }
}

BASIC_PRICE_LOW = 9900
BASIC_PRICE_HIGH = 14900
PRO_PRICE_LOW = 29000
PRO_PRICE_HIGH = 39000

EQUIPMENT_CATALOG = {
    "espresso_machine": {"label": "에스프레소 머신", "kw": 2.5, "default": 1, "essential": True},
    "grinder": {"label": "그라인더", "kw": 0.4, "default": 1, "essential": True},
    "showcase": {"label": "쇼케이스", "kw": 0.8, "default": 1, "essential": False},
    "ice_machine": {"label": "제빙기", "kw": 0.8, "default": 1, "essential": False},
    "refrigerator": {"label": "냉장고", "kw": 0.35, "default": 2, "essential": True},
    "freezer": {"label": "냉동고", "kw": 0.45, "default": 1, "essential": False},
    "oven": {"label": "오븐", "kw": 4.0, "default": 1, "essential": False},
    "proofer": {"label": "발효기", "kw": 1.5, "default": 1, "essential": False},
    "dishwasher": {"label": "식기세척기", "kw": 1.2, "default": 1, "essential": False},
    "ac": {"label": "에어컨", "kw": 1.2, "default": 2, "essential": True},
    "ventilation": {"label": "환기팬 또는 후드", "kw": 0.5, "default": 1, "essential": False},
}

DAYS = [
    ("mon", "월"),
    ("tue", "화"),
    ("wed", "수"),
    ("thu", "목"),
    ("fri", "금"),
    ("sat", "토"),
    ("sun", "일"),
]


# =========================================================
# Sample Profiles and Input Persistence
# =========================================================

SAMPLE_PROFILES = {
    "소형 테이크아웃 카페": {
        "area_input_unit": "평",
        "area_value": 10.0,
        "schedule_mode": "간단 입력",
        "open_time": "08:00",
        "close_time": "20:00",
        "business_days": 26,
        "monthly_kwh": 950,
        "monthly_bill": 230000,
        "contract_power": 10.0,
        "indoor_temp": 25.5,
        "indoor_humidity": 55,
        "equipment_counts": {
            "espresso_machine": 1,
            "grinder": 1,
            "showcase": 1,
            "ice_machine": 0,
            "refrigerator": 1,
            "freezer": 0,
            "oven": 0,
            "proofer": 0,
            "dishwasher": 0,
            "ac": 1,
            "ventilation": 1,
        },
        "smart_plug_entries": []
    },
    "일반 카페": {
        "area_input_unit": "평",
        "area_value": 22.0,
        "schedule_mode": "간단 입력",
        "open_time": "08:00",
        "close_time": "22:00",
        "business_days": 28,
        "monthly_kwh": 1800,
        "monthly_bill": 420000,
        "contract_power": 15.0,
        "indoor_temp": 25.5,
        "indoor_humidity": 55,
        "equipment_counts": {
            "espresso_machine": 1,
            "grinder": 2,
            "showcase": 1,
            "ice_machine": 1,
            "refrigerator": 2,
            "freezer": 1,
            "oven": 0,
            "proofer": 0,
            "dishwasher": 1,
            "ac": 2,
            "ventilation": 1,
        },
        "smart_plug_entries": [
            {"device": "쇼케이스 냉장고", "daily_kwh": 4.5, "after_hours_ratio": 30}
        ]
    },
    "베이커리형 카페": {
        "area_input_unit": "평",
        "area_value": 35.0,
        "schedule_mode": "간단 입력",
        "open_time": "08:00",
        "close_time": "23:00",
        "business_days": 30,
        "monthly_kwh": 4200,
        "monthly_bill": 950000,
        "contract_power": 30.0,
        "indoor_temp": 26.0,
        "indoor_humidity": 58,
        "equipment_counts": {
            "espresso_machine": 2,
            "grinder": 2,
            "showcase": 2,
            "ice_machine": 1,
            "refrigerator": 3,
            "freezer": 2,
            "oven": 2,
            "proofer": 1,
            "dishwasher": 1,
            "ac": 3,
            "ventilation": 2,
        },
        "smart_plug_entries": [
            {"device": "쇼케이스 냉장고", "daily_kwh": 7.5, "after_hours_ratio": 55},
            {"device": "제빙기", "daily_kwh": 5.0, "after_hours_ratio": 35}
        ]
    },
}


def parse_time_string(value, fallback):
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        try:
            hour, minute = value.split(":")[:2]
            return time(int(hour), int(minute))
        except Exception:
            return fallback
    return fallback


def time_to_string(value):
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)


def apply_input_profile(profile):
    st.session_state["area_input_unit"] = profile.get("area_input_unit", "평")
    st.session_state["area_value"] = float(profile.get("area_value", 20.0))
    st.session_state["schedule_mode"] = profile.get("schedule_mode", "간단 입력")
    st.session_state["open_time_main"] = parse_time_string(profile.get("open_time", "08:00"), time(8, 0))
    st.session_state["close_time_main"] = parse_time_string(profile.get("close_time", "22:00"), time(22, 0))
    st.session_state["business_days"] = int(profile.get("business_days", 28))
    st.session_state["monthly_kwh"] = int(profile.get("monthly_kwh", 1800))
    st.session_state["monthly_bill"] = int(profile.get("monthly_bill", 420000))
    st.session_state["monthly_kwh_text"] = format_number_text(profile.get("monthly_kwh", 1800))
    st.session_state["monthly_bill_text"] = format_number_text(profile.get("monthly_bill", 420000))
    st.session_state["contract_power"] = float(profile.get("contract_power", 15.0))
    st.session_state["indoor_temp"] = float(profile.get("indoor_temp", 25.5))
    st.session_state["indoor_humidity"] = int(profile.get("indoor_humidity", 55))

    equipment_counts = profile.get("equipment_counts", {})
    for key, item in EQUIPMENT_CATALOG.items():
        count = int(equipment_counts.get(key, 0))
        st.session_state[f"has_{key}"] = count > 0
        if count > 0:
            st.session_state[f"count_{key}"] = count

    smart_entries = profile.get("smart_plug_entries", [])
    st.session_state["smart_plug_count"] = len(smart_entries)
    for i, entry in enumerate(smart_entries):
        st.session_state[f"plug_device_{i}"] = entry.get("device", "쇼케이스 냉장고")
        st.session_state[f"plug_kwh_day_{i}"] = float(entry.get("daily_kwh", 4.5))
        st.session_state[f"after_hours_ratio_{i}"] = int(entry.get("after_hours_ratio", 25))


def initialize_default_inputs():
    if st.session_state.get("inputs_initialized"):
        return
    apply_input_profile(SAMPLE_PROFILES["일반 카페"])
    st.session_state["inputs_initialized"] = True


def build_saved_input_state(
    area_input_unit,
    area_value,
    schedule_mode,
    open_time,
    close_time,
    business_days,
    monthly_kwh,
    monthly_bill,
    contract_power,
    indoor_temp,
    indoor_humidity,
    equipment_counts,
    smart_plug_entries
):
    compact_plugs = []
    for entry in smart_plug_entries:
        compact_plugs.append({
            "device": entry.get("device", "기타 장비"),
            "daily_kwh": float(entry.get("daily_kwh", 0)),
            "after_hours_ratio": int(entry.get("after_hours_ratio", 0)),
        })

    return {
        "app": "CafeWatt",
        "version": "0.9",
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "area_input_unit": area_input_unit,
        "area_value": float(area_value),
        "schedule_mode": schedule_mode,
        "open_time": time_to_string(open_time),
        "close_time": time_to_string(close_time),
        "business_days": int(business_days),
        "monthly_kwh": int(monthly_kwh),
        "monthly_bill": int(monthly_bill),
        "contract_power": float(contract_power),
        "indoor_temp": float(indoor_temp),
        "indoor_humidity": int(indoor_humidity),
        "equipment_counts": equipment_counts,
        "smart_plug_entries": compact_plugs,
        "selected_location_label": st.session_state.get("selected_location_label", ""),
        "latitude": st.session_state.get("latitude", None),
        "longitude": st.session_state.get("longitude", None),
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
    return 0 if b == 0 else a / b


def parse_number_text(value, fallback=0):
    """쉼표가 포함된 숫자 입력값을 안전하게 정수로 변환합니다."""
    try:
        cleaned = str(value).replace(",", "").replace("원", "").replace("kWh", "").strip()
        if cleaned == "":
            return fallback
        return int(float(cleaned))
    except Exception:
        return fallback


def format_number_text(value):
    try:
        return f"{int(float(value)):,}"
    except Exception:
        return str(value)


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


def class_to_badge(css_class):
    if css_class == "good":
        return "result-badge-good"
    if css_class == "warning":
        return "result-badge-warning"
    return "result-badge-danger"


def grade_from_ratio(ratio):
    if ratio < 0.85:
        return "낮음", "good"
    if ratio <= 1.15:
        return "평균 수준", "good"
    if ratio <= 1.35:
        return "높음", "warning"
    return "매우 높음", "danger"


def score_from_ratio(ratio):
    if ratio <= 0.85:
        return 88
    if ratio <= 1.0:
        return 78
    if ratio <= 1.15:
        return 68
    if ratio <= 1.35:
        return 55
    return 42


def equipment_input(key, label, default_count, default_checked=False, max_count=10):
    checked = st.sidebar.checkbox(f"{label} 있음", value=default_checked, key=f"has_{key}")
    count = 0
    if checked:
        count = st.sidebar.slider(
            f"{label} 개수",
            min_value=1,
            max_value=max_count,
            value=default_count,
            key=f"count_{key}"
        )
    return checked, count


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

# 첫 화면 기본값을 카페 평균적인 입력값으로 세팅합니다.
# 이전 세션에서 0일, 현재 시각, 계약전력 0kW처럼 비어 있는 값이 남아 있으면 평균값으로 보정합니다.
if "average_defaults_v13_applied" not in st.session_state:
    default_profile = SAMPLE_PROFILES.get("일반 카페", {})

    st.session_state.setdefault("area_input_unit", default_profile.get("area_input_unit", "평"))
    st.session_state.setdefault("area_value", float(default_profile.get("area_value", 22.0)))
    st.session_state.setdefault("schedule_mode", "간단 입력")
    st.session_state["open_time_main"] = parse_time_string(default_profile.get("open_time", "09:00"), time(9, 0))
    st.session_state["close_time_main"] = parse_time_string(default_profile.get("close_time", "22:00"), time(22, 0))
    st.session_state["business_days"] = int(default_profile.get("business_days", 28))
    st.session_state.setdefault("monthly_kwh", int(default_profile.get("monthly_kwh", 1800)))
    st.session_state.setdefault("monthly_bill", int(default_profile.get("monthly_bill", 420000)))
    st.session_state.setdefault("monthly_kwh_text", format_number_text(default_profile.get("monthly_kwh", 1800)))
    st.session_state.setdefault("monthly_bill_text", format_number_text(default_profile.get("monthly_bill", 420000)))
    st.session_state["contract_power"] = float(default_profile.get("contract_power", 15.0))
    st.session_state.setdefault("indoor_temp", float(default_profile.get("indoor_temp", 25.5)))
    st.session_state.setdefault("indoor_humidity", int(default_profile.get("indoor_humidity", 55)))

    # 기본 장비 구성도 일반 카페 기준으로 보정합니다.
    for key, item in EQUIPMENT_CATALOG.items():
        default_count = int(default_profile.get("equipment_counts", {}).get(key, item["default"] if item.get("essential") else 0))
        st.session_state[f"has_{key}"] = default_count > 0
        if default_count > 0:
            st.session_state[f"count_{key}"] = default_count

    st.session_state["average_defaults_v13_applied"] = True

# 안전 보정: 사용자가 아직 값을 넣기 전 0 또는 현재 시각으로 남은 경우 평균값으로 보정합니다.
if st.session_state.get("business_days", 28) == 0:
    st.session_state["business_days"] = 28
if float(st.session_state.get("contract_power", 15.0) or 0) == 0:
    st.session_state["contract_power"] = 15.0
if st.session_state.get("open_time_main") == st.session_state.get("close_time_main"):
    st.session_state["open_time_main"] = time(9, 0)
    st.session_state["close_time_main"] = time(22, 0)


# =========================================================
# Kakao API
# =========================================================

def get_clean_kakao_key():
    raw_key = st.secrets.get("KAKAO_REST_API_KEY", "")
    key = str(raw_key or "").strip()

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
        return {"success": False, "message": "주소를 입력하세요.", "results": []}

    kakao_key, key_error = get_clean_kakao_key()
    if key_error:
        return {"success": False, "message": key_error, "results": []}

    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    query = address_query.strip()
    address_url = "https://dapi.kakao.com/v2/local/search/address.json"
    keyword_url = "https://dapi.kakao.com/v2/local/search/keyword.json"

    try:
        response = requests.get(
            address_url,
            headers=headers,
            params={"query": query, "analyze_type": "similar"},
            timeout=10
        )

        if response.status_code == 401:
            return {"success": False, "message": "Kakao API 인증에 실패했습니다. REST API Key를 확인하세요.", "results": []}
        if response.status_code == 403:
            return {"success": False, "message": "Kakao API 접근이 거부되었습니다. Kakao Developers에서 카카오맵 또는 Local API 사용 설정을 확인하세요.", "results": []}

        response.raise_for_status()
        data = response.json()
        results = parse_kakao_documents(data.get("documents", []))

        if results:
            return {"success": True, "message": "주소 검색 성공", "results": results}

        keyword_response = requests.get(
            keyword_url,
            headers=headers,
            params={"query": query},
            timeout=10
        )

        if keyword_response.status_code == 403:
            return {"success": False, "message": "Kakao API 접근이 거부되었습니다. Kakao Developers 설정을 확인하세요.", "results": []}

        keyword_response.raise_for_status()
        keyword_data = keyword_response.json()
        keyword_results = []

        for item in keyword_data.get("documents", []):
            place_name = item.get("place_name", "")
            address_name = item.get("road_address_name") or item.get("address_name") or place_name
            x = item.get("x")
            y = item.get("y")
            if x is None or y is None:
                continue
            label = address_name
            if place_name and place_name not in label:
                label = f"{place_name} · {address_name}"
            keyword_results.append({"label": label, "latitude": float(y), "longitude": float(x)})

        if keyword_results:
            return {"success": True, "message": "키워드 기반 위치 검색 성공", "results": keyword_results}

        return {"success": False, "message": "검색 결과가 없습니다. 도로명 주소나 구체적인 건물명을 입력하세요.", "results": []}

    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Kakao API 요청 실패: {e}", "results": []}
    except Exception as e:
        return {"success": False, "message": f"주소 검색 처리 중 오류: {e}", "results": []}


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
        return {"success": False, "error": str(e), "temperature": None, "humidity": None, "wind_speed": None, "raw": None}


# =========================================================
# Map
# =========================================================

def show_location_map(latitude, longitude, label):
    if FOLIUM_AVAILABLE:
        m = folium.Map(location=[latitude, longitude], zoom_start=16, tiles="OpenStreetMap")
        folium.CircleMarker(
            location=[latitude, longitude],
            radius=10,
            popup=label,
            tooltip=label,
            fill=True,
            fill_opacity=0.9
        ).add_to(m)
        folium.Circle(location=[latitude, longitude], radius=250, fill=True, fill_opacity=0.08).add_to(m)

        map_data = st_folium(m, height=380, use_container_width=True, key="cafewatt_map")
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
        map_df = pd.DataFrame([{"lat": latitude, "lon": longitude}])
        st.map(map_df, latitude="lat", longitude="lon", zoom=15)
        st.info("지도 클릭 기능을 사용하려면 requirements.txt에 folium, streamlit-folium을 추가하세요.")


# =========================================================
# Diagnosis Logic
# =========================================================

def adjusted_benchmark_hour(equipment_counts):
    benchmark = BASE_BENCHMARK["monthly_kwh_per_operating_hour"]

    if equipment_counts.get("oven", 0) > 0:
        benchmark += 3.0
    if equipment_counts.get("proofer", 0) > 0:
        benchmark += 1.0
    if equipment_counts.get("freezer", 0) > 0:
        benchmark += 0.7 * equipment_counts.get("freezer", 0)
    if equipment_counts.get("showcase", 0) > 0:
        benchmark += 0.7 * equipment_counts.get("showcase", 0)
    if equipment_counts.get("ice_machine", 0) > 0:
        benchmark += 0.5

    return benchmark


def estimate_equipment_peak_kw(area_pyeong, equipment_counts):
    base_peak = max(4.0, area_pyeong * 0.45)
    equipment_peak = 0

    for key, count in equipment_counts.items():
        equipment_peak += EQUIPMENT_CATALOG[key]["kw"] * count

    simultaneous_factor = 0.55
    estimated_peak = base_peak + equipment_peak * simultaneous_factor
    return max(6, estimated_peak), base_peak, equipment_peak * simultaneous_factor


def contract_power_diagnosis(contract_power, estimated_peak_kw):
    low = BASE_BENCHMARK["contract_power_low"]
    high = BASE_BENCHMARK["contract_power_high"]

    if contract_power == 0:
        return "정보 부족", "계약전력을 입력하면 기본요금 부담과 전력 여유를 간단히 진단할 수 있습니다.", "warning"

    usage_ratio = estimated_peak_kw / contract_power if contract_power > 0 else 0

    if usage_ratio >= 0.9:
        return "전력 여유 낮음", "현재 장비 구성에서는 피크 시간대 전력 여유가 낮을 수 있습니다. 냉방기, 커피머신, 제빙기, 오븐의 동시 사용을 분산하는 것이 좋습니다.", "danger"

    if usage_ratio <= 0.5 and contract_power > high:
        return "계약전력 과다 가능성", "입력된 장비 기준으로는 계약전력이 다소 높을 가능성이 있습니다. 실제 최대 사용량을 확인한 뒤 계약전력 조정을 검토할 수 있습니다.", "warning"

    if low <= contract_power <= high:
        return "대체로 적정", "현재 규모와 장비 구성 기준으로 계약전력이 일반적인 범위에 있습니다. 다만 실제 피크 사용량 확인이 필요합니다.", "good"

    return "확인 필요", "계약전력은 장비 구성과 동시 사용률에 따라 달라집니다. 한전, 전기기사 또는 전기공사업체와 실제 적정성을 확인하는 것이 좋습니다.", "warning"


def cooling_load_diagnosis(outdoor_temp, indoor_temp, indoor_humidity):
    temp_gap = indoor_temp - outdoor_temp

    if outdoor_temp >= 30 and indoor_temp <= 24:
        return "냉방 부담 높음", "외기온도가 높은데 실내온도를 낮게 유지하고 있어 냉방 전력 사용이 커질 가능성이 있습니다.", "warning"
    if outdoor_temp >= 30 and indoor_temp > 27:
        return "쾌적성 위험", "외기온도와 실내온도가 모두 높은 편입니다. 냉방 성능, 출입문 개방, 실외기 상태를 먼저 확인하세요.", "danger"
    if indoor_humidity >= 70:
        return "습도 관리 필요", "실내습도가 높아 체감 쾌적성이 낮아질 수 있습니다. 제습 운전이나 환기 패턴 점검이 필요합니다.", "warning"
    if abs(temp_gap) <= 3:
        return "냉방 부담 보통", "현재 실내외 온도차가 크지 않아 냉방 부담이 과도하게 높게 나타나지는 않습니다.", "good"
    return "확인 필요", "현재 날씨와 실내 조건을 기준으로 냉방 설정과 장비 운전 패턴을 함께 확인하는 것이 좋습니다.", "neutral"


def calculate_reliability(monthly_kwh, monthly_bill, contract_power, equipment_counts, schedule_mode, has_weather, plug_device):
    score = 35
    reasons = []

    if monthly_kwh > 0 and monthly_bill > 0:
        score += 20
        reasons.append("월 전력사용량과 전기요금이 모두 입력되었습니다.")
    else:
        reasons.append("월 전력사용량 또는 전기요금 정보가 부족합니다.")

    if sum(equipment_counts.values()) >= 3:
        score += 15
        reasons.append("주요 장비 구성이 입력되었습니다.")
    else:
        reasons.append("장비 구성이 제한적으로 입력되어 있습니다.")

    if schedule_mode == "요일별 입력":
        score += 15
        reasons.append("요일별 운영시간이 반영되었습니다.")
    else:
        score += 8
        reasons.append("간단 운영시간 기준으로 계산되었습니다.")

    if contract_power > 0:
        score += 7
        reasons.append("계약전력 정보가 포함되었습니다.")

    if has_weather:
        score += 5
        reasons.append("위치 기반 현재 날씨가 반영되었습니다.")

    if plug_device != "없음":
        score += 3
        reasons.append("스마트플러그 장비 사용량이 포함되었습니다.")

    score = min(score, 100)

    if score >= 80:
        return score, "높음", "good", reasons
    if score >= 60:
        return score, "보통", "warning", reasons
    return score, "낮음", "danger", reasons


def calculate_recommendations(
    monthly_kwh,
    monthly_bill,
    monthly_hours,
    indoor_temp,
    indoor_humidity,
    outdoor_temp,
    plug_kwh_month,
    after_hours_ratio,
    contract_status,
    equipment_counts,
    ratio_hour,
    price_per_kwh
):
    recommendations = []

    if ratio_hour > 1.35:
        recommendations.append({
            "title": "운영시간당 전력사용량이 매우 높습니다",
            "body": "영업시간 동안 장비가 동시에 작동하면서 전력 사용이 커질 수 있습니다. 오븐, 제빙기, 에어컨, 냉장 장비의 동시 사용 패턴을 우선 점검하세요.",
            "impact": "high"
        })
    elif ratio_hour > 1.15:
        recommendations.append({
            "title": "운영시간당 전력사용량이 높은 편입니다",
            "body": "월 운영시간 대비 전력사용량이 다소 높습니다. 냉방 운전 시간, 냉장 장비 상태, 폐점 후 장비 사용을 확인하세요.",
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
            "body": f"스마트플러그로 확인된 장비들의 영업시간 외 사용 비중이 높습니다. 폐점 후 자동 종료 또는 운전 스케줄 조정으로 월 약 {won(estimated_waste)} 수준의 낭비를 줄일 수 있습니다.",
            "impact": "high"
        })

    if contract_status in ["전력 여유 낮음", "계약전력 과다 가능성"]:
        recommendations.append({
            "title": "계약전력 확인이 필요합니다",
            "body": "계약전력은 기본요금과 운영 안정성에 영향을 줍니다. 최근 최대 사용 패턴을 확인한 뒤 조정 여부를 검토하세요.",
            "impact": "medium"
        })

    if equipment_counts.get("showcase", 0) > 0 or equipment_counts.get("refrigerator", 0) + equipment_counts.get("freezer", 0) >= 3:
        recommendations.append({
            "title": "냉장 장비 상시 부하를 점검하세요",
            "body": "쇼케이스, 냉장고, 냉동고가 많은 매장은 24시간 전력 사용 비중이 커질 수 있습니다. 방열 공간, 문 패킹, 설정온도를 점검하세요.",
            "impact": "medium"
        })

    if equipment_counts.get("ice_machine", 0) > 0:
        recommendations.append({
            "title": "제빙기 운전 패턴을 확인하세요",
            "body": "제빙기는 여름철 전력 사용 증가에 영향을 줄 수 있습니다. 폐점 후 운전 상태와 주변 온도를 확인하세요.",
            "impact": "medium"
        })

    if equipment_counts.get("oven", 0) > 0 or equipment_counts.get("proofer", 0) > 0:
        recommendations.append({
            "title": "베이커리 장비와 냉방 피크를 분산하세요",
            "body": "오븐이나 발효기와 냉방이 동시에 작동하면 피크 전력이 커질 수 있습니다. 예열 시간과 냉방 피크 시간이 겹치지 않도록 운영하세요.",
            "impact": "high"
        })

    if equipment_counts.get("ac", 0) >= 2:
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
    return sorted(recommendations, key=lambda x: impact_order.get(x["impact"], 3))[:5]




def calculate_savings_breakdown(
    monthly_bill,
    price_per_kwh,
    indoor_temp,
    outdoor_temp,
    ratio_hour,
    contract_status,
    equipment_counts,
    smart_plug_entries,
    after_hours_kwh_total
):
    """입력값 기반으로 월 예상 절감 금액을 항목별로 분해합니다."""
    items = []

    # 1. 냉방 설정과 운전 패턴 개선
    if indoor_temp < 24 and outdoor_temp >= 24:
        cooling_low = monthly_bill * 0.02
        cooling_high = monthly_bill * 0.06
        cooling_reason = "실내온도가 낮은 편이어서 설정온도 조정이나 구역별 운전으로 냉방 전력을 줄일 수 있습니다."
    elif ratio_hour > 1.15 and outdoor_temp >= 26:
        cooling_low = monthly_bill * 0.015
        cooling_high = monthly_bill * 0.045
        cooling_reason = "운영시간 대비 전력사용량이 높고 외기온도가 높아 냉방 운전 패턴 점검 여지가 있습니다."
    else:
        cooling_low = monthly_bill * 0.005
        cooling_high = monthly_bill * 0.02
        cooling_reason = "현재 입력값 기준으로 냉방 절감 여지는 제한적이지만 설정온도와 운전시간 점검은 가능합니다."

    items.append({
        "항목": "냉방 설정과 운전 패턴",
        "월 최소 절감": cooling_low,
        "월 최대 절감": cooling_high,
        "근거": cooling_reason
    })

    # 2. 영업시간 외 스마트플러그 장비 사용 절감
    if smart_plug_entries and after_hours_kwh_total > 0:
        after_cost = after_hours_kwh_total * price_per_kwh
        smart_low = after_cost * 0.35
        smart_high = after_cost * 0.75
        smart_reason = "스마트플러그로 입력된 장비의 영업시간 외 사용량을 기준으로 조정 가능한 비용을 추정했습니다."
    else:
        smart_low = 0
        smart_high = 0
        smart_reason = "스마트플러그 데이터가 없어 영업시간 외 장비 사용 절감액은 별도로 계산하지 않았습니다."

    items.append({
        "항목": "영업시간 외 장비 사용",
        "월 최소 절감": smart_low,
        "월 최대 절감": smart_high,
        "근거": smart_reason
    })

    # 3. 냉장 장비 점검
    cold_count = equipment_counts.get("showcase", 0) + equipment_counts.get("refrigerator", 0) + equipment_counts.get("freezer", 0)
    if cold_count >= 3:
        cold_low = monthly_bill * 0.01
        cold_high = monthly_bill * 0.04
        cold_reason = "쇼케이스, 냉장고, 냉동고 등 상시 운전 장비가 많아 방열 공간, 문 패킹, 설정온도 점검 여지가 있습니다."
    elif cold_count > 0:
        cold_low = monthly_bill * 0.005
        cold_high = monthly_bill * 0.02
        cold_reason = "냉장 장비가 있어 기본적인 방열 공간과 설정온도 점검을 통한 절감 여지가 있습니다."
    else:
        cold_low = 0
        cold_high = 0
        cold_reason = "냉장 장비 입력이 없어 냉장 장비 절감액은 별도로 계산하지 않았습니다."

    items.append({
        "항목": "냉장 장비 점검",
        "월 최소 절감": cold_low,
        "월 최대 절감": cold_high,
        "근거": cold_reason
    })

    # 4. 계약전력 조정 가능성
    if contract_status == "계약전력 과다 가능성":
        contract_low = monthly_bill * 0.02
        contract_high = monthly_bill * 0.06
        contract_reason = "입력된 장비와 추정 피크부하 대비 계약전력이 높을 가능성이 있어 기본요금 점검 여지가 있습니다."
    else:
        contract_low = 0
        contract_high = 0
        contract_reason = "현재 입력값만으로는 계약전력 조정에 따른 절감액을 별도로 반영하지 않았습니다."

    items.append({
        "항목": "계약전력 점검",
        "월 최소 절감": contract_low,
        "월 최대 절감": contract_high,
        "근거": contract_reason
    })

    raw_low = sum(item["월 최소 절감"] for item in items)
    raw_high = sum(item["월 최대 절감"] for item in items)

    cap_low = monthly_bill * 0.03 if ratio_hour < 0.85 else monthly_bill * 0.08
    cap_high = monthly_bill * 0.10 if ratio_hour < 0.85 else monthly_bill * 0.25

    total_low = min(raw_low, cap_low)
    total_high = min(max(raw_high, total_low), cap_high)

    if monthly_bill < 300000 and total_high < 20000:
        explanation = "월 전기요금과 예상 절감 범위가 낮아, 현재는 Free 수준의 무료 진단이나 월별 재점검 용도로 활용하는 것이 적합합니다."
    elif total_high >= 50000 or monthly_bill >= 800000:
        explanation = "월 예상 절감 가능성이나 전기요금 규모를 고려하면 Pro 수준의 정기 관리 기능을 검토할 수 있습니다."
    else:
        explanation = "예상 절감액이 중간 수준이거나 상시 장비가 있는 매장은 Basic 수준의 월별 점검과 리포트 관리가 적합할 수 있습니다."

    return items, total_low, total_high, explanation


def calculate_management_fit(estimated_saving_low, estimated_saving_high, monthly_bill, ratio_hour, equipment_counts, smart_plug_count):
    """절감 가능성, 전기요금 규모, 장비 복잡도를 기준으로 적합한 관리 단계를 판단합니다."""
    complex_equipment_count = (
        equipment_counts.get("showcase", 0)
        + equipment_counts.get("ice_machine", 0)
        + equipment_counts.get("freezer", 0)
        + equipment_counts.get("oven", 0)
        + equipment_counts.get("proofer", 0)
        + equipment_counts.get("ac", 0)
    )

    bakery_like = equipment_counts.get("oven", 0) > 0 or equipment_counts.get("proofer", 0) > 0
    many_smart_plugs = smart_plug_count >= 3
    business_scale = monthly_bill >= 1200000 or many_smart_plugs and monthly_bill >= 900000

    if business_scale:
        return {
            "label": "다점포 관리 검토",
            "tier": "Business",
            "price_range": MANAGEMENT_TIERS["business"]["price"],
            "level": "danger",
            "message": "현재 매장은 전기요금 규모와 관리 복잡도가 큰 편입니다. 여러 매장의 전기요금 변화, 장비별 사용량, 이상 사용 여부를 지속적으로 관리하는 Business 수준의 운영 구조를 검토할 수 있습니다.",
            "payback": "Business 수준",
            "basis": "월 전기요금 규모, 스마트플러그 수, 장비 복잡도, 관리 범위를 함께 반영했습니다.",
            "value_message": "단순 절감보다 매장별 전력 사용 변동을 계속 추적하고, 이상 사용을 빠르게 발견하는 관리 가치가 큽니다."
        }

    if estimated_saving_high < 20000 and monthly_bill < 300000 and ratio_hour <= 1.15 and complex_equipment_count <= 3:
        return {
            "label": "무료 진단 권장",
            "tier": "Free",
            "price_range": MANAGEMENT_TIERS["free"]["price"],
            "level": "good",
            "message": "현재 매장은 전기요금 절감 가능성이 크지 않습니다. 유료 관리보다는 무료 진단으로 현재 상태를 확인하고, 다음 달 고지서와 비교하는 방식이 적합합니다.",
            "payback": "Free 수준",
            "basis": "월 예상 절감액이 낮고, 전기요금 규모와 장비 구성이 비교적 단순합니다.",
            "value_message": "절감액이 작은 매장은 월 구독보다 사용량이 갑자기 증가하는지 확인하는 가벼운 점검 용도가 더 적합합니다."
        }

    if estimated_saving_high >= 50000 or monthly_bill >= 800000 or ratio_hour > 1.35 or complex_equipment_count >= 6 or bakery_like:
        return {
            "label": "유료 관리 검토",
            "tier": "Pro",
            "price_range": MANAGEMENT_TIERS["pro"]["price"],
            "level": "danger",
            "message": "현재 매장은 월 예상 절감 가능성이 높거나 장비 구성이 복잡하여 정기적인 에너지 관리가 적합합니다. 스마트플러그 기반 장비별 사용량 분석과 월별 리포트를 함께 활용하면 낭비 요인을 더 구체적으로 확인할 수 있습니다.",
            "payback": "Pro 수준",
            "basis": "월 예상 절감액, 전기요금 규모, 베이커리형 장비 또는 부하 큰 장비 구성을 반영했습니다.",
            "value_message": "가치는 한 번의 절감보다 전기 사용량이 다시 증가하지 않도록 장비별 이상 사용과 폐점 후 사용을 지속적으로 잡아내는 데 있습니다."
        }

    return {
        "label": "정기 점검 권장",
        "tier": "Basic",
        "price_range": MANAGEMENT_TIERS["basic"]["price"],
        "level": "warning",
        "message": "현재 매장은 큰 절감보다 월별 전기요금 변동과 장비 사용 패턴을 정기적으로 확인하는 것이 적합합니다. 일부 장비에 스마트플러그를 연결하면 더 정확한 진단이 가능합니다.",
        "payback": "Basic 수준",
        "basis": "월 예상 절감액이 중간 수준이거나 냉장 장비, 제빙기, 에어컨처럼 장시간 작동하는 장비가 포함되어 있습니다.",
        "value_message": "사용자가 매일 직접 조작하기보다, 월별 전기요금 변화와 장시간 작동 장비를 꾸준히 확인해 다시 요금이 올라가지 않도록 관리하는 방향이 적합합니다."
    }

def generate_next_actions(recommendations, management_fit, smart_plug_count):
    actions = []

    for rec in recommendations:
        title = rec.get("title", "")
        if "영업시간 외" in title:
            actions.append("스마트플러그 장비의 폐점 후 운전 여부를 확인하고, 불필요한 장비는 자동 종료 시간을 설정하세요.")
        elif "냉장" in title:
            actions.append("냉장고와 쇼케이스의 문 패킹, 방열 공간, 설정온도를 먼저 점검하세요.")
        elif "냉방" in title or "에어컨" in title:
            actions.append("에어컨을 동시에 강하게 켜기보다 구역별 순차 운전과 설정온도 조정을 검토하세요.")
        elif "계약전력" in title:
            actions.append("최근 최대 사용량 또는 피크 시간대를 확인한 뒤 계약전력 조정 필요성을 검토하세요.")
        elif "베이커리" in title:
            actions.append("오븐 예열 시간과 냉방 피크 시간이 겹치지 않도록 운영 스케줄을 조정하세요.")

    if smart_plug_count == 0:
        actions.append("쇼케이스, 제빙기, 소형 냉장고 중 하나에 스마트플러그를 연결해 실제 장비 사용량을 확인하세요.")

    if management_fit["label"] == "무료 진단 권장":
        actions.append("다음 달 고지서가 나오면 전력사용량과 요금을 다시 입력해 증가 여부를 확인하세요.")
    else:
        actions.append("월별 리포트를 저장해 전기요금과 사용량이 증가하는 시점을 추적하세요.")

    # 중복 제거 후 3개만 반환
    unique_actions = []
    for action in actions:
        if action not in unique_actions:
            unique_actions.append(action)

    return unique_actions[:3]

def get_priority_label(impact):
    if impact == "high":
        return "우선 조치"
    if impact == "medium":
        return "검토 필요"
    return "관찰"


def get_priority_color(impact):
    if impact == "high":
        return "danger"
    if impact == "medium":
        return "warning"
    return "good"


# =========================================================
# Report
# =========================================================

def build_report_text(
    area_pyeong,
    area_m2,
    monthly_kwh,
    monthly_bill,
    contract_power,
    energy_score,
    reliability_score,
    reliability_label,
    kwh_per_hour,
    selected_location_label,
    outdoor_temp,
    outdoor_humidity,
    wind_speed,
    monthly_hours,
    equipment_counts,
    recommendations,
    summary,
    smart_plug_entries=None,
    estimated_saving_low=0,
    estimated_saving_high=0,
    management_fit=None,
    next_actions=None,
    savings_breakdown=None
):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    equipment_lines = []
    for key, count in equipment_counts.items():
        if count > 0:
            equipment_lines.append(f"- {EQUIPMENT_CATALOG[key]['label']}: {count}대")
    equipment_text = "\n".join(equipment_lines) if equipment_lines else "- 선택된 장비 없음"

    smart_plug_lines = []
    if smart_plug_entries:
        for item in smart_plug_entries:
            smart_plug_lines.append(
                f"- {item['device']}: 월 {item['monthly_kwh']:.1f} kWh, 영업시간 외 사용 비중 {item['after_hours_ratio']:.0f}%"
            )
    smart_plug_text = "\n".join(smart_plug_lines) if smart_plug_lines else "- 입력된 스마트플러그 데이터 없음"

    rec_lines = []
    for idx, rec in enumerate(recommendations, start=1):
        rec_lines.append(f"{idx}. {rec['title']}\n   {rec['body']}")
    rec_text = "\n\n".join(rec_lines)

    return f"""
CafeWatt 진단 리포트
생성 시각: {now}

1. 매장 정보
업종: 카페
매장 면적: {area_pyeong:.1f}평 / {area_m2:.1f}㎡
월 운영시간: {monthly_hours:.1f}시간
기준 위치: {selected_location_label}

2. 전기요금 정보
월 전력사용량: {monthly_kwh:,.0f} kWh
월 전기요금: {monthly_bill:,.0f}원
계약전력: {contract_power:.1f} kW

3. 핵심 진단
종합 에너지 점수: {energy_score} / 100
진단 신뢰도: {reliability_label} ({reliability_score} / 100)
운영시간당 전력사용량: {kwh_per_hour:.1f} kWh/hour

4. 날씨와 실내환경
현재 외기온도: {outdoor_temp:.1f}°C
현재 외기습도: {outdoor_humidity:.0f}%
풍속: {wind_speed:.1f} m/s

5. 장비 구성
{equipment_text}

6. 스마트플러그 데이터
{smart_plug_text}

7. 월 예상 절감 금액과 관리 적합도
월 예상 절감 금액: {won(estimated_saving_low)} ~ {won(estimated_saving_high)}
관리 적합도: {(management_fit or {}).get("label", "확인 필요")}
권장 관리 단계: {(management_fit or {}).get("tier", "확인 필요")} 수준
예상 가격 범위: {(management_fit or {}).get("price_range", "확인 필요")}
판단 근거: {(management_fit or {}).get("basis", "확인 필요")}
관리 가치: {(management_fit or {}).get("value_message", "전기 사용량이 다시 증가하지 않도록 지속적으로 확인하는 것이 중요합니다.")}

8. 다음 행동
{chr(10).join([f"{idx + 1}. {action}" for idx, action in enumerate(next_actions or [])])}

9. 추천 조치
{rec_text}

10. 종합 요약
{summary}

안내
CafeWatt는 카페의 에너지 사용 현황을 빠르게 파악하기 위한 기초 에너지 진단 도구입니다. 결과는 사용자가 입력한 전기요금, 운영시간, 장비 구성, 실내환경 정보와 위치 기반 날씨 데이터를 함께 반영해 계산됩니다.
"""

def build_pdf_report(report_text):
    if not REPORTLAB_AVAILABLE:
        return None

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 17 * mm
    y = height - 18 * mm
    max_width = width - 2 * margin_x

    brand = colors.HexColor("#7A4A24")
    soft = colors.HexColor("#FFF3DF")
    line = colors.HexColor("#E6D6C0")
    text_color = colors.HexColor("#2B2118")
    muted = colors.HexColor("#6B5E52")

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
        font_regular = "HYGothic-Medium"
        font_bold = "HYGothic-Medium"
    except Exception:
        font_regular = "Helvetica"
        font_bold = "Helvetica-Bold"

    def draw_header():
        nonlocal y
        c.setFillColor(brand)
        c.roundRect(margin_x, y - 20 * mm, max_width, 20 * mm, 4 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(font_bold, 17)
        c.drawString(margin_x + 7 * mm, y - 8 * mm, "CafeWatt 진단 리포트")
        c.setFont(font_regular, 9)
        c.drawString(margin_x + 7 * mm, y - 14 * mm, "카페 전기요금, 장비 부하, 날씨, 스마트플러그 사용량 진단")
        y -= 28 * mm

    def new_page_if_needed(required=12 * mm):
        nonlocal y
        if y < required + 18 * mm:
            c.showPage()
            y = height - 18 * mm
            draw_header()

    def draw_section(title):
        nonlocal y
        new_page_if_needed(16 * mm)
        c.setFillColor(soft)
        c.roundRect(margin_x, y - 9 * mm, max_width, 9 * mm, 2 * mm, stroke=0, fill=1)
        c.setFillColor(brand)
        c.setFont(font_bold, 11)
        c.drawString(margin_x + 4 * mm, y - 6 * mm, title)
        y -= 13 * mm

    def draw_text(paragraph, size=9, leading=5 * mm, indent=0, color=text_color):
        nonlocal y
        c.setFillColor(color)
        c.setFont(font_regular, size)
        lines = simpleSplit(paragraph, font_regular, size, max_width - indent)
        for line in lines:
            new_page_if_needed(leading)
            c.drawString(margin_x + indent, y, line)
            y -= leading

    c.setTitle("CafeWatt 진단 리포트")
    draw_header()

    for paragraph in report_text.split("\n"):
        text_line = paragraph.strip()
        if not text_line:
            y -= 3 * mm
            continue

        if text_line[0:2].isdigit() and "." in text_line[:4]:
            draw_section(text_line)
            continue

        if text_line.startswith("생성 시각"):
            draw_text(text_line, size=8, leading=5 * mm, color=muted)
            y -= 2 * mm
            continue

        if text_line.startswith("안내"):
            draw_section("안내")
            continue

        if text_line.startswith("-"):
            draw_text(text_line, size=9, indent=4 * mm)
        elif text_line.startswith("CafeWatt 진단 리포트"):
            continue
        else:
            draw_text(text_line, size=9)

    c.setStrokeColor(line)
    c.line(margin_x, 15 * mm, width - margin_x, 15 * mm)
    c.setFillColor(muted)
    c.setFont(font_regular, 8)
    c.drawString(margin_x, 10 * mm, "CafeWatt | 카페 전기요금 진단 도구")

    c.save()
    buffer.seek(0)
    return buffer.getvalue()


# =========================================================
# Header
# =========================================================

st.markdown('<div class="main-title">☕ CafeWatt</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">카페의 전기요금, 운영시간, 장비 구성, 실내환경, 위치 기반 날씨를 연결해 에너지 사용 수준을 진단합니다.</div>',
    unsafe_allow_html=True
)

st.markdown("""
<div class="hero-box">
    <span class="info-chip">전기요금 진단</span>
    <span class="info-chip">주소 기반 날씨</span>
    <span class="info-chip">카페 장비 분석</span>
    <span class="info-chip">계약전력 점검</span>
    <span class="info-chip">진단 신뢰도</span>
    <span class="info-chip">PDF 리포트</span>
</div>
""", unsafe_allow_html=True)


# =========================================================
# Sidebar Inputs
# =========================================================

st.sidebar.markdown("### 샘플 데이터로 빠르게 테스트하거나, 현재 입력값을 파일로 저장하고 다시 불러올 수 있습니다.")

sample_name = st.sidebar.selectbox(
    "샘플 카페 데이터",
    list(SAMPLE_PROFILES.keys()),
    index=1,
    key="sample_profile_select"
)

if st.sidebar.button("샘플 데이터 적용", use_container_width=True):
    apply_input_profile(SAMPLE_PROFILES[sample_name])
    st.sidebar.success(f"{sample_name} 샘플을 적용했습니다.")
    st.rerun()

st.sidebar.divider()

st.sidebar.header("매장 기본 정보")
st.sidebar.caption("처음 화면은 일반적인 중형 카페 평균값으로 시작합니다. 실제 매장 조건에 맞게 수정하세요.")
store_type = "카페"

area_unit, area_value_col = st.sidebar.columns([0.85, 1.15])
with area_unit:
    area_input_unit = st.selectbox("면적 단위", ["평", "㎡"], key="area_input_unit")
with area_value_col:
    area_value = st.number_input("매장 면적", min_value=5.0, max_value=500.0, step=1.0, key="area_value")

if area_input_unit == "평":
    area_pyeong = area_value
    area_m2 = area_value * 3.3058
else:
    area_m2 = area_value
    area_pyeong = area_value / 3.3058

st.sidebar.caption(f"변환 면적: {area_pyeong:.1f}평 / {area_m2:.1f}㎡")

schedule_mode = st.sidebar.radio("운영시간 입력 방식", ["간단 입력", "요일별 입력"], horizontal=True, key="schedule_mode")

if schedule_mode == "간단 입력":
    open_time = st.sidebar.time_input("오픈 시간", key="open_time_main")
    close_time = st.sidebar.time_input("마감 시간", key="close_time_main")
    business_days = st.sidebar.slider("월 영업일수", 1, 31, key="business_days")

    open_hours = close_time.hour + close_time.minute / 60 - (open_time.hour + open_time.minute / 60)
    if open_hours <= 0:
        open_hours += 24
    monthly_hours = open_hours * business_days
    weekly_hours = monthly_hours / 4.345 if monthly_hours > 0 else 0
else:
    weekly_hours = 0
    business_days_per_week = 0
    with st.sidebar.expander("요일별 운영시간 설정", expanded=True):
        for day_key, day_label in DAYS:
            is_open = st.checkbox(f"{day_label}요일 영업", value=(day_key not in ["sun"]), key=f"open_{day_key}")
            if is_open:
                c1, c2 = st.columns(2)
                with c1:
                    day_open = st.time_input(f"{day_label} 오픈", value=time(9, 0), key=f"open_time_{day_key}")
                with c2:
                    day_close = st.time_input(f"{day_label} 마감", value=time(22, 0), key=f"close_time_{day_key}")

                day_hours = day_close.hour + day_close.minute / 60 - (day_open.hour + day_open.minute / 60)
                if day_hours <= 0:
                    day_hours += 24
                weekly_hours += day_hours
                business_days_per_week += 1

    monthly_hours = weekly_hours * 4.345
    business_days = int(round(business_days_per_week * 4.345))
    open_hours = weekly_hours / business_days_per_week if business_days_per_week > 0 else 0

st.sidebar.caption(f"예상 월 운영시간: {monthly_hours:.0f}시간")

st.sidebar.divider()

st.sidebar.header("전기요금 정보")

if "monthly_kwh_text" not in st.session_state:
    st.session_state["monthly_kwh_text"] = format_number_text(st.session_state.get("monthly_kwh", 1800))
if "monthly_bill_text" not in st.session_state:
    st.session_state["monthly_bill_text"] = format_number_text(st.session_state.get("monthly_bill", 420000))

monthly_kwh_text = st.sidebar.text_input(
    "월 전력사용량 (kWh)",
    key="monthly_kwh_text",
    help="전기요금 고지서의 월 사용량을 입력하세요. 예: 1,800"
)
monthly_kwh = parse_number_text(monthly_kwh_text, fallback=1800)
st.sidebar.caption(f"입력값: {monthly_kwh:,} kWh")

monthly_bill_text = st.sidebar.text_input(
    "월 전기요금 (원)",
    key="monthly_bill_text",
    help="최근 월 전기요금을 원 단위로 입력하세요. 예: 420,000"
)
monthly_bill = parse_number_text(monthly_bill_text, fallback=420000)
st.sidebar.caption(f"입력값: {monthly_bill:,}원")

contract_power = st.sidebar.number_input("계약전력 (kW)", min_value=1.0, max_value=100.0, step=1.0, key="contract_power", help="일반 중형 카페는 10~20kW 수준에서 시작하는 경우가 많아 기본값을 15kW로 설정했습니다.")

st.sidebar.divider()

st.sidebar.header("카페 장비 정보")
st.sidebar.caption("장비를 체크하면 개수를 선택할 수 있습니다.")

equipment_counts = {}
for key, item in EQUIPMENT_CATALOG.items():
    default_checked = item["essential"]
    checked, count = equipment_input(key, item["label"], item["default"], default_checked=default_checked, max_count=10)
    equipment_counts[key] = count if checked else 0

st.sidebar.divider()

st.sidebar.header("실내환경")
if "indoor_temp" not in st.session_state:
    st.session_state["indoor_temp"] = 25.5
if "indoor_humidity" not in st.session_state:
    st.session_state["indoor_humidity"] = 55

indoor_temp = st.sidebar.slider(
    "영업시간 평균 실내온도 (°C)",
    min_value=10.0,
    max_value=38.0,
    step=0.5,
    key="indoor_temp",
    help="센서가 없으면 평소 영업시간 평균값을 입력하세요."
)
indoor_humidity = st.sidebar.slider(
    "평균 실내습도 (%)",
    min_value=0,
    max_value=100,
    key="indoor_humidity",
    help="센서가 없으면 평소 실내 평균 습도를 입력하세요."
)

st.sidebar.divider()

st.sidebar.header("스마트플러그 장비")
st.sidebar.caption("스마트플러그가 여러 개라면 장비별로 추가해 입력할 수 있습니다.")

smart_plug_count = st.sidebar.number_input(
    "스마트플러그 연결 장비 수",
    min_value=0,
    max_value=8,
    step=1,
    key="smart_plug_count"
)

smart_plug_entries = []
plug_kwh_month = 0.0
after_hours_kwh_total = 0.0

plug_device_options = [
    "쇼케이스 냉장고",
    "제빙기",
    "소형 냉장고",
    "냉동고",
    "공기청정기",
    "복합기",
    "오븐",
    "발효기",
    "기타 장비"
]

if smart_plug_count > 0:
    with st.sidebar.expander("스마트플러그 장비별 입력", expanded=True):
        for i in range(int(smart_plug_count)):
            st.markdown(f"**장비 {i + 1}**")
            plug_device_name = st.selectbox(
                f"연결 장비 {i + 1}",
                plug_device_options,
                key=f"plug_device_{i}"
            )
            plug_kwh_day_i = st.number_input(
                f"하루 사용량 {i + 1}",
                min_value=0.0,
                max_value=100.0,
                value=4.5,
                step=0.5,
                key=f"plug_kwh_day_{i}",
                help="스마트플러그 앱에서 확인한 하루 전력사용량입니다."
            )
            after_hours_ratio_i = st.slider(
                f"영업시간 외 사용 비중 {i + 1}",
                0,
                100,
                25,
                key=f"after_hours_ratio_{i}"
            )

            monthly_kwh_i = plug_kwh_day_i * business_days
            after_hours_kwh_i = monthly_kwh_i * after_hours_ratio_i / 100

            smart_plug_entries.append({
                "device": plug_device_name,
                "daily_kwh": plug_kwh_day_i,
                "monthly_kwh": monthly_kwh_i,
                "after_hours_ratio": after_hours_ratio_i,
                "after_hours_kwh": after_hours_kwh_i
            })

            plug_kwh_month += monthly_kwh_i
            after_hours_kwh_total += after_hours_kwh_i

after_hours_ratio = (after_hours_kwh_total / plug_kwh_month * 100) if plug_kwh_month > 0 else 0
plug_device = "여러 장비" if smart_plug_count > 1 else (smart_plug_entries[0]["device"] if smart_plug_count == 1 else "없음")


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
        <b>{st.session_state["selected_location_label"]}</b>
        <div class="metric-caption">주소 기반으로 날씨 데이터와 지도를 연결합니다.</div>
    </div>
    """, unsafe_allow_html=True)

latitude = st.session_state["latitude"]
longitude = st.session_state["longitude"]
selected_location_label = st.session_state["selected_location_label"]
weather_data = get_weather_open_meteo(latitude, longitude)

outdoor_temp = 28.0
outdoor_humidity = 60
wind_speed = 0.0
has_weather = False

if weather_data["success"] and weather_data["temperature"] is not None:
    outdoor_temp = float(weather_data["temperature"])
    outdoor_humidity = float(weather_data["humidity"]) if weather_data["humidity"] is not None else 55
    wind_speed = float(weather_data["wind_speed"]) if weather_data["wind_speed"] is not None else 0.0
    has_weather = True

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

kwh_per_m2 = safe_divide(monthly_kwh, area_m2)
kwh_per_hour = safe_divide(monthly_kwh, monthly_hours)
price_per_kwh = safe_divide(monthly_bill, monthly_kwh)

benchmark_hour = adjusted_benchmark_hour(equipment_counts)
ratio_hour = safe_divide(kwh_per_hour, benchmark_hour)
ratio_area_reference = safe_divide(kwh_per_m2, BASE_BENCHMARK["monthly_kwh_per_m2_reference"])

hour_grade, hour_class = grade_from_ratio(ratio_hour)
energy_score = score_from_ratio(ratio_hour)

estimated_peak_kw, base_peak, device_extra = estimate_equipment_peak_kw(area_pyeong, equipment_counts)
contract_status, contract_message, contract_class = contract_power_diagnosis(contract_power, estimated_peak_kw)
cooling_status, cooling_message, cooling_class = cooling_load_diagnosis(outdoor_temp, indoor_temp, indoor_humidity)

reliability_score, reliability_label, reliability_class, reliability_reasons = calculate_reliability(
    monthly_kwh,
    monthly_bill,
    contract_power,
    equipment_counts,
    schedule_mode,
    has_weather,
    plug_device
)

recommendations = calculate_recommendations(
    monthly_kwh,
    monthly_bill,
    monthly_hours,
    indoor_temp,
    indoor_humidity,
    outdoor_temp,
    plug_kwh_month,
    after_hours_ratio,
    contract_status,
    equipment_counts,
    ratio_hour,
    price_per_kwh
)

savings_breakdown, estimated_saving_low, estimated_saving_high, savings_explanation = calculate_savings_breakdown(
    monthly_bill,
    price_per_kwh,
    indoor_temp,
    outdoor_temp,
    ratio_hour,
    contract_status,
    equipment_counts,
    smart_plug_entries,
    after_hours_kwh_total
)

management_fit = calculate_management_fit(
    estimated_saving_low,
    estimated_saving_high,
    monthly_bill,
    ratio_hour,
    equipment_counts,
    smart_plug_count
)

next_actions = generate_next_actions(recommendations, management_fit, smart_plug_count)

bakery_like = equipment_counts.get("oven", 0) > 0 or equipment_counts.get("proofer", 0) > 0
if ratio_hour > 1.15:
    summary = "현재 카페는 월 운영시간과 장비 구성 기준으로 전력 사용량이 높은 편입니다. 냉방 설정, 냉장 장비, 영업시간 외 사용량을 우선 점검하는 것이 좋습니다."
elif ratio_hour < 0.85:
    summary = "현재 카페는 월 운영시간과 장비 구성 기준으로 전력 사용량이 낮은 편입니다. 다만 실내 쾌적성이 떨어지지 않는지 함께 확인하는 것이 좋습니다."
else:
    summary = "현재 카페는 월 운영시간과 장비 구성 기준으로 평균에 가까운 전력 사용 수준입니다. 스마트플러그 장비와 계약전력을 점검하면 추가 절감 가능성을 찾을 수 있습니다."

if bakery_like:
    summary += " 오븐 또는 발효기 사용이 반영되어 베이커리형 부하 특성이 일부 포함되었습니다."


# =========================================================
# Main Dashboard
# =========================================================

st.markdown('<div class="section-title">CafeWatt 핵심 진단 결과</div>', unsafe_allow_html=True)
score_col, reliability_col, kwh_col, bill_col = st.columns(4)

with score_col:
    metric_card("종합 에너지 점수", f"{energy_score}점", "100점에 가까울수록 효율적")
with reliability_col:
    metric_card("진단 신뢰도", f"{reliability_label}", f"{reliability_score}점 / 100점")
with kwh_col:
    metric_card("월 전력사용량", kwh(monthly_kwh), f"운영시간당 {kwh_per_hour:.1f} kWh")
with bill_col:
    metric_card("월 전기요금", won(monthly_bill), f"평균 단가 {price_per_kwh:.0f}원/kWh")

saving_col, fit_col = st.columns([1, 1])
with saving_col:
    metric_card(
        "월 예상 절감 금액",
        f"{won(estimated_saving_low)} ~ {won(estimated_saving_high)}",
        "항목별 절감 가능성을 합산한 월 예상 범위입니다.",
        small=True
    )
with fit_col:
    fit_badge = class_to_badge(management_fit["level"])
    st.markdown(f"""
    <div class="card-white">
        <div class="metric-title">관리 적합도</div>
        <div class="metric-value-small">{management_fit["label"]}</div>
        <p><span class="{fit_badge}">{management_fit["payback"]}</span></p>
        <p class="small-text">권장 관리 단계는 아래 핵심 해석에서 확인할 수 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="card-soft">
    <div class="metric-title">핵심 해석</div>
    <p>{summary}</p>
    <p><b>권장 관리 단계: {management_fit["tier"]} 수준</b> · {management_fit["price_range"]}</p>
    <p>{management_fit["message"]}</p>
    <p>{management_fit.get("value_message", "CafeWatt의 핵심 가치는 한 번의 절감보다 전기 사용량이 다시 증가하지 않도록 지속적으로 관리하는 데 있습니다.")}</p>
    <p class="small-text" style="margin-bottom: 0;">CafeWatt는 모든 카페에 유료 관리를 권장하지 않고, 현재 매장의 전기요금, 예상 절감 가능성, 장비 구성, 운영 규모를 기준으로 Free, Basic, Pro, Business 중 적합한 관리 단계를 제안합니다. 위 가격은 향후 서비스 구성을 위한 예시이며, 실제 가격은 기능 범위와 데이터 연동 방식에 따라 달라질 수 있습니다.</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-title">다음 행동</div>', unsafe_allow_html=True)
action_cols = st.columns(3)
for idx, action in enumerate(next_actions):
    with action_cols[idx]:
        st.markdown(f"""
        <div class="card-white">
            <div class="metric-title">Action {idx + 1}</div>
            <p style="margin-bottom: 0;">{action}</p>
        </div>
        """, unsafe_allow_html=True)

st.divider()


# =========================================================
# Tabs
# =========================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["진단 요약", "장비와 계약전력", "날씨와 실내환경", "스마트플러그", "추천 조치", "리포트"])


# =========================================================
# Tab 1
# =========================================================

with tab1:
    left, right = st.columns([1.1, 1])

    with left:
        st.markdown('<div class="section-title">진단 요약</div>', unsafe_allow_html=True)

        hour_badge = class_to_badge(hour_class)
        reliability_badge = class_to_badge(reliability_class)

        st.markdown(f"""
        <div class="card">
            <div class="metric-title">운영시간 기준 전력사용량</div>
            <div class="metric-value">{kwh_per_hour:.1f} kWh/hour</div>
            <p>장비 구성 반영 기준 <span class="{hour_badge}">{hour_grade}</span></p>
            <p class="small-text">장비 보정 기준 대비 {pct((ratio_hour - 1) * 100)} 수준입니다.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="card-white">
            <div class="metric-title">진단 신뢰도</div>
            <div class="metric-value-small">{reliability_label} · {reliability_score}점</div>
            <p><span class="{reliability_badge}">{reliability_label}</span></p>
            <p class="small-text">실제 시간별 전력 데이터가 없기 때문에 현재 결과는 1차 진단용입니다.</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("진단 신뢰도 산정 이유"):
            for reason in reliability_reasons:
                st.write(f"• {reason}")

        st.markdown('<div class="section-title">월 예상 절감 금액 산정 근거</div>', unsafe_allow_html=True)
        savings_df = pd.DataFrame([
            {
                "절감 항목": item["항목"],
                "월 최소 절감": won(item["월 최소 절감"]),
                "월 최대 절감": won(item["월 최대 절감"]),
                "근거": item["근거"]
            }
            for item in savings_breakdown
        ])
        st.dataframe(savings_df, use_container_width=True, hide_index=True)
        st.info(savings_explanation)

        with st.expander("관리 단계 기준 보기"):
            st.write("CafeWatt는 모든 카페에 유료 관리를 권장하지 않습니다. 매장 규모, 절감 가능성, 장비 구성, 스마트플러그 사용 여부를 기준으로 적합한 관리 단계를 제안합니다.")
            tier_df = pd.DataFrame([
                {"관리 단계": "Free", "예상 가격": MANAGEMENT_TIERS["free"]["price"], "적합한 대상": MANAGEMENT_TIERS["free"]["target"]},
                {"관리 단계": "Basic", "예상 가격": MANAGEMENT_TIERS["basic"]["price"], "적합한 대상": MANAGEMENT_TIERS["basic"]["target"]},
                {"관리 단계": "Pro", "예상 가격": MANAGEMENT_TIERS["pro"]["price"], "적합한 대상": MANAGEMENT_TIERS["pro"]["target"]},
                {"관리 단계": "Business", "예상 가격": MANAGEMENT_TIERS["business"]["price"], "적합한 대상": MANAGEMENT_TIERS["business"]["target"]},
            ])
            st.dataframe(tier_df, use_container_width=True, hide_index=True)
            st.caption("위 가격은 향후 서비스 구성을 위한 예시이며, 실제 가격은 기능 범위와 데이터 연동 방식에 따라 달라질 수 있습니다.")

    with right:
        st.markdown('<div class="section-title">운영 정보</div>', unsafe_allow_html=True)

        op1, op2 = st.columns(2)
        with op1:
            metric_card("매장 면적", f"{area_pyeong:.1f}평", f"{area_m2:.1f}㎡")
        with op2:
            metric_card("월 운영시간", f"{monthly_hours:.0f}시간", f"월 영업일수 약 {business_days}일")

        op3, op4 = st.columns(2)
        with op3:
            metric_card("운영 방식", schedule_mode, f"주 {weekly_hours:.1f}시간")
        with op4:
            metric_card("전기 단가", f"{price_per_kwh:.0f}원/kWh", "요금 ÷ 사용량 기준")

        st.info("기존의 업종 선택과 면적 기준 비교 그래프는 제거했습니다. 현재 점수는 운영시간과 장비 구성 기준을 중심으로 계산됩니다.")


# =========================================================
# Tab 2
# =========================================================

with tab2:
    st.markdown('<div class="section-title">장비 구성과 피크부하 추정</div>', unsafe_allow_html=True)

    selected_equipment = []
    for key, count in equipment_counts.items():
        if count > 0:
            selected_equipment.append({
                "장비": EQUIPMENT_CATALOG[key]["label"],
                "개수": count,
                "개당 추정 kW": EQUIPMENT_CATALOG[key]["kw"],
                "총 추정 kW": EQUIPMENT_CATALOG[key]["kw"] * count
            })

    if selected_equipment:
        st.dataframe(pd.DataFrame(selected_equipment), use_container_width=True, hide_index=True)
    else:
        st.info("선택된 장비가 없습니다.")

    left, right = st.columns([1, 1])
    with left:
        st.markdown(f"""
        <div class="card">
            <div class="metric-title">추정 피크부하</div>
            <div class="metric-value">{estimated_peak_kw:.1f} kW</div>
            <p class="small-text">입력된 장비 구성, 면적, 단순 동시사용률을 바탕으로 추정한 값입니다.</p>
        </div>
        """, unsafe_allow_html=True)

        peak_df = pd.DataFrame({
            "구분": ["기본부하", "장비 추가부하"],
            "추정 kW": [base_peak, device_extra]
        })
        st.bar_chart(peak_df, x="구분", y="추정 kW", use_container_width=True)

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

        if bakery_like:
            st.warning("오븐 또는 발효기가 선택되어 베이커리형 장비 부하가 반영되었습니다.")


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

    st.markdown(f"""
    <div class="card">
        <div class="metric-title">냉방 부담 진단</div>
        <div class="metric-value-small">{cooling_status}</div>
        <p>{cooling_message}</p>
    </div>
    """, unsafe_allow_html=True)

    env_df = pd.DataFrame({"항목": ["외기온도", "실내온도", "외기습도", "실내습도", "풍속"], "값": [outdoor_temp, indoor_temp, outdoor_humidity, indoor_humidity, wind_speed]})
    st.dataframe(env_df, use_container_width=True, hide_index=True)
    st.caption(f"날씨 기준 위치: {selected_location_label}")


# =========================================================
# Tab 4
# =========================================================

with tab4:
    st.markdown('<div class="section-title">스마트플러그 장비 분석</div>', unsafe_allow_html=True)

    if smart_plug_count == 0:
        st.info("스마트플러그 장비가 아직 입력되지 않았습니다. 쇼케이스, 제빙기, 냉장고처럼 상시 가동되는 장비부터 연결하면 진단 신뢰도를 높일 수 있습니다.")
    else:
        smart_plug_df = pd.DataFrame([
            {
                "장비": item["device"],
                "하루 사용량 kWh": item["daily_kwh"],
                "월 예상 사용량 kWh": item["monthly_kwh"],
                "영업시간 외 비중 %": item["after_hours_ratio"],
                "영업시간 외 사용량 kWh": item["after_hours_kwh"],
                "월 예상 비용": won(item["monthly_kwh"] * price_per_kwh),
                "영업시간 외 예상 비용": won(item["after_hours_kwh"] * price_per_kwh)
            }
            for item in smart_plug_entries
        ])
        st.dataframe(smart_plug_df, use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("스마트플러그 월 사용량", kwh(plug_kwh_month))
        with c2:
            metric_card("영업시간 외 사용량", kwh(after_hours_kwh_total))
        with c3:
            metric_card("영업시간 외 비중", f"{after_hours_ratio:.0f}%")

        if after_hours_ratio >= 25:
            st.warning("스마트플러그로 입력된 장비들의 영업시간 외 사용 비중이 높은 편입니다. 폐점 후 운전이 필요한 장비와 불필요한 장비를 구분해 점검하는 것이 좋습니다.")
        else:
            st.success("현재 입력된 스마트플러그 장비에서는 영업시간 외 낭비 신호가 강하게 보이지 않습니다.")

    st.caption("현재는 스마트플러그 앱에서 확인한 값을 직접 입력하는 방식입니다. 추후 CSV 업로드나 실시간 API 연동으로 확장할 수 있습니다.")


# =========================================================
# Tab 5
# =========================================================

with tab5:
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
# Tab 6
# =========================================================

with tab6:
    st.markdown('<div class="section-title">진단 리포트 다운로드</div>', unsafe_allow_html=True)

    report_text = build_report_text(
        area_pyeong,
        area_m2,
        monthly_kwh,
        monthly_bill,
        contract_power,
        energy_score,
        reliability_score,
        reliability_label,
        kwh_per_hour,
        selected_location_label,
        outdoor_temp,
        outdoor_humidity,
        wind_speed,
        monthly_hours,
        equipment_counts,
        recommendations,
        summary,
        smart_plug_entries,
        estimated_saving_low,
        estimated_saving_high,
        management_fit,
        next_actions,
        savings_breakdown
    )

    st.text_area("리포트 미리보기", report_text, height=420)

    now_name = datetime.now().strftime("%Y%m%d_%H%M")
    txt_file_name = f"CafeWatt_Report_{now_name}.txt"
    pdf_file_name = f"CafeWatt_Report_{now_name}.pdf"

    download_col1, download_col2 = st.columns(2)

    with download_col1:
        st.download_button(
            label="TXT 리포트 다운로드",
            data=report_text,
            file_name=txt_file_name,
            mime="text/plain",
            use_container_width=True
        )

    with download_col2:
        if REPORTLAB_AVAILABLE:
            pdf_bytes = build_pdf_report(report_text)
            st.download_button(
                label="PDF 리포트 다운로드",
                data=pdf_bytes,
                file_name=pdf_file_name,
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.warning("PDF 다운로드를 사용하려면 requirements.txt에 reportlab을 추가하세요.")

    st.caption("PDF 리포트는 한글 형식의 진단 보고서로 생성됩니다.")


# =========================================================
# Footer
# =========================================================

st.divider()

with st.expander("CafeWatt 진단 기준 안내"):
    st.write("""
    CafeWatt는 카페의 에너지 사용 현황을 빠르게 파악하기 위한 기초 에너지 진단 도구입니다.

    현재 결과는 사용자가 입력한 전기요금, 운영시간, 장비 구성, 실내환경 정보와 위치 기반 날씨 데이터를 함께 반영해 계산됩니다.
    일반 카페와 베이커리 카페를 별도로 구분하지 않고, 오븐, 발효기, 냉동고, 쇼케이스 등 선택한 장비 구성을 통해 베이커리형 부하 특성을 반영합니다.

    계약전력 진단은 사전 참고용입니다.
    실제 계약전력 변경은 한전, 전기공사업체, 전기기사와 확인해야 합니다.

    스마트플러그 분석은 사용자가 입력한 장비별 사용량을 기준으로 영업시간 외 사용 가능성과 예상 비용을 계산합니다.
    매장 전체 전력사용량은 월 전력사용량 입력값을 기준으로 판단합니다.

    주소 검색은 Kakao Local API를 사용하고, 날씨 데이터는 Open Meteo API를 사용합니다.
    """)

st.caption("CafeWatt | 카페 전기요금 진단 도구")
