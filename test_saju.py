"""
사주 명식 테스트 스크립트
결제/API 없이 만세력 계산 결과를 바로 확인합니다.

사용법:
  python test_saju.py               → 기본 예제 3개 출력
  python test_saju.py 1990 3 15 13 M  → 직접 입력 (년 월 일 시 성별)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from saju.calculator import calculate_saju, saju_to_dict

# ── ANSI 색상 ──
R  = '\033[91m'   # 빨강 (火)
G  = '\033[92m'   # 초록 (木)
Y  = '\033[93m'   # 노랑 (土)
B  = '\033[94m'   # 파랑 (水)
M  = '\033[95m'   # 마젠타 (金)
C  = '\033[96m'   # 시안
W  = '\033[97m'   # 흰색
DIM= '\033[2m'
END= '\033[0m'
BOLD='\033[1m'

OHAENG_COLOR = {'목': G, '화': R, '토': Y, '금': M, '수': B}


def color_oh(text, ohaeng):
    c = OHAENG_COLOR.get(ohaeng, W)
    return f"{c}{text}{END}"


def print_result(saju_data: dict):
    p = saju_data['pillars']
    order = ['si', 'il', 'wol', 'nyeon']
    labels = {'si': '시주', 'il': '일주', 'wol': '월주', 'nyeon': '년주'}

    print()
    print(f"{BOLD}{C}{'─'*52}{END}")
    print(f"{BOLD}  {saju_data['name']}  |  {saju_data['birth_date']}  {saju_data['birth_time']}  |  {saju_data['gender']}{END}")
    print(f"{C}{'─'*52}{END}")

    # ── 사주 원국 표 (시→일→월→년) ──
    header = f"  {'':4}"
    stem_row  = f"  {'천간':4}"
    branch_row= f"  {'지지':4}"
    oh_row    = f"  {'오행':4}"

    for key in order:
        pp = p[key]
        lbl = labels[key]
        oh_s = pp['ohaeng_stem']
        oh_b = pp['ohaeng_branch']
        cs = OHAENG_COLOR.get(oh_s, W)
        cb = OHAENG_COLOR.get(oh_b, W)
        header     += f"  {BOLD}{lbl:^6}{END}"
        stem_row   += f"  {cs}{pp['stem_hanja']}({pp['stem_kor']}){END}  "
        branch_row += f"  {cb}{pp['branch_hanja']}({pp['branch_kor']}){END}  "
        oh_row     += f"  {cs}{oh_s}{END}/{cb}{oh_b}{END}     "

    print(header)
    print(f"  {'─'*46}")
    print(stem_row)
    print(branch_row)
    print(oh_row)
    print(f"  {'─'*46}")

    # ── 일간 ──
    ig = saju_data['ilgan']
    strength = f"{'신강(身强) 💪' if ig['is_strong'] else '신약(身弱) 🌱'}"
    print(f"\n  {BOLD}일간{END}: {color_oh(ig['name'], ig['ohaeng'])} ({ig['ohaeng']})   {strength}")

    # ── 오행 분포 ──
    print(f"\n  {BOLD}오행 분포{END}")
    ohaeng_names = ['목', '화', '토', '금', '수']
    for oh in ohaeng_names:
        d = saju_data['ohaeng'][oh]
        pct = d['pct']
        bar_len = pct // 5
        bar = '█' * bar_len + '░' * (20 - bar_len)
        c = OHAENG_COLOR.get(oh, W)
        print(f"  {c}{oh}{END}  {c}{bar}{END}  {pct:2d}%  ({d['score']}점)")

    # ── 합충파해 ──
    hc = saju_data['hapchung']
    if any([hc['haps'], hc['chungs'], hc['pas'], hc['haes']]):
        print(f"\n  {BOLD}합충파해{END}")
        if hc['haps']:   print(f"  {G}합 :{END} {', '.join(hc['haps'])}")
        if hc['chungs']: print(f"  {R}충 :{END} {', '.join(hc['chungs'])}")
        if hc['pas']:    print(f"  {Y}파 :{END} {', '.join(hc['pas'])}")
        if hc['haes']:   print(f"  {M}해 :{END} {', '.join(hc['haes'])}")
    else:
        print(f"\n  {DIM}합충파해 없음{END}")

    # ── 대운 ──
    dw = saju_data['daewoon']
    print(f"\n  {BOLD}대운{END}  (시작 나이: {dw['start_age']}세)")
    for d in dw['list']:
        cur = f" {R}◀ 현재{END}" if d['is_current'] else ""
        oh = d.get('ohaeng', '')
        c = OHAENG_COLOR.get(oh, W)
        print(f"  {d['start_age']:2d}~{d['end_age']:2d}세  {c}{d['name_hanja']}({d['name']}){END}{cur}")

    # ── 세운 ──
    sw = saju_data['sewoon']
    print(f"\n  {BOLD}세운{END}")
    print(f"  2025년  {sw['2025']['name_hanja']}({sw['2025']['name']})   {DIM}을사년{END}")
    print(f"  2026년  {sw['2026']['name_hanja']}({sw['2026']['name']})   {DIM}병오년{END}")

    print(f"\n{C}{'─'*52}{END}")
    print()


def run_test(name, year, month, day, hour, gender, is_lunar=False, label=""):
    if label:
        print(f"\n{BOLD}{W}[ 테스트: {label} ]{END}")
    try:
        result = calculate_saju(name, year, month, day, hour, 0, gender, is_lunar)
        data = saju_to_dict(result)
        print_result(data)
    except Exception as e:
        print(f"{R}오류: {e}{END}")
        import traceback; traceback.print_exc()


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

if __name__ == '__main__':
    args = sys.argv[1:]

    if args:
        # 직접 입력 모드: python test_saju.py 1990 3 15 13 M [음력]
        if len(args) < 5:
            print("사용법: python test_saju.py 년 월 일 시(0-23) 성별(M/F) [음력:true]")
            print("예시 : python test_saju.py 1990 3 15 13 M")
            sys.exit(1)
        y, mo, d, h = int(args[0]), int(args[1]), int(args[2]), int(args[3])
        g = args[4].upper()
        lunar = len(args) > 5 and args[5].lower() == 'true'
        run_test("테스트", y, mo, d, h, g, lunar, f"{y}년 {mo}월 {d}일 {h}시 {'음력' if lunar else '양력'}")

    else:
        print(f"\n{BOLD}{C}=== 라이프코더 해커 — 만세력 테스트 ==={END}")
        print(f"{DIM}아래 예시 3개로 계산이 제대로 되는지 확인합니다.{END}")

        # ── 검증용: 1984-02-04 = 丁亥日 (day_offset 캘리브레이션 기준) ──
        run_test(
            "캘리브레이션", 1984, 2, 4, 9, 'M',
            label="1984-02-04 (정해일 검증 — 시주가 壬巳여야 함)"
        )

        # ── 2000년생 여성 오전 ──
        run_test(
            "테스트A", 2000, 5, 20, 10, 'F',
            label="2000년 5월 20일 오전 10시 여성 (경진년·오월·무오일·갑오시)"
        )

        # ── 1990년생 남성 야간 ──
        run_test(
            "테스트B", 1990, 11, 3, 23, 'M',
            label="1990년 11월 3일 23시 남성 (경오년·술월)"
        )

        print(f"\n{DIM}직접 테스트: python test_saju.py 1995 8 15 14 F{END}\n")
