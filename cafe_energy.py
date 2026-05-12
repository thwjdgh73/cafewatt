import streamlit as st
import pandas as pd
import requests
from datetime import time

st.set_page_config(
    page_title="CafeWatt",
    page_icon="☕",
    layout="wide"
)

# -----------------------------
# 기본 스타일
# -----------------------------

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
    margin-bottom: 24px;
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
</style>
""", unsafe_allow_html=True)


# -----------------------------
# 기준 데이터
# 실제 서비스에서는 공공데이터와 실제 사용자 데이터로 교체
# -----------------------------

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


# -----------------------------
# 함수
# -----------------------------

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


def get_weather_open_meteo(latitude, longitude):
    """
    Open Meteo API에서 현재 외기온도, 외기습도, 풍속을 가져옵니다.
    API key 없이 사용 가능합니다.
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
    contract_status
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

    if store_type == "베이커리 카페":
        recommendations.append(
            "베이커리 카페는 오븐, 발효기, 냉동고, 냉방이 동시에 작동할 때 피크가 커질 수 있습니다. 오븐 예열과 냉방 피크 시간이 겹치지 않도록 운영하세요."
        )
    else:
        recommendations.append(
            "일반 카페는 제빙기, 쇼케이스, 냉장고, 냉방기가 주요 전력 원인입니다. 먼저 24시간 작동 장비의 상태를 확인하세요."
        )

    return recommendations[:4]


# -----------------------------
# 헤더
# -----------------------------

st.markdown('<div class="main-title">☕ CafeWatt</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">카페와 베이커리 카페의 전기요금, 실내환경, 장비 사용 패턴을 바탕으로 에너지 낭비 가능성을 쉽게 진단합니다.</div>',
    unsafe_allow_html=True
)


# -----------------------------
# 사이드바 입력
# -----------------------------

st.sidebar.header("매장 정보 입력")

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

st.sidebar.header("실내환경")

indoor_temp = st.sidebar.slider("영업시간 평균 실내온도", 18.0, 32.0, 25.5, 0.5)
indoor_humidity = st.sidebar.slider("평균 실내습도", 20, 90, 55)

st.sidebar.divider()

st.sidebar.header("날씨 API")

use_weather_api = st.sidebar.checkbox("현재 날씨 자동 불러오기", value=True)

latitude = st.sidebar.number_input(
    "위도",
    value=37.5665,
    format="%.6f",
    help="기본값은 서울시청 기준입니다."
)

longitude = st.sidebar.number_input(
    "경도",
    value=126.9780,
    format="%.6f",
    help="기본값은 서울시청 기준입니다."
)

weather_data = None

if use_weather_api:
    weather_data = get_weather_open_meteo(latitude, longitude)

    if weather_data["success"] and weather_data["temperature"] is not None:
        outdoor_temp = float(weather_data["temperature"])
        outdoor_humidity = float(weather_data["humidity"]) if weather_data["humidity"] is not None else 55
        wind_speed = float(weather_data["wind_speed"]) if weather_data["wind_speed"] is not None else 0

        st.sidebar.success(
            f"현재 외기온도 {outdoor_temp:.1f}°C / 외기습도 {outdoor_humidity:.0f}%"
        )
    else:
        st.sidebar.warning("날씨 데이터를 불러오지 못했습니다. 수동 입력값을 사용하세요.")
        outdoor_temp = st.sidebar.slider("평균 외기온도", 0.0, 38.0, 28.0, 0.5)
        outdoor_humidity = st.sidebar.slider("평균 외기습도", 10, 100, 60)
        wind_speed = 0
else:
    outdoor_temp = st.sidebar.slider("평균 외기온도", 0.0, 38.0, 28.0, 0.5)
    outdoor_humidity = st.sidebar.slider("평균 외기습도", 10, 100, 60)
    wind_speed = 0

st.sidebar.divider()

st.sidebar.header("스마트플러그 장비")

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


# -----------------------------
# 계산
# -----------------------------

benchmark = BENCHMARKS[store_type]

