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


# ─────────────────────────────────────────────────────────────
# 현재 트랜짓 계산 — "지금 이 사람에게 일어나고 있는 일" 후킹용
# ─────────────────────────────────────────────────────────────

# 외행성 × 출생 행성 × 어스펙트 → 현재 상황 설명 맵
_TRANSIT_SITUATIONS = {
    ('saturn', 'sun', True): {
        'situation': '지금 하려는 것들이 자꾸 막히고, 노력하는데 결과가 안 나오는 답답한 시기입니다.',
        'detail': '직장이나 커리어에서 압박감이 크고, 내가 제대로 가고 있는 건지 확신이 안 서는 감각이 있을 겁니다. 무기력과 책임감 사이를 왔다갔다하고 있다면 지금이 딱 그 시기입니다.',
        'theme': 'career_block',
    },
    ('saturn', 'moon', True): {
        'situation': '감정적으로 무겁고, 관계에서 소진되는 느낌. 혼자 있고 싶은데 동시에 외로운 그 이상한 감각이 지금 있을 겁니다.',
        'detail': '주변 사람들과 뭔가 어긋나는 것 같고, 감정 표현이 평소보다 어렵게 느껴지는 시기입니다. 관계가 잘못된 게 아니라 지금 감정 에너지가 아래로 내려앉는 구간입니다.',
        'theme': 'emotional_drain',
    },
    ('saturn', 'venus', True): {
        'situation': '연애나 주변 관계에서 현실적인 부분들이 자꾸 부딪히는 시기. 원하는 것과 실제 상황 사이의 간격이 유독 크게 느껴질 겁니다.',
        'detail': '관계에서 기대했던 것들이 충족되지 않거나, 관계를 유지하는 것 자체에 에너지가 많이 드는 시기입니다.',
        'theme': 'relationship_reality',
    },
    ('saturn', 'mars', True): {
        'situation': '뭔가 해야 하는 건 아는데 실행이 안 되거나, 행동을 해도 성과가 안 보이는 답답한 시기입니다.',
        'detail': '의욕과 실행 사이의 간격이 크고, 에너지를 쏟아도 방향이 안 잡히는 번아웃 직전의 감각이 있을 수 있습니다.',
        'theme': 'action_block',
    },
    ('jupiter', 'sun', True): {
        'situation': '새로운 기회나 가능성이 보이는데, 어디로 가야 할지 선택이 어려운 시기입니다. 더 크게 살고 싶다는 욕구가 강하게 올라오고 있을 겁니다.',
        'detail': '이것저것 동시에 잡으려다 정작 집중이 안 되는 패턴이 나타날 수 있습니다. 이 흐름을 잘 타면 작은 시도가 생각보다 큰 결과로 이어집니다.',
        'theme': 'opportunity',
    },
    ('jupiter', 'sun', False): {
        'situation': '오랫동안 막혔던 것이 조금씩 열리는 느낌이 들거나, 뭔가 잘 풀리는 감각이 오는 시기입니다.',
        'detail': '이 흐름을 알아차리고 움직이면 작은 시도가 생각보다 큰 결과로 이어질 수 있습니다.',
        'theme': 'opportunity_open',
    },
    ('jupiter', 'moon', True): {
        'situation': '지금 있는 환경이나 관계에서 뭔가 더 원하는 게 생겼고, 변화에 대한 욕구가 강하게 올라오는 시기입니다.',
        'detail': '현재에 만족하지 못하는 감각이 있다면, 그게 단순한 불만이 아니라 성장 신호일 수 있습니다.',
        'theme': 'change_desire',
    },
    ('jupiter', 'moon', False): {
        'situation': '감정적으로 뭔가 더 원하는 게 생기고, 변화에 대한 욕구가 올라오는 시기입니다.',
        'detail': '지금의 불만족감은 더 넓게 살고 싶다는 신호입니다.',
        'theme': 'change_desire',
    },
    ('uranus', 'sun', True): {
        'situation': '지금까지 해온 것들을 뒤집고 싶은 충동이 있고, 예상하지 못한 변화들이 일어나거나 일어날 것 같은 불안한 기대감이 공존하는 시기입니다.',
        'detail': '안정적으로 살고 싶은데 자꾸 흔들리거나, 스스로 흔들고 싶어지는 양면적인 감각. 지금 딱 그 시기에 있습니다.',
        'theme': 'sudden_change',
    },
    ('uranus', 'moon', True): {
        'situation': '감정이 예측불가로 요동치고, 주변 관계에서 갑작스런 변화가 일어나거나 일어나고 있을 겁니다.',
        'detail': '평소에는 괜찮던 것들이 갑자기 불편해지거나, 오래된 관계에서 균열이 생기는 느낌이 드는 시기입니다.',
        'theme': 'emotional_disruption',
    },
    ('uranus', 'venus', True): {
        'situation': '관계나 돈에서 갑작스런 변화가 생기거나, 기존의 방식을 완전히 바꾸고 싶은 충동이 강하게 오는 시기입니다.',
        'detail': '이 충동은 단순한 변덕이 아니라 진짜 변화가 필요한 시점이라는 신호일 수 있습니다.',
        'theme': 'relationship_disruption',
    },
    ('neptune', 'sun', True): {
        'situation': '방향이 흐릿하고, 내가 진짜 뭘 원하는지 잘 모르겠는 안개 같은 시기를 지나고 있습니다.',
        'detail': '노력은 하는데 어디로 가는 건지 모르겠고, 예전에 확신했던 것들이 지금은 흔들립니다. 이 흐릿함은 당신이 잘못된 게 아니라 재정비가 필요한 구간입니다.',
        'theme': 'confusion',
    },
    ('neptune', 'moon', True): {
        'situation': '내 감정인지 남의 감정인지 경계가 흐릿하고, 관계에서 뭔가 불명확한 느낌이 드는 시기입니다.',
        'detail': '이상과 현실 사이를 왔다갔다하고, 결정을 내리기가 유독 어려운 시기입니다.',
        'theme': 'emotional_confusion',
    },
    ('pluto', 'sun', True): {
        'situation': '깊은 곳에서 뭔가를 끝내고 새로 시작하고 싶은 강한 압박을 느끼는 시기입니다. 지금까지의 자신을 완전히 바꾸고 싶다는 충동이 있을 겁니다.',
        'detail': '이 변화 욕구는 단순한 충동이 아니라, 당신의 삶에서 뭔가가 끝나야 할 때가 됐다는 신호입니다.',
        'theme': 'transformation',
    },
    ('pluto', 'moon', True): {
        'situation': '감정적으로 낡은 것을 털어내야 하는 시기에 있습니다. 오래된 상처나 패턴이 다시 표면으로 올라오는 느낌이 있을 겁니다.',
        'detail': '지금 힘들게 느껴지는 감각들은 더 깊은 변화를 위한 전처리 과정입니다.',
        'theme': 'emotional_transformation',
    },
    ('pluto', 'venus', True): {
        'situation': '관계나 돈에 대한 가치관이 뿌리부터 흔들리는 시기입니다. 오래된 집착이나 패턴을 끝내야 한다는 감각이 강하게 옵니다.',
        'detail': '이 불편함은 변화 직전의 신호입니다.',
        'theme': 'value_transformation',
    },
}

