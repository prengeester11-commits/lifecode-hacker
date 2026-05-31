"""
출생 차트 기반 '기질 강점' 추출 모듈 (PyEphem).

중요: 이 모듈의 결과는 보고서에 '점성술'로 노출되지 않는다.
행성/별자리 위치를 계산하되, 외부로는 점성술 용어 없이
'기질 강점' 형태의 plain 한국어 설명만 GPT 내부 컨텍스트로 전달한다.

태어난 도시로 위치를 잡아 출생 차트의 원소(불·흙·바람·물)·양식 균형을 산출,
명리 분석과 융합할 강점 신호를 만든다.
"""
import math
import logging
import datetime as _dt

log = logging.getLogger(__name__)

# 원소(element) / 양식(modality) — 12 사인 인덱스 0~11
_ELEMENT = ['불', '흙', '바람', '물', '불', '흙', '바람', '물', '불', '흙', '바람', '물']
_MODALITY = ['주도', '안정', '변화', '주도', '안정', '변화', '주도', '안정', '변화', '주도', '안정', '변화']

# 원소별 강점 키워드 (점성술 용어 없음)
_ELEMENT_STRENGTH = {
    '불': '추진력·열정·즉각 실행·솔직한 자기표현',
    '흙': '안정감·끈기·현실 감각·책임감·신뢰',
    '바람': '소통력·아이디어·객관적 사고·사교성·호기심',
    '물': '공감력·직관·섬세한 감수성·깊은 정서·돌봄',
}
_MODALITY_STRENGTH = {
    '주도': '먼저 시작하고 판을 여는 추진형',
    '안정': '끝까지 밀고 가는 끈기·집중형',
    '변화': '상황에 유연하게 적응하는 융통형',
}

# 주요 한국 도시 좌표 (lat, lon). 미매칭 시 서울 기본값.
_CITY_DB = {
    '서울': (37.5665, 126.9780), '부산': (35.1796, 129.0756), '인천': (37.4563, 126.7052),
    '대구': (35.8714, 128.6014), '대전': (36.3504, 127.3845), '광주': (35.1595, 126.8526),
    '울산': (35.5384, 129.3114), '세종': (36.4800, 127.2890), '수원': (37.2636, 127.0286),
    '창원': (35.2280, 128.6811), '고양': (37.6584, 126.8320), '용인': (37.2411, 127.1776),
    '성남': (37.4200, 127.1267), '청주': (36.6424, 127.4890), '전주': (35.8242, 127.1480),
    '천안': (36.8151, 127.1139), '안산': (37.3219, 126.8309), '제주': (33.4996, 126.5312),
    '포항': (36.0190, 129.3435), '춘천': (37.8813, 127.7298), '강릉': (37.7519, 128.8761),
    '목포': (34.8118, 126.3922), '여수': (34.7604, 127.6622), '김해': (35.2285, 128.8894),
}
_DEFAULT_CITY = '서울'


def resolve_city(city: str):
    """도시명(부분일치) → (lat, lon, matched_name). 미입력/미매칭 시 None 또는 서울."""
    if not city:
        return None
    c = city.strip().replace('특별시', '').replace('광역시', '').replace('시', '').replace('특별자치도', '').strip()
    for key, (lat, lon) in _CITY_DB.items():
        if key in city or key in c:
            return (lat, lon, key)
    # 미매칭: 한국 사용자 가정, 서울 좌표로 근사 (행성 원소 균형은 위치 영향 거의 없음)
    lat, lon = _CITY_DB[_DEFAULT_CITY]
    return (lat, lon, _DEFAULT_CITY)


