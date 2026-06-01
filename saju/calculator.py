"""
만세력 계산 엔진
사주팔자, 오행, 십신, 합충파해, 대운, 세운 계산
"""
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from .constants import (
    CHEONGAN, CHEONGAN_HANJA, CHEONGAN_OHAENG, CHEONGAN_UMYANG,
    JIJI, JIJI_HANJA, JIJI_OHAENG, JIJI_UMYANG, JIJI_12ZHI_ANIMAL,
    OHAENG, OHAENG_SAENG, OHAENG_GEUK,
    SIPSIN, SIPSIN_DESC,
    HOUR_BRANCH, HOUR_STEM_BASE,
    CHEONGAN_HAP, CHEONGAN_HAP_NAME, CHEONGAN_CHUNG,
    JIJI_YUKHAP, JIJI_YUKHAP_NAME,
    JIJI_SAMHAP, JIJI_CHUNG, JIJI_PA, JIJI_HAE,
    JIJI_JANGGAN, JIJI_BONGI,
    get_daewoon_direction, get_gapja_name, get_gapja_hanja
)
from .solar_terms import (
    get_month_branch, get_year_for_saju, get_nearest_solar_terms,
    get_solar_term_date
)

# ─────────────────────────────────────────────
# 일주 계산 상수 — 한국 정통 만세력 기준
# 교차검증 기준점:
#   • 1900-01-01 = 甲戌日 (갑술, 60갑자 position 10)
#   • 2000-01-01 = 戊午日 (무오, 60갑자 position 54)
#   • 1990-03-15 = 己卯日 (기묘, position 15)
#   • 1989-09-25 = 戊子日 (무자, position 24)
# date.toordinal() 기반: (ordinal + 14) % 60 = position
# 즉  date(2000,1,1).toordinal()=730120, 730120%60=40, (40+14)%60=54=戊午 ✓
# ─────────────────────────────────────────────
_DAY_OFFSET = 14

# 한국 진태양시 보정 (KST 기준 약 -30분)
# 한국 표준시는 동경 135도 기준이지만 한국은 동경 약 127도에 위치
# 보정값 = -30분 (정통 만세력 관행)
_KST_CORRECTION_MIN = -30


@dataclass
class Pillar:
    """사주 한 기둥 (년주/월주/일주/시주)"""
    label: str          # '년주', '월주', '일주', '시주'
    stem: int           # 천간 인덱스 (0-9)
    branch: int         # 지지 인덱스 (0-11)

    @property
    def stem_kor(self): return CHEONGAN[self.stem]
    @property
    def branch_kor(self): return JIJI[self.branch]
    @property
    def stem_hanja(self): return CHEONGAN_HANJA[self.stem]
    @property
    def branch_hanja(self): return JIJI_HANJA[self.branch]
    @property
    def name_kor(self): return self.stem_kor + self.branch_kor
    @property
    def name_hanja(self): return self.stem_hanja + self.branch_hanja
    @property
    def ohaeng_stem(self): return OHAENG[CHEONGAN_OHAENG[self.stem]]
    @property
    def ohaeng_branch(self): return OHAENG[JIJI_OHAENG[self.branch]]
    @property
    def animal(self): return JIJI_12ZHI_ANIMAL[self.branch]


@dataclass
class DaeWoon:
    """대운 (10년 주기 운)"""
    start_age: int
    end_age: int
    stem: int
    branch: int
    is_current: bool = False

    @property
    def name(self): return CHEONGAN[self.stem] + JIJI[self.branch]
    @property
    def name_hanja(self): return CHEONGAN_HANJA[self.stem] + JIJI_HANJA[self.branch]
    @property
    def ohaeng(self): return OHAENG[CHEONGAN_OHAENG[self.stem]]


@dataclass
class SeWoon:
    """세운 (연간 운)"""
    year: int
    stem: int
    branch: int

    @property
    def name(self): return CHEONGAN[self.stem] + JIJI[self.branch]
    @property
    def name_hanja(self): return CHEONGAN_HANJA[self.stem] + JIJI_HANJA[self.branch]


