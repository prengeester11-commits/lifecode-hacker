"""
만세력 정확도 교차검증 스크립트
한국 정통 만세력 기준점들로 계산 정확도 검증
"""
import sys, os, io
# Windows cp949 환경에서도 한글 출력
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date
from saju.calculator import calculate_saju, _get_day_pillar, _get_hour_pillar
from saju.constants import CHEONGAN, JIJI

OK   = '\033[92m✓\033[0m'
FAIL = '\033[91m✗\033[0m'


def pillar_str(stem_idx, branch_idx):
    return CHEONGAN[stem_idx] + JIJI[branch_idx]


def test_day(year, month, day, expected):
    s, b = _get_day_pillar(year, month, day)
    got = pillar_str(s, b)
    ok = got == expected
    mark = OK if ok else FAIL
    print(f"  {mark} {year}-{month:02d}-{day:02d} 일주: {got} (기대: {expected})")
    return ok


def test_full(year, month, day, hour, gender, expected):
    """expected: {'nyeon': '경오', 'wol': '기묘', 'il': '기묘', 'si': '무진'}"""
    r = calculate_saju("검증", year, month, day, hour, 0, gender, False)
    got = {
        'nyeon': r.nyeon_ju.name_kor,
        'wol':   r.wol_ju.name_kor,
        'il':    r.il_ju.name_kor,
        'si':    r.si_ju.name_kor,
    }
    all_ok = True
    print(f"\n[테스트] {year}-{month:02d}-{day:02d} {hour:02d}:00 {gender}")
    for k in ['nyeon', 'wol', 'il', 'si']:
        label = {'nyeon':'년주', 'wol':'월주', 'il':'일주', 'si':'시주'}[k]
        ok = got[k] == expected[k]
        mark = OK if ok else FAIL
        print(f"  {mark} {label}: {got[k]} (기대: {expected[k]})")
        if not ok: all_ok = False
    return all_ok


def test_daewoon(year, month, day, hour, gender, expected_current_age, expected_current_name):
    r = calculate_saju("검증", year, month, day, hour, 0, gender, False)
    cur = r.current_daewoon
    if cur is None:
        print(f"  {FAIL} 현재 대운 계산 안됨")
        return False
    got_name = cur.name
    got_age  = f"{cur.start_age}~{cur.end_age}세"
    ok_name  = got_name == expected_current_name
    ok_age   = cur.start_age <= expected_current_age <= cur.end_age
    mark_n   = OK if ok_name else FAIL
    mark_a   = OK if ok_age  else FAIL
    print(f"  {mark_n} 현재 대운 이름: {got_name} (기대: {expected_current_name})")
    print(f"  {mark_a} 현재 대운 범위: {got_age} (현재 나이 {expected_current_age} 포함되어야 함)")
    return ok_name and ok_age


if __name__ == '__main__':
    print("=" * 60)
    print("  한국 정통 만세력 교차검증")
    print("=" * 60)

    # ── 일주 캘리브레이션 ──
    print("\n[1] 일주 계산 — 알려진 기준점")
    base_ok = all([
        test_day(1900, 1, 1,  "갑술"),
        test_day(2000, 1, 1,  "무오"),
        test_day(1990, 3, 15, "기묘"),
        test_day(1989, 9, 25, "무자"),
    ])

    # ── 전체 사주 — 사용자 제시 케이스 1 ──
    print("\n[2] 사용자 검증 케이스 #1")
    case1_ok = test_full(
        1990, 3, 15, 9, 'M',
        {'nyeon': '경오', 'wol': '기묘', 'il': '기묘', 'si': '무진'}
    )

    # ── 전체 사주 — 사용자 제시 케이스 2 ──
    print("\n[3] 사용자 검증 케이스 #2")
    case2_ok = test_full(
        1989, 9, 25, 20, 'M',
        {'nyeon': '기사', 'wol': '계유', 'il': '무자', 'si': '임술'}
    )

    # ── 대운 검증 ──
    print("\n[4] 대운 계산 — 사용자 검증 케이스 #2")
    print("    (1989년생 남자, 2026년 현재 36~37세)")
    dw_ok = test_daewoon(
        1989, 9, 25, 20, 'M',
        expected_current_age=36,
        expected_current_name='기사',
    )

    # ── 신강/신약 검증 ──
    print("\n[5] 신강/신약 판정 — 한국 정통 만세력 룰 검증")
    print("    1989-09-25 戊子일 酉월 → 월령 실령, 득지 실지 → 신약이어야 함")
    r = calculate_saju("검증", 1989, 9, 25, 20, 0, 'M', False)
    d = r.strength_detail
    print(f"    월령(月令): {'득령' if d['weolryeong'] else '실령'} ({d['score_weolryeong']}점)")
    print(f"    득지(得地): {'득지' if d['deukji'] else '실지'} ({d['score_deukji']}점)")
    print(f"    득세(得勢): {d['score_deukse']}점")
    print(f"    총점: {d['total']}점")
    print(f"    판정: {'신강' if r.is_strong else '신약'}")
    strength_ok = (not r.is_strong)
    print(f"  {OK if strength_ok else FAIL} 기대값: 신약 → {'통과' if strength_ok else '실패'}")

    # ── 종합 ──
    print("\n" + "=" * 60)
    all_pass = base_ok and case1_ok and case2_ok and dw_ok and strength_ok
    if all_pass:
        print("  ✅ 전체 통과 — 만세력 정확도 검증 완료")
    else:
        print("  ❌ 일부 실패 — 위 항목 확인 필요")
    print("=" * 60)