# 어스펙트 허용 오차 (target_deg, max_orb)
_HARD_ASPECTS = [(0, 8), (180, 8), (90, 7)]
_SOFT_ASPECTS = [(120, 8), (60, 6)]

_PLANET_WEIGHT = {'sun': 4.0, 'moon': 3.5, 'venus': 2.5, 'mars': 2.0, 'mercury': 1.5}
_OUTER_WEIGHT  = {'saturn': 4.0, 'pluto': 3.5, 'uranus': 3.0, 'neptune': 2.5, 'jupiter': 2.0}
_OUTER_PLANETS = ['saturn', 'jupiter', 'uranus', 'neptune', 'pluto']
_NATAL_TARGETS = ['sun', 'moon', 'venus', 'mars']


def _lon_diff(a: float, b: float) -> float:
    """두 황경 사이의 최소 각도 차이 (0~180°)"""
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def _aspect_score(diff_deg: float):
    """(is_hard: bool, score: float) 반환. 어스펙트 없으면 (None, 0)."""
    for target, max_orb in _HARD_ASPECTS:
        orb = abs(diff_deg - target)
        if orb <= max_orb:
            return True, float(max_orb - orb)
    for target, max_orb in _SOFT_ASPECTS:
        orb = abs(diff_deg - target)
        if orb <= max_orb:
            return False, float(max_orb - orb) * 0.5
    return None, 0.0