@dataclass
class HapChungResult:
    """합충파해 분석 결과"""
    haps: List[str] = field(default_factory=list)      # 합 목록
    chungs: List[str] = field(default_factory=list)    # 충 목록
    pas: List[str] = field(default_factory=list)       # 파 목록
    haes: List[str] = field(default_factory=list)      # 해 목록


@dataclass
class SajuResult:
    """전체 사주 분석 결과"""
    name: str
    birth_date: str
    birth_time: str
    gender: str
    is_lunar: bool

    # 사주팔자 (전통 표기: 시→일→월→년 순)
    si_ju: Pillar    # 시주
    il_ju: Pillar    # 일주
    wol_ju: Pillar   # 월주
    nyeon_ju: Pillar # 년주

    # 오행 분포 (0-4: 목화토금수)
    ohaeng_count: Dict[str, int]
    ohaeng_score: Dict[str, float]  # 지장간 가중치 포함

    # 일간 정보
    ilgan: int          # 일간 천간 인덱스
    ilgan_ohaeng: str   # 일간 오행
    is_strong: bool     # 신강/신약
    strength_detail: dict  # 월령/득지/득세 상세

    # 십신
    sipsin_map: Dict[str, str]  # 각 기둥별 십신

    # 합충파해
    hapchung: HapChungResult

    # 대운
    daewoon_start_age: int      # 첫 대운 시작 나이
    daewoon_list: List[DaeWoon]
    current_daewoon: Optional[DaeWoon]

    # 세운 (올해·내년 동적)
    sewoon_first: SeWoon
    sewoon_second: SeWoon

    # 현재 나이
    current_age: int


def _get_day_pillar(year: int, month: int, day: int) -> Tuple[int, int]:
    """일간지 계산"""
    ordinal = date(year, month, day).toordinal()
    pos = (ordinal + _DAY_OFFSET) % 60
    return pos % 10, pos % 12


def _get_year_pillar(saju_year: int) -> Tuple[int, int]:
    """년간지 계산 (입춘 기준 연도 적용 후)"""
    stem = (saju_year - 4) % 10
    branch = (saju_year - 4) % 12
    return stem, branch


def _get_month_pillar(year_stem: int, month_branch: int) -> Tuple[int, int]:
    """
    월간지 계산
    인월(寅=2) 기준 천간:
      갑/기년 → 병인(2), 을/경년 → 무인(4), 병/신년 → 경인(6)
      정/임년 → 임인(8), 무/계년 → 갑인(0)
    """
    base = [2, 4, 6, 8, 0][year_stem % 5]
    # 인월(2)부터 시작하는 월지 순서: 인(2), 묘(3), ..., 해(11), 자(0), 축(1)
    month_index_from_in = (month_branch - 2) % 12
    stem = (base + month_index_from_in) % 10
    return stem, month_branch