kwh_per_m2 = monthly_kwh / area_m2
kwh_per_hour = monthly_kwh / monthly_hours if monthly_hours > 0 else 0
price_per_kwh = monthly_bill / monthly_kwh if monthly_kwh > 0 else 0

ratio_area = kwh_per_m2 / benchmark["monthly_kwh_per_m2"]
ratio_hour = kwh_per_hour / benchmark["kwh_per_operating_hour"]

area_grade, area_class = grade_from_ratio(ratio_area)
hour_grade, hour_class = grade_from_ratio(ratio_hour)

energy_score = score_from_ratio((ratio_area + ratio_hour) / 2)

# 장비 기반 간단 최대부하 추정
if store_type == "일반 카페":
    estimated_peak_kw = max(6, area_pyeong * 0.55)
else:
    estimated_peak_kw = max(12, area_pyeong * 1.1)

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
    contract_status
)

estimated_saving_low = monthly_bill * 0.05
estimated_saving_high = monthly_bill * 0.15

if energy_score < 55:
    estimated_saving_low = monthly_bill * 0.08
    estimated_saving_high = monthly_bill * 0.22


# -----------------------------
# 메인 결과
# -----------------------------

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("종합 에너지 점수", f"{energy_score}점")

with col2:
    st.metric("월 전력사용량", kwh(monthly_kwh))

with col3:
    st.metric("월 전기요금", won(monthly_bill))

with col4:
    st.metric("예상 절감 여지", f"{won(estimated_saving_low)} ~ {won(estimated_saving_high)}")

with col5:
    st.metric("현재 외기온도", f"{outdoor_temp:.1f}°C")

st.divider()


# -----------------------------
# 진단 요약
# -----------------------------

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


# -----------------------------
# 날씨 분석
# -----------------------------

st.subheader("날씨와 냉방 부담")

weather_col1, weather_col2, weather_col3 = st.columns(3)

with weather_col1:
    st.metric("외기온도", f"{outdoor_temp:.1f}°C")

with weather_col2:
    st.metric("외기습도", f"{outdoor_humidity:.0f}%")

with weather_col3:
    st.metric("실내외 온도차", f"{indoor_temp - outdoor_temp:+.1f}°C")

if outdoor_temp >= 30 and indoor_temp <= 24:
    st.warning("외기온도가 높은데 실내온도가 낮게 유지되고 있습니다. 냉방 전력 사용이 커질 가능성이 있습니다.")
elif outdoor_temp >= 30 and indoor_temp > 27:
    st.warning("외기온도와 실내온도가 모두 높은 편입니다. 냉방 성능이나 출입문 개방으로 인한 냉방 손실을 확인하세요.")
else:
    st.success("현재 날씨 조건에서는 냉방 부담이 과도하게 높게 나타나지는 않습니다.")


st.divider()


# -----------------------------
# 스마트플러그 분석
# -----------------------------

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


# -----------------------------
# 추천 조치
# -----------------------------

st.subheader("CafeWatt 추천 조치")

for idx, rec in enumerate(recommendations, start=1):
    st.markdown(f"**{idx}. {rec}**")

st.divider()


# -----------------------------
# 요약
# -----------------------------

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


# -----------------------------
# 하단 안내
# -----------------------------

with st.expander("CafeWatt 진단 기준 안내"):
    st.write("""
    CafeWatt는 카페와 베이커리 카페의 기본 에너지 진단용 MVP입니다.

    현재 결과는 입력값과 간단한 업종 기준값을 바탕으로 계산됩니다.
    실제 서비스에서는 공공데이터, 실제 사용자 데이터, 센서 데이터가 누적되면서 업종 평균 기준을 계속 개선해야 합니다.

    계약전력 진단은 사전 참고용입니다.
    실제 계약전력 변경은 한전, 전기공사업체, 전기기사와 확인해야 합니다.

    스마트플러그 분석은 연결된 특정 장비의 사용량만 보여줍니다.
    매장 전체 전력사용량은 월 전력사용량 입력값을 기준으로 판단합니다.
    """)

st.caption("CafeWatt MVP 0.1 | 카페 전기요금 진단 AI")