def compute_current_transits(year, month, day, hour, minute, lat, lon, tz_offset=9):
    """
    출생 정보 + 현재 날짜 기준 가장 강하게 작동 중인 트랜짓 계산.
    반환: dict({'situation', 'detail', 'theme'}) 또는 None
    """
    try:
        import ephem
        import datetime as _dt2

        local_birth = _dt.datetime(year, month, day, max(hour, 0), minute)
        utc_birth   = local_birth - _dt.timedelta(hours=tz_offset)
        utc_now     = _dt.datetime.utcnow()

        obs_birth = ephem.Observer(); obs_birth.lat = str(lat); obs_birth.lon = str(lon)
        obs_birth.date = ephem.Date(utc_birth)
        obs_now   = ephem.Observer(); obs_now.lat = str(lat); obs_now.lon = str(lon)
        obs_now.date   = ephem.Date(utc_now)

        def _get_lon(body, obs):
            body.compute(obs)
            return math.degrees(ephem.Ecliptic(body).lon) % 360

        planet_makers = {
            'sun': ephem.Sun, 'moon': ephem.Moon, 'mercury': ephem.Mercury,
            'venus': ephem.Venus, 'mars': ephem.Mars,
            'jupiter': ephem.Jupiter, 'saturn': ephem.Saturn,
            'uranus': ephem.Uranus, 'neptune': ephem.Neptune,
        }
        try:
            planet_makers['pluto'] = ephem.Pluto
        except AttributeError:
            pass  # 구버전 ephem 호환

        # 출생 행성 황경
        natal_lons = {}
        for name in _NATAL_TARGETS:
            if name in planet_makers:
                natal_lons[name] = _get_lon(planet_makers[name](), obs_birth)

        # 현재 외행성 황경
        current_lons = {}
        for name in _OUTER_PLANETS:
            if name in planet_makers:
                current_lons[name] = _get_lon(planet_makers[name](), obs_now)

        # 가장 강한 트랜짓 탐색
        best_score = 0.0
        best_key   = None
        for tp in _OUTER_PLANETS:
            if tp not in current_lons:
                continue
            for np_ in _NATAL_TARGETS:
                if np_ not in natal_lons:
                    continue
                diff = _lon_diff(current_lons[tp], natal_lons[np_])
                is_hard, asp = _aspect_score(diff)
                if is_hard is None:
                    continue
                score = asp * _OUTER_WEIGHT[tp] * _PLANET_WEIGHT[np_]
                if score > best_score:
                    best_score = score
                    best_key   = (tp, np_, is_hard)

        if not best_key:
            return None

        data = _TRANSIT_SITUATIONS.get(best_key)
        if not data:
            # 반대 is_hard로 시도
            alt = (best_key[0], best_key[1], not best_key[2])
            data = _TRANSIT_SITUATIONS.get(alt)
        return data  # None이면 호출자가 fallback 처리

    except Exception as e:
        log.warning(f'트랜짓 계산 실패: {e}')
        return None


def build_transit_hook_context(year, month, day, hour, minute, city, tz_offset=9) -> str:
    """
    GPT 내부용: 현재 트랜짓 기반 '현재 상황 후킹' 컨텍스트.
    점성술 용어 절대 노출 금지. 계산 불가 시 빈 문자열.
    """
    resolved = resolve_city(city)
    if not resolved:
        return ''
    lat, lon, _ = resolved
    transit = compute_current_transits(year, month, day, hour, minute, lat, lon, tz_offset)
    if not transit:
        return ''
    lines = [
        '',
        '【현재 상황 후킹 데이터 — 최우선. 첫 섹션 팩폭 오프닝에 반드시 활용. 천체·행성·별자리 용어 절대 금지】',
        f"- 지금 이 사람이 겪고 있을 현실 상황: {transit['situation']}",
        f"- 구체적 맥락: {transit['detail']}",
        f"- 현재 주제 코드(내부용): {transit['theme']}",
        '첫 문장부터 이 상황을 직격해야 한다. "지금 당신 딱 이 상황이죠?" 하고.',
    ]
    return '\n'.join(lines)


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