def _get_hour_pillar(day_stem: int, hour: int, minute: int = 0) -> Tuple[int, int]:
    """
    시간지 계산 — 한국 진태양시 보정 적용

    KST 09:00 → -30분 → 08:30 → 진시(辰時)
    KST 20:00 → -30분 → 19:30 → 술시(戌時)
    KST 23:00 → -30분 → 22:30 → 해시(亥時)
    """
    # 한국 표준시 → 진태양시 보정
    total_min = hour * 60 + minute + _KST_CORRECTION_MIN
    if total_min < 0:
        total_min += 24 * 60
    corrected_hour = (total_min // 60) % 24

    branch = HOUR_BRANCH.get(corrected_hour, 0)
    base = HOUR_STEM_BASE[day_stem]
    stem = (base + branch) % 10
    return stem, branch


def _get_sipsin(ilgan: int, target_stem: int) -> str:
    """십신 계산"""
    il_oh = CHEONGAN_OHAENG[ilgan]
    ta_oh = CHEONGAN_OHAENG[target_stem]
    il_uy = CHEONGAN_UMYANG[ilgan]
    ta_uy = CHEONGAN_UMYANG[target_stem]
    same = (il_uy == ta_uy)

    if il_oh == ta_oh:
        return '비견' if same else '겁재'
    elif OHAENG_SAENG[il_oh] == ta_oh:
        return '식신' if same else '상관'
    elif OHAENG_GEUK[il_oh] == ta_oh:
        return '편재' if same else '정재'
    elif OHAENG_GEUK[ta_oh] == il_oh:
        return '편관' if same else '정관'
    elif OHAENG_SAENG[ta_oh] == il_oh:
        return '편인' if same else '정인'
    return '?'


def get_gyeokguk(ilgan: int, wol_branch: int) -> dict:
    """
    격국(格局) 판정 — 월지(月支) 본기의 십신을 기준으로 한다.
    (왕지/표준 케이스에 정확. 비견/겁재는 건록격/양인격으로.)
    무자일주 월지 酉(본기 辛) → 무토 기준 상관 → 상관격. (검증 케이스)
    """
    bongi = JIJI_BONGI[wol_branch]
    sipsin = _get_sipsin(ilgan, bongi)
    name_map = {
        '비견': '건록격', '겁재': '양인격',
        '식신': '식신격', '상관': '상관격',
        '편재': '편재격', '정재': '정재격',
        '편관': '편관격', '정관': '정관격',
        '편인': '편인격', '정인': '정인격',
    }
    return {
        'sipsin': sipsin,
        'name': name_map.get(sipsin, '특수격'),
        'wol_bongi': CHEONGAN[bongi],
    }


def _calc_ohaeng(pillars: List[Pillar]) -> Tuple[Dict, Dict]:
    """오행 분포 계산 (기본 + 지장간 가중치)"""
    count = {oh: 0 for oh in OHAENG}
    score = {oh: 0.0 for oh in OHAENG}

    for p in pillars:
        # 천간 오행
        oh = OHAENG[CHEONGAN_OHAENG[p.stem]]
        count[oh] += 1
        score[oh] += 1.0

        # 지지 오행 (지장간 포함)
        jj_oh = OHAENG[JIJI_OHAENG[p.branch]]
        count[jj_oh] += 1
        score[jj_oh] += 0.8

        # 지장간 세부 (여기)
        for hidden in JIJI_JANGGAN.get(p.branch, []):
            h_oh = OHAENG[CHEONGAN_OHAENG[hidden]]
            score[h_oh] += 0.2

    return count, score


def _check_hapchung(pillars: List[Pillar]) -> HapChungResult:
    """합충파해 분석"""
    result = HapChungResult()
    stems = [p.stem for p in pillars]
    branches = [p.branch for p in pillars]
    labels = [p.label for p in pillars]

    # 천간합
    for i in range(len(stems)):
        for j in range(i + 1, len(stems)):
            key = (stems[i], stems[j])
            if key in CHEONGAN_HAP_NAME:
                name = CHEONGAN_HAP_NAME[key]
                result.haps.append(f"{labels[i]}-{labels[j]} {name}")

    # 천간충 / 천간극 (인접 기둥끼리: 년-월, 월-일, 일-시)
    hap_keys = set(CHEONGAN_HAP_NAME.keys())
    for i in range(len(stems) - 1):
        j = i + 1
        a, b = stems[i], stems[j]
        if (a, b) in CHEONGAN_CHUNG:
            result.chungs.append(f"{labels[i]}-{labels[j]} {CHEONGAN_CHUNG[(a, b)]}(천간충)")
        elif (a, b) not in hap_keys:
            oa, ob = CHEONGAN_OHAENG[a], CHEONGAN_OHAENG[b]
            if OHAENG_GEUK[oa] == ob:       # a가 b를 극
                result.chungs.append(
                    f"{labels[i]}-{labels[j]} {CHEONGAN[a]}{CHEONGAN[b]}극(천간극, {OHAENG[oa]}극{OHAENG[ob]})")
            elif OHAENG_GEUK[ob] == oa:      # b가 a를 극
                result.chungs.append(
                    f"{labels[i]}-{labels[j]} {CHEONGAN[b]}{CHEONGAN[a]}극(천간극, {OHAENG[ob]}극{OHAENG[oa]})")

    # 지지 육합
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            key = (branches[i], branches[j])
            if key in JIJI_YUKHAP_NAME:
                name = JIJI_YUKHAP_NAME[key]
                result.haps.append(f"{labels[i]}-{labels[j]} {name}")

    # 지지 삼합
    for members, oh, name in JIJI_SAMHAP:
        matched = [labels[i] for i, b in enumerate(branches) if b in members]
        if len(matched) >= 2:
            result.haps.append(f"{'/'.join(matched)} {name}")

    # 지지충
    for b1, b2, name in JIJI_CHUNG:
        i_list = [i for i, b in enumerate(branches) if b == b1]
        j_list = [j for j, b in enumerate(branches) if b == b2]
        for i in i_list:
            for j in j_list:
                result.chungs.append(f"{labels[i]}-{labels[j]} {name}")

    # 지지파
    for b1, b2, name in JIJI_PA:
        i_list = [i for i, b in enumerate(branches) if b == b1]
        j_list = [j for j, b in enumerate(branches) if b == b2]
        for i in i_list:
            for j in j_list:
                result.pas.append(f"{labels[i]}-{labels[j]} {name}")

    # 지지해
    for b1, b2, name in JIJI_HAE:
        i_list = [i for i, b in enumerate(branches) if b == b1]
        j_list = [j for j, b in enumerate(branches) if b == b2]
        for i in i_list:
            for j in j_list:
                result.haes.append(f"{labels[i]}-{labels[j]} {name}")

    return result


def _check_strength(ilgan: int, pillars: List[Pillar]) -> Tuple[bool, dict]:
    """
    한국 정통 만세력 신강/신약 판정
    핵심 3요소:
      - 월령(月令, 가중치 3): 월지가 일간을 돕는가 (비겁 또는 인성)
      - 득지(得地, 가중치 2): 일지가 일간을 돕는가
      - 득세(得勢, 가중치 1): 나머지 자리에서 비겁/인성 합계

    돕는 오행 = 비겁(같은 오행) + 인성(나를 생하는 오행)
    빼앗는 오행 = 식상(내가 생) + 재성(내가 극) + 관성(나를 극)

    pillars 순서: [년주, 월주, 일주, 시주]
    """
    il_oh = CHEONGAN_OHAENG[ilgan]

    # 인성 오행 (나를 생하는 오행): OHAENG_SAENG[X] == il_oh 인 X
    inseong_oh = None
    for i, target in enumerate(OHAENG_SAENG):
        if target == il_oh:
            inseong_oh = i
            break

    # 일간을 돕는 오행 (비겁 + 인성)
    helping = {il_oh, inseong_oh}

    nyeon, wol, il, si = pillars

    # ─ 월령 (가중치 3) ─
    wol_branch_oh = JIJI_OHAENG[wol.branch]
    weolryeong = wol_branch_oh in helping
    score_w = 3 if weolryeong else 0

    # ─ 득지 (가중치 2) ─
    il_branch_oh = JIJI_OHAENG[il.branch]
    deukji = il_branch_oh in helping
    score_d = 2 if deukji else 0

    # ─ 득세 (가중치 1) ─
    # 시간/년주 천간+지지 + 월간 (월지·일지 제외)
    others_oh = [
        CHEONGAN_OHAENG[si.stem],    JIJI_OHAENG[si.branch],
        CHEONGAN_OHAENG[nyeon.stem], JIJI_OHAENG[nyeon.branch],
        CHEONGAN_OHAENG[wol.stem],
    ]
    score_s = sum(1 for o in others_oh if o in helping)

    total_score = score_w + score_d + score_s

    # 판정 룰:
    #   1) 월령+득지 모두 실패하면 → 무조건 신약 (한국 정통 룰)
    #   2) 월령 성공 + 총점 5점 이상 → 신강
    #   3) 월령 실패시 총점 6점 이상이어야 신강
    if not weolryeong and not deukji:
        is_strong = False
    elif weolryeong:
        is_strong = total_score >= 5
    else:
        is_strong = total_score >= 6

    detail = {
        'weolryeong': weolryeong,
        'deukji': deukji,
        'score_weolryeong': score_w,
        'score_deukji': score_d,
        'score_deukse': score_s,
        'total': total_score,
        'helping_ohaeng': sorted([OHAENG[o] for o in helping if o is not None]),
    }
    return is_strong, detail


def _calc_daewoon(
    birth_date: date, month_stem: int, month_branch: int,
    year_stem: int, gender: str, current_year: int
) -> Tuple[int, List[DaeWoon], Optional[DaeWoon]]:
    """대운 계산"""
    forward = get_daewoon_direction(year_stem, gender)

    # 이전/다음 절기 찾기
    prev_term, next_term = get_nearest_solar_terms(
        birth_date.year, birth_date.month, birth_date.day
    )

    # 대운 시작 나이 = 절기까지의 일수 / 3
    if forward and next_term:
        days = (next_term[0] - birth_date).days
    elif not forward and prev_term:
        days = (birth_date - prev_term[0]).days
    else:
        days = 30  # fallback

    start_age = max(1, round(days / 3))

    # 대운 10주기 생성
    daewoon_list = []
    for i in range(10):
        if forward:
            pos = (month_stem * 12 + month_branch + (i + 1) * 12) % 60
            # 60갑자에서 순서대로 +1씩
            base_pos = (month_stem + (i + 1)) % 60
            d_stem = (month_stem + i + 1) % 10
            d_branch = (month_branch + i + 1) % 12
        else:
            d_stem = (month_stem - i - 1) % 10
            d_branch = (month_branch - i - 1) % 12

        age_start = start_age + i * 10
        age_end = age_start + 9

        current_age = current_year - (birth_date.year)
        is_current = (age_start <= current_age <= age_end)

        dw = DaeWoon(
            start_age=age_start,
            end_age=age_end,
            stem=d_stem,
            branch=d_branch,
            is_current=is_current
        )
        daewoon_list.append(dw)

    current_dw = next((dw for dw in daewoon_list if dw.is_current), None)
    return start_age, daewoon_list, current_dw


def _get_sewoon(year: int) -> SeWoon:
    """세운 계산"""
    stem = (year - 4) % 10
    branch = (year - 4) % 12
    return SeWoon(year=year, stem=stem, branch=branch)


def get_month_pillars(year: int) -> List[dict]:
    """
    해당 양력 연도의 12개월 월건(月建) 간지 — 五虎遁(년상기월법) 기준.
    양력 1~12월에 지지 丑寅卯辰巳午未申酉戌亥子를 매핑한 약식(절기 경계 비엄밀).
    예) 2026 병오년: 1월 己丑, 2월 庚寅, ..., 12월 庚子.
    """
    year_stem = (year - 4) % 10
    # 五虎遁: 寅月(정월)의 천간 = (년간%5)*2 + 2
    tiger_stem = ((year_stem % 5) * 2 + 2) % 10
    pillars = []
    for m in range(1, 13):
        branch = m % 12                       # 1월=축(1) ... 11월=해(11), 12월=자(0)
        stem = (tiger_stem + (m - 2)) % 10     # 寅月(2월) 기준 ±
        pillars.append({
            'month': m,
            'stem': stem,
            'branch': branch,
            'name': CHEONGAN[stem] + JIJI[branch],
            'name_hanja': CHEONGAN_HANJA[stem] + JIJI_HANJA[branch],
        })
    return pillars


def calculate_saju(
    name: str,
    year: int, month: int, day: int,
    hour: int, minute: int,
    gender: str,          # 'M' or 'F'
    is_lunar: bool = False
) -> SajuResult:
    """
    사주팔자 전체 계산
    is_lunar=True이면 음력 날짜를 양력으로 변환 후 계산
    """
    # 음력 변환
    if is_lunar:
        try:
            from korean_lunar_calendar import KoreanLunarCalendar
            cal = KoreanLunarCalendar()
            cal.setLunarDate(year, month, day, False)
            solar = cal.SolarIsoFormat().split('-')
            year, month, day = int(solar[0]), int(solar[1]), int(solar[2])
        except Exception:
            pass  # 변환 실패 시 양력으로 처리

    birth = date(year, month, day)
    current_year = date.today().year
    current_age = current_year - year

    # ── 년주 ──
    saju_year = get_year_for_saju(year, month, day)
    ny_stem, ny_branch = _get_year_pillar(saju_year)
    nyeon_ju = Pillar('년주', ny_stem, ny_branch)

    # ── 월주 ──
    month_branch = get_month_branch(year, month, day)
    wol_stem, wol_branch = _get_month_pillar(ny_stem, month_branch)
    wol_ju = Pillar('월주', wol_stem, wol_branch)

    # ── 일주 ──
    il_stem, il_branch = _get_day_pillar(year, month, day)
    il_ju = Pillar('일주', il_stem, il_branch)

    # ── 시주 ──
    si_stem, si_branch = _get_hour_pillar(il_stem, hour, minute)
    si_ju = Pillar('시주', si_stem, si_branch)

    # ── 오행 분포 ──
    all_pillars = [nyeon_ju, wol_ju, il_ju, si_ju]
    ohaeng_count, ohaeng_score = _calc_ohaeng(all_pillars)

    # ── 일간 정보 ──
    ilgan = il_stem
    ilgan_ohaeng = OHAENG[CHEONGAN_OHAENG[ilgan]]
    is_strong, strength_detail = _check_strength(ilgan, all_pillars)

    # ── 십신 ──
    sipsin_map = {}
    for p in all_pillars:
        sipsin_map[p.label + '_천간'] = _get_sipsin(ilgan, p.stem) if p.label != '일주' else '일간(나)'
        # 지지는 본기(本氣)로 십신 계산 (여기/중기가 아닌 대표 천간 기준)
        sipsin_map[p.label + '_지지'] = _get_sipsin(ilgan, JIJI_BONGI[p.branch])

    # ── 합충파해 ──
    hapchung = _check_hapchung(all_pillars)

    # ── 대운 ──
    daewoon_start, daewoon_list, current_dw = _calc_daewoon(
        birth, wol_stem, wol_branch, ny_stem, gender, current_year
    )

    # ── 세운 (올해·내년 동적 계산) ──
    sewoon_first = _get_sewoon(current_year)
    sewoon_second = _get_sewoon(current_year + 1)

    birth_time_str = f"{hour:02d}:{minute:02d}" if hour >= 0 else '미상'
    hour_names = {0:'자시',1:'축시',2:'인시',3:'묘시',4:'진시',5:'사시',
                  6:'오시',7:'미시',8:'신시',9:'유시',10:'술시',11:'해시'}
    si_name = hour_names.get(si_branch, '')

    return SajuResult(
        name=name,
        birth_date=f"{year}년 {month}월 {day}일",
        birth_time=f"{birth_time_str} ({si_name})",
        gender='남성' if gender == 'M' else '여성',
        is_lunar=is_lunar,
        si_ju=si_ju,
        il_ju=il_ju,
        wol_ju=wol_ju,
        nyeon_ju=nyeon_ju,
        ohaeng_count=ohaeng_count,
        ohaeng_score=ohaeng_score,
        ilgan=ilgan,
        ilgan_ohaeng=ilgan_ohaeng,
        is_strong=is_strong,
        strength_detail=strength_detail,
        sipsin_map=sipsin_map,
        hapchung=hapchung,
        daewoon_start_age=daewoon_start,
        daewoon_list=daewoon_list,
        current_daewoon=current_dw,
        sewoon_first=sewoon_first,
        sewoon_second=sewoon_second,
        current_age=current_age
    )


def saju_to_dict(result: SajuResult) -> dict:
    """SajuResult를 JSON 직렬화 가능한 딕셔너리로 변환"""
    from .constants import CHEONGAN, JIJI, OHAENG

    def pillar_dict(p: Pillar):
        return {
            'label': p.label,
            'stem': p.stem,
            'branch': p.branch,
            'stem_kor': p.stem_kor,
            'branch_kor': p.branch_kor,
            'stem_hanja': p.stem_hanja,
            'branch_hanja': p.branch_hanja,
            'name_kor': p.name_kor,
            'name_hanja': p.name_hanja,
            'ohaeng_stem': p.ohaeng_stem,
            'ohaeng_branch': p.ohaeng_branch,
            'animal': p.animal,
        }

    ohaeng_total = sum(result.ohaeng_score.values()) or 1
    ohaeng_pct = {k: round(v / ohaeng_total * 100) for k, v in result.ohaeng_score.items()}

    # ── 시간 흐름(월운·세운·대운)의 십신을 일간 기준으로 미리 계산 ──
    #    (GPT가 추측하다 틀리는 것을 방지: 천간=그대로, 지지=본기 기준)
    ilg = result.ilgan

    # 격국(월지 본기 기준) — GPT 추측 방지
    gyeokguk = get_gyeokguk(result.ilgan, result.wol_ju.branch)

    def _sipsin_pair(stem, branch):
        return _get_sipsin(ilg, stem), _get_sipsin(ilg, JIJI_BONGI[branch])

    month_pillars = get_month_pillars(result.sewoon_first.year)
    for mp in month_pillars:
        s_sip, b_sip = _sipsin_pair(mp['stem'], mp['branch'])
        mp['stem_sipsin'] = s_sip
        mp['branch_sipsin'] = b_sip

    sw1_s, sw1_b = _sipsin_pair(result.sewoon_first.stem, result.sewoon_first.branch)
    sw2_s, sw2_b = _sipsin_pair(result.sewoon_second.stem, result.sewoon_second.branch)

    return {
        'name': result.name,
        'birth_date': result.birth_date,
        'birth_time': result.birth_time,
        'gender': result.gender,
        'is_lunar': result.is_lunar,
        'current_age': result.current_age,

        # 만세력 표기: 시→일→월→년
        'pillars': {
            'si': pillar_dict(result.si_ju),
            'il': pillar_dict(result.il_ju),
            'wol': pillar_dict(result.wol_ju),
            'nyeon': pillar_dict(result.nyeon_ju),
        },
        'pillar_order': ['si', 'il', 'wol', 'nyeon'],

        'ilgan': {
            'index': result.ilgan,
            'name': CHEONGAN[result.ilgan],
            'ohaeng': result.ilgan_ohaeng,
            'is_strong': result.is_strong,
            'strength_label': '신강(身强)' if result.is_strong else '신약(身弱)',
            'strength_detail': result.strength_detail,
        },

        'gyeokguk': gyeokguk,

        'ohaeng': {
            oh: {
                'count': result.ohaeng_count[oh],
                'score': round(result.ohaeng_score[oh], 1),
                'pct': ohaeng_pct[oh],
            }
            for oh in OHAENG
        },

        'sipsin': result.sipsin_map,

        'hapchung': {
            'haps': result.hapchung.haps,
            'chungs': result.hapchung.chungs,
            'pas': result.hapchung.pas,
            'haes': result.hapchung.haes,
        },

        'daewoon': {
            'start_age': result.daewoon_start_age,
            'current': {
                'name': result.current_daewoon.name if result.current_daewoon else '계산 중',
                'name_hanja': result.current_daewoon.name_hanja if result.current_daewoon else '',
                'start_age': result.current_daewoon.start_age if result.current_daewoon else 0,
                'end_age': result.current_daewoon.end_age if result.current_daewoon else 9,
            } if result.current_daewoon else {},
            'list': [
                {
                    'name': dw.name,
                    'name_hanja': dw.name_hanja,
                    'start_age': dw.start_age,
                    'end_age': dw.end_age,
                    'ohaeng': dw.ohaeng,
                    'is_current': dw.is_current,
                    'stem_sipsin': _get_sipsin(ilg, dw.stem),
                    'branch_sipsin': _get_sipsin(ilg, JIJI_BONGI[dw.branch]),
                }
                for dw in result.daewoon_list[:6]  # 현재 기준 앞뒤 포함 6개
            ],
        },

        # 올해(첫 세운년) 월별 간지 + 십신 — 캘린더 섹션용
        'month_pillars': month_pillars,

        'sewoon': {
            'first': {
                'year': result.sewoon_first.year,
                'name': result.sewoon_first.name,
                'name_hanja': result.sewoon_first.name_hanja,
                'stem_kor': CHEONGAN[result.sewoon_first.stem],
                'branch_kor': JIJI[result.sewoon_first.branch],
                'stem_sipsin': sw1_s,
                'branch_sipsin': sw1_b,
            },
            'second': {
                'year': result.sewoon_second.year,
                'name': result.sewoon_second.name,
                'name_hanja': result.sewoon_second.name_hanja,
                'stem_kor': CHEONGAN[result.sewoon_second.stem],
                'branch_kor': JIJI[result.sewoon_second.branch],
                'stem_sipsin': sw2_s,
                'branch_sipsin': sw2_b,
            },
        },
    }