def _sign_of(body, observer):
    """천체의 황경(ecliptic longitude) → 12 사인 인덱스 0~11"""
    import ephem
    ecl = ephem.Ecliptic(body)
    lon_deg = math.degrees(ecl.lon) % 360
    return int(lon_deg // 30)


def compute_astro(year, month, day, hour, minute, lat, lon, tz_offset=9):
    """
    출생 차트의 원소·양식 균형과 핵심 3요소(자기/정서/인상)의 원소를 계산.
    반환: dict 또는 None(계산 실패).
    """
    try:
        import ephem
    except Exception as e:
        log.warning(f'ephem 미설치 — 기질 보강 생략: {e}')
        return None

    try:
        # 현지시각 → UTC
        local = _dt.datetime(year, month, day, max(hour, 0), minute)
        utc = local - _dt.timedelta(hours=tz_offset)

        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = ephem.Date(utc)

        bodies = {
            'sun': ephem.Sun(), 'moon': ephem.Moon(), 'mercury': ephem.Mercury(),
            'venus': ephem.Venus(), 'mars': ephem.Mars(),
            'jupiter': ephem.Jupiter(), 'saturn': ephem.Saturn(),
        }
        signs = {}
        for name, b in bodies.items():
            b.compute(obs)
            signs[name] = _sign_of(b, obs)

        # 상승점(Ascendant) — 현지 항성시 기반
        asc_sign = None
        try:
            ramc = float(obs.sidereal_time())  # 라디안
            eps = math.radians(23.4367)
            lat_r = math.radians(float(lat))
            asc = math.atan2(math.cos(ramc),
                             -(math.sin(ramc) * math.cos(eps) + math.tan(lat_r) * math.sin(eps)))
            asc_deg = math.degrees(asc) % 360
            asc_sign = int(asc_deg // 30)
        except Exception:
            asc_sign = None

        # 원소·양식 집계 (7천체 + 상승점)
        elem_count = {'불': 0, '흙': 0, '바람': 0, '물': 0}
        mod_count = {'주도': 0, '안정': 0, '변화': 0}
        all_signs = list(signs.values()) + ([asc_sign] if asc_sign is not None else [])
        for s in all_signs:
            elem_count[_ELEMENT[s]] += 1
            mod_count[_MODALITY[s]] += 1

        return {
            'sun_elem': _ELEMENT[signs['sun']],
            'moon_elem': _ELEMENT[signs['moon']],
            'asc_elem': _ELEMENT[asc_sign] if asc_sign is not None else None,
            'elem_count': elem_count,
            'mod_count': mod_count,
        }
    except Exception as e:
        log.warning(f'기질 보강 계산 실패: {e}')
        return None


def build_astro_context(year, month, day, hour, minute, city, tz_offset=9) -> str:
    """
    GPT 내부용 '기질 보강 데이터' 컨텍스트 문자열 생성.
    점성술 용어 없이 강점 신호만. 계산 불가 시 빈 문자열.
    """
    resolved = resolve_city(city)
    if not resolved:
        return ''
    lat, lon, _ = resolved
    a = compute_astro(year, month, day, hour, minute, lat, lon, tz_offset)
    if not a:
        return ''

    # 가장 강한 원소 1~2개, 양식 1개
    elem_sorted = sorted(a['elem_count'].items(), key=lambda x: x[1], reverse=True)
    top_elems = [e for e, c in elem_sorted if c > 0][:2]
    mod_sorted = sorted(a['mod_count'].items(), key=lambda x: x[1], reverse=True)
    top_mod = mod_sorted[0][0]

    lines = ['', '【기질 보강 데이터 — 내부 참고용. 아래 출처·용어는 절대 보고서에 노출 금지】']
    lines.append(f"- 핵심 자기표현 기질: {a['sun_elem']} 계열 → {_ELEMENT_STRENGTH[a['sun_elem']]}")
    lines.append(f"- 정서의 결: {a['moon_elem']} 계열 → {_ELEMENT_STRENGTH[a['moon_elem']]}")
    if a['asc_elem']:
        lines.append(f"- 바깥으로 비치는 첫인상: {a['asc_elem']} 계열 → {_ELEMENT_STRENGTH[a['asc_elem']]}")
    balance = ', '.join(f"{e} {c}" for e, c in elem_sorted if c > 0)
    lines.append(f"- 전반 기질 균형: {balance} (가장 강함: {', '.join(top_elems)})")
    lines.append(f"- 행동 양식: {top_mod} → {_MODALITY_STRENGTH[top_mod]}")
    lines.append("위 기질 강점들을 명리 분석의 강점과 자연스럽게 융합해 더 입체적으로 풀되, "
                 "점성술/별자리/행성/태양/달/상승점 등 어떤 용어·출처도 언급하지 말 것. "
                 "그냥 '당신의 타고난 기질'처럼 녹여서 표현하라.")
    return '\n'.join(lines)
