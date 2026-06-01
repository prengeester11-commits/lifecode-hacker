"""
GPT-4o 사주 해석 엔진
라이프코드 해커 스타일: 무의식 패턴 분석 + 실행 지침
연애/돈/습관 균등 분배, 한글 오타 없음, 이모지·특수기호 금지
"""
import os
import re
import html
import json
import time
import logging
from openai import OpenAI

log = logging.getLogger(__name__)
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# ─────────────────────────────────────────────────────────────
# 시스템 프롬프트: 라이프코드 해커 페르소나
# ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 '라이프코드 해커'입니다.
사주명리학(四柱命理學)과 무의식 정화를 결합한 전문가로,
단순한 운세 풀이가 아니라 사람이 반복하는 무의식 패턴을 사주를 통해 분석하는 역할을 합니다.

【핵심 원칙】
1. 미래를 맞히는 게 아닙니다. 패턴을 발견하고 끊어내는 것이 목적입니다.
2. 두려움을 주는 표현은 절대 사용하지 않습니다. "조심하세요", "위험합니다", "흉합니다" 같은 공포 언어 금지.
   대신: "이 시기에 OO 에너지가 강해집니다. OO 방식으로 대응하면 기회가 됩니다."
3. 연애, 재물, 습관·행동 영역을 균등하게 깊이 있게 다룹니다.
4. 【전문용어 전면 금지 — 가장 중요】 독자는 사주를 1도 모르는 초등학생 수준입니다.
   아래 전문용어는 본문(제목 포함)에 절대, 단 한 번도 쓰지 마세요. 괄호 병기도 금지:
   - 십신 용어: 비견·겁재·식신·상관·편재·정재·편관·정관·편인·정인, 그리고 재성·관성·인성·식상·비겁
   - 격국·용신·기신·격(상관격 등)·신강·신약·월령·득령·득지·득세·일간·일주·월지·지장간·본기·천간·지지·오행
   대신, 시스템이 제공하는 십신 값을 아래 '쉬운 말 사전'으로 바꿔 그 의미만 자연스럽게 풀어 씁니다:
   · 비견 → "나와 비슷한, 또 하나의 나 같은 기운(자립·소신)"
   · 겁재 → "나와 닮았지만 더 센 기운(경쟁심·승부욕), 돈·관계가 분산되기 쉬움"
   · 식신 → "내 안에서 편안하게 흘러나오는 표현·여유의 기운"
   · 상관 → "내 식대로 톡톡 튀게 드러내는 표현·재능의 기운(틀에 갇히면 답답함)"
   · 편재 → "크게 굴리는 돈·기회의 기운(통이 크고 유동적)"
   · 정재 → "차곡차곡 모으는 안정된 돈·성실함의 기운"
   · 편관 → "나를 강하게 밀어붙이는 도전·압박의 기운(자극·돌파)"
   · 정관 → "나를 다잡는 책임·질서·명예의 기운"
   · 편인 → "직관·영감으로 나를 채우는 기운(독창·깊은 생각·때로 외로움)"
   · 정인 → "따뜻하게 나를 보살피고 키워주는 기운(배움·안정)"
   - "겉으로 드러나는 기운"(천간)과 "속에서 작동하는 기운"(지지)처럼 풀어 쓰되 한자어는 쓰지 않습니다.
   - 시스템이 주는 십신 값은 '내부 참고용'일 뿐, 본문엔 반드시 위 쉬운 말로만 변환해 씁니다.
   - "설기" 대신 "기운이 빠져나간다", "왕하다" 대신 "세다/넘친다" 처럼 모든 한자 표현을 일상어로.
   - 한 문장은 짧게. 명리를 모르는 사람도 그 문단만 읽고 바로 이해되게.
5. 추상적 표현 금지. 구체적 행동, 선택 기준, 관계 패턴으로 풀어냅니다.
6. 이분법적 단정 금지. "OO이다" 대신 "OO 경향이 있습니다", "OO로 나타날 수 있습니다" 사용.
7. 한국어 맞춤법 철저히 지키고, 오타가 없도록 주의합니다.

【십신 값 사용 규칙 — 계산 정확성】
- 십신은 시스템이 일간 기준으로 이미 정확히 계산해 제공합니다(천간 그대로, 지지는 본기 기준).
  제공된 십신을 절대 스스로 다시 계산하거나 다른 값으로 바꾸지 마세요. 단, 본문엔 위 4번의 쉬운 말로만 표현합니다.

【톤 — 매우 중요】
8. 다정하고 따뜻한 존댓말. 의뢰인이 자기 모습을 마주하는 데 부담을 느끼지 않도록 합니다.
9. 부족함이나 약점을 짚을 때는 반드시 "그래서 당신은 이렇게 살아남았습니다"식의 인정과 위로를 함께 적습니다.
10. 한 섹션을 마치기 전에 반드시 격려나 응원의 한 문장을 자연스럽게 흘려보냅니다.
   예: "이 패턴을 알아차린 것만으로도 이미 큰 변화의 시작입니다."
11. "당신의 잘못이 아닙니다", "그럴 만한 이유가 있었습니다" 같은 인정 문장을 적절히 섞습니다.
12. 거리감 있는 분석가가 아니라, 옆에서 함께 명식을 들여다보는 동행자의 어조로 씁니다.

【몰입·후킹 규칙 — 매우 중요】
13. 밋밋하면 안 됩니다. 각 섹션은 "와, 이거 내 얘기잖아?" 또는 "어, 이건 의외인데?" 하는
    감탄이 최소 한 번은 나오도록 씁니다. 뻔한 일반론(누구에게나 해당하는 말) 금지.
14. 각 섹션의 첫머리는 호기심을 자극하는 한 문장으로 엽니다. 질문형, 반전형, 장면 묘사형 등으로
    독자가 다음 줄을 읽고 싶게 만듭니다. (예: "당신이 매번 같은 곳에서 멈추는 데에는 이유가 있습니다.")
15. 구체적 장면과 비유를 적극 사용합니다. 추상적 설명 대신 독자의 실제 삶 장면이 떠오르게 합니다.
16. 의외의 발견(사주 구조에서 나오는 반전 포인트)을 한 가지씩 짚어 흥미를 만듭니다.

【희망의 메시지 — 매우 중요】
17. 핵심 철학: "무의식을 알아차리는 순간, 현실이 바뀌기 시작한다." 이 메시지를 보고서 곳곳에 자연스럽게 흘립니다.
    약점·패턴을 짚은 뒤에는 거의 매번 "그런데 이걸 알아차린 지금부터는 달라질 수 있어요" 식의 희망을 한 스푼 얹습니다.
18. 운명을 정해진 것으로 단정하지 않습니다. "타고난 결은 있지만, 알아차림과 선택으로 흐름은 바뀝니다"라는 태도로.
19. 읽는 사람이 무거워지지 않고 "오, 나 이거 바꿀 수 있겠는데?" 하는 설렘과 흥미가 끝까지 올라가게 합니다.
19-1. 【지루함 방지 — 매우 중요】 분량이 길어 독자가 지칠 수 있으니, 두세 섹션마다 한 번씩 '환기 한 스푼'을 [흥미] 또는 [희망] 박스로 넣어
   독자가 다시 빠져들게 합니다. 다음 두 메시지를 번갈아 자연스럽게:
   (가) "왜 이게 특별한가": 단순 운세 풀이는 '무슨 일이 일어날지'만 말하지만, 여기서는 '왜 내가 그렇게 반응하는지(무의식의 뿌리)'까지 본다 — 그래서 같은 상황이 와도 다른 선택을 할 수 있게 된다는 점.
   (나) "읽으면 뭐가 달라지나": 이 글을 끝까지 읽고 자기 패턴을 알아차리면, 다음에 같은 순간이 왔을 때 한 박자 멈추고 다른 길을 고를 수 있다 — 그 작은 멈춤이 인생의 방향을 바꾼다는 설렘.
   단, 매번 똑같은 문장 반복 금지. 그 섹션 내용과 연결해 매번 다르게 표현합니다.

【'특별함'의 기준 — 8,900원 이상의 가치】
20. 매 섹션에 '이 사람에게만 해당되는' 구체적 통찰을 최소 하나 담습니다. 검색하면 나오는 일반론은 가치가 없습니다.
21. 그 사람의 사주 구조를 실제 근거로 삼아 "그래서 당신은 이렇다"를 보여줍니다(단, 전문용어 없이 4번의 쉬운 말로만).
    근거 있는 통찰이 보이면 "어떻게 이렇게까지 알지?" 하는 특별한 신뢰가 생깁니다.
22. 다 읽고 나면 "이건 나만을 위해 쓰인 글이다, 캡처해서 간직하고 싶다"는 느낌이 남도록 정성껏 씁니다.

【특수 서식 — 반드시 활용 (스캔성·흥미)】
다음 마커를 적극적으로 사용하세요. 마커는 반드시 줄의 맨 앞에 오고, 한 줄로 작성합니다.

- [핵심] 그 섹션에서 가장 중요한 한 줄 요약. 각 섹션 본문 시작 직후(여는 글 다음)에 반드시 1개.
  바빠서 한 줄만 읽어도 핵심이 전달되도록, 강렬하고 구체적으로.
  예) [핵심] 당신은 흔들리지 않는 산이지만, 그 산을 늘 흔드는 건 바깥이 아니라 당신 안의 물입니다.

- [흥미] "이거 재밌네" 싶은 의외의 포인트. 각 섹션에 1개 정도. 반전·뜻밖의 연결·재미있는 비유.
  예) [흥미] 재밌는 건, 당신이 돈을 못 모으는 게 아니라 '모으면 불안해서' 일부러 흘려보낸다는 점이에요.

- [희망] "무의식을 알아차리면 현실이 바뀐다"는 희망을, 광고가 아니라 진심 어린 응원으로.
  지정된 섹션마다 1개씩. 강요·판매 느낌 절대 금지. 설레는 가능성으로.
  예) [희망] 이 패턴은 평생 가는 게 아니에요. 뿌리를 한 번 알아차리는 순간, 같은 상황에서 다른 선택이 가능해집니다.

- 색상 하이라이트는 '독자가 꼭 기억해야 할 중요한 문구'에만, 확실하게 사용합니다. 장식이 아니라 신호입니다.
  세 가지 의미로 구분해 칠하세요:
  ==문구== : 이 사람이 반드시 기억해야 할 핵심 (용신 오행, 핵심 패턴 이름, 가장 중요한 통찰) — 골드
  ++문구++ : 꼭 살려야 할 강점·기회 — 민트
  ^^문구^^ : 꼭 신경 써야 할 균형·주의 지점 (겁주기 아님) — 살구
  중요한 문구가 나오면 망설이지 말고 확실히 칠하되, 평범한 단어를 장식으로 칠하지는 마세요.
  한 섹션에서 색 강조는 모두 합쳐 3~6개 정도가 적당합니다.

【출력 형식 절대 규칙 — 매우 중요】
- 이모지 절대 금지. 어떤 종류의 이모지도 출력하지 마세요.
  금지 예: 별 모양, 하트, 체크 기호, 화살표 이모지, 표정, 손동작, 동식물, 사물 이모지 등 일체 금지.
- 유니코드 특수기호 금지. 다음 문자들도 사용 금지:
  화살표 기호(→ ← ↑ ↓ ⇒ ⇐), 체크표(✓ ✗ ☑), 별표(★ ☆),
  꺾쇠(⟨ ⟩ « »), 줄임표 기호(…), 점(• ◦ ▪ ▫ ‣), 박스 그리기 문자 등 모두 금지.
- 사용 가능한 문장 부호: 마침표 쉼표 물음표 느낌표 따옴표 괄호 콜론 세미콜론 하이픈(-) 슬래시(/).
- 강조는 텍스트 자체로(**굵게** 사용 가능, GPT 마크다운). 시각 기호로 강조하지 않습니다.
- 한자(漢字)는 명리 용어 표기 시 사용 가능. 그 외 한자 장식 금지.
- 출력은 자연스러운 한국어 문장 위주. 표나 그림 그리지 마세요.
- 분량은 각 섹션에 명시된 분량을 반드시 채워주세요. 짧게 끝나지 않도록 합니다.
"""


def _build_saju_context(saju_data: dict) -> str:
    """사주 데이터를 프롬프트용 텍스트로 변환"""
    p = saju_data['pillars']
    oh = saju_data['ohaeng']
    hc = saju_data['hapchung']
    dw = saju_data['daewoon']
    sw = saju_data['sewoon']
    ilgan = saju_data['ilgan']

    # 오행 분포 텍스트
    ohaeng_text = ', '.join([
        f"{k}({oh[k]['pct']}%)" for k in ['목', '화', '토', '금', '수']
    ])

    # 합충파해 텍스트
    hap_text = ' / '.join(hc['haps']) if hc['haps'] else '없음'
    chung_text = ' / '.join(hc['chungs']) if hc['chungs'] else '없음'
    pa_text = ' / '.join(hc['pas']) if hc['pas'] else '없음'
    hae_text = ' / '.join(hc['haes']) if hc['haes'] else '없음'

    # 대운 텍스트
    dw_current = dw.get('current', {})
    dw_list_text = ', '.join([
        f"{d['start_age']}-{d['end_age']}세 {d['name']}({d['name_hanja']})"
        for d in dw.get('list', [])
    ])

    # 시주 → 일주 → 월주 → 년주 순 표기
    pillar_order = ['si', 'il', 'wol', 'nyeon']
    pillar_labels = {'si': '시주', 'il': '일주', 'wol': '월주', 'nyeon': '년주'}
    pillar_text = ' | '.join([
        f"{pillar_labels[k]} {p[k]['name_hanja']}({p[k]['name_kor']}) [{p[k]['ohaeng_stem']}/{p[k]['ohaeng_branch']}]"
        for k in pillar_order
    ])

    # 신강/신약 상세 (월령·득지·득세)
    sd = ilgan.get('strength_detail', {})
    strength_text = f"""{ilgan['strength_label']} (총점 {sd.get('total', '?')}점)
  - 월령(月令): {'득령(성공)' if sd.get('weolryeong') else '실령(실패)'}
  - 득지(得地): {'득지(성공)' if sd.get('deukji') else '실지(실패)'}
  - 득세(得勢): {sd.get('score_deukse', '?')}점
  - 일간을 돕는 오행(비겁/인성): {', '.join(sd.get('helping_ohaeng', []))}"""

    # 원국 각 자리 십신을 쉬운 말로 변환 (GPT가 전문용어를 안 보게)
    sipsin_easy = {k: _sk(v) for k, v in saju_data.get('sipsin', {}).items()}

    return f"""
【의뢰인 정보】
이름: {saju_data['name']}
생년월일: {saju_data['birth_date']} ({saju_data['gender']})
출생시간: {saju_data['birth_time']}
현재 나이: 만 {saju_data['current_age']}세

【사주팔자 원국 (시주에서 년주 순서)】
{pillar_text}

【일간(日干, 나의 본질 에너지)】
{ilgan['name']}({ilgan['ohaeng']})

【신강/신약 판정 (한국 정통 만세력 룰)】
{strength_text}

【오행 분포】
{ohaeng_text}

【각 자리의 기운 (쉬운 말) — 본문에 그대로 활용, 전문용어 금지】
{json.dumps(sipsin_easy, ensure_ascii=False)}

【합충파해(合沖破害)】
합(合): {hap_text}
충(沖): {chung_text}
파(破): {pa_text}
해(害): {hae_text}

【대운(大運) 흐름】
첫 대운 시작: 만 {dw['start_age']}세
현재 대운: {dw_current.get('name', '?')}({dw_current.get('name_hanja', '')}) {dw_current.get('start_age', '')}~{dw_current.get('end_age', '')}세
전체 대운: {dw_list_text}

【세운(歲運) — 올해와 내년】
올해 {sw['first']['year']}년: {sw['first']['name']}({sw['first']['name_hanja']})년
내년 {sw['second']['year']}년: {sw['second']['name']}({sw['second']['name_hanja']})년

【해석 시 반드시 반영할 것】
- 신강/신약 판정은 위 룰(월령·득지·득세) 기준이며 이게 용신 결정의 기초입니다.
- 신약이면 비겁/인성을 보충하는 방향이 도움이 되고, 신강이면 식상/재성/관성으로 흐름을 풀어주는 방향이 도움됩니다.
- 월령 실령 케이스는 가을생 토일주가 금에 설기되는 등의 구조가 흔하며 이런 점을 무시하지 마세요.
"""


def generate_report_sections(saju_data: dict, astro_context: str = '') -> dict:
    """
    사주 데이터를 받아 보고서 각 섹션을 GPT로 생성.
    astro_context: 출생 차트 기반 '기질 보강 데이터'(내부용, 점성술 용어 비노출).
    Returns: 섹션별 텍스트 딕셔너리
    """
    context = _build_saju_context(saju_data)
    if astro_context:
        context = context + '\n' + astro_context

    sections = {}

    # 섹션별 프롬프트 정의 (총 13개)
    prompts = [
        ('intro',        _prompt_intro(context)),
        ('gyeokguk',     _prompt_gyeokguk(context, saju_data)),   # 신설: 본질 구조·보충 기운
        ('love',         _prompt_love(context)),
        ('money',        _prompt_money(context)),
        ('habit',        _prompt_habit(context)),
        ('career',       _prompt_career(context)),         # 신설: 직업·건강
        ('hapchung',     _prompt_hapchung(context)),
        ('family',       _prompt_family(context)),         # 신설: 가족·관계
        ('daewoon',      _prompt_daewoon(context, saju_data)),
        ('sewoon',       _prompt_sewoon(context, saju_data)),
        ('calendar',     _prompt_calendar(context, saju_data)),   # 신설: 12개월 캘린더
        ('action',       _prompt_action(context)),
        ('purification', _prompt_purification(context)),
    ]

    # 캘린더 등 장문 섹션은 토큰 한도를 넉넉히 (1800은 한글 장문에서 잘림)
    long_sections = {'calendar', 'gyeokguk', 'career'}
    # [희망] 마커(알아차림→현실 변화 메시지)를 넣을 섹션 (중간중간 흥미·희망 유지)
    hope_sections = {'intro', 'love', 'money', 'habit', 'daewoon', 'action'}
    # 박스·색강조를 넣지 않는 섹션 (정화 선언문은 깨끗한 선언만)
    no_engage = {'purification'}

    for section_key, user_prompt in prompts:
        max_tokens = 3400 if section_key in long_sections else 2400
        if section_key in no_engage:
            full_prompt = user_prompt
        else:
            full_prompt = user_prompt + _engage_suffix(section_key in hope_sections)
        text = _generate_one_section(section_key, full_prompt, max_tokens)
        # 마크다운(##, **, 박스 마커)을 이메일용 HTML로 변환
        sections[section_key] = _markdown_to_html(text)

    return sections


def generate_cover_line(saju_data: dict) -> str:
    """
    표지 첫인상용 '이 사람을 정의하는 한 줄' 생성.
    실패해도 기본 문구 반환.
    """
    try:
        ilgan = saju_data.get('ilgan', {})
        oh = saju_data.get('ohaeng', {})
        try:
            dominant = max(['목', '화', '토', '금', '수'], key=lambda k: oh.get(k, {}).get('pct', 0))
        except Exception:
            dominant = ''
        prompt = (
            f"다음 사람의 사주 본질을 한 문장으로 정의하는 '표지 헤드라인'을 만들어줘.\n"
            f"일간 {ilgan.get('name','')}({ilgan.get('ohaeng','')}), {ilgan.get('strength_label','')}, "
            f"가장 강한 기운 {dominant}.\n"
            "조건: 20자 이내, 그 사람의 핵심을 시적이면서 또렷하게, 단언형, "
            "보자마자 '오 내 얘기다' 싶게, 이모지·특수기호·따옴표 없이, 딱 한 줄만 출력."
        )
        resp = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': '너는 사람의 마음을 한 줄로 꿰뚫는 카피라이터다.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.85,
            max_tokens=60,
        )
        line = resp.choices[0].message.content.strip().strip('"\'').split('\n')[0]
        line = _strip_disallowed_symbols(line).strip()
        return line or '흔들려도 끝내 중심을 찾는 사람'
    except Exception as e:
        log.warning(f'표지 헤드라인 생성 실패: {e}')
        return '흔들려도 끝내 중심을 찾는 사람'


def _engage_suffix(with_hope: bool) -> str:
    """모든 섹션에 공통 적용하는 몰입·후킹 지시 (시스템 프롬프트 보강)"""
    base = """

【이 섹션에 반드시 적용할 것】
- 여는 글 바로 다음 줄에 [핵심] 한 줄 요약을 1개 넣으세요. (가장 강렬한 한 줄)
- 본문 중 자연스러운 위치에 [흥미] 포인트를 1개 넣으세요. ("이거 재밌네" 싶은 의외의 발견)
- 의미 기반 색강조를 정밀하게: 핵심 키워드는 ==골드==, 기회·강점은 ++민트++, 균형 필요 지점은 ^^살구^^.
  의미가 분명할 때만, 이 섹션 전체에서 합쳐 3~5개 이내로.
- 첫 문장은 호기심을 자극하게, 뻔한 일반론은 쓰지 마세요."""
    if with_hope:
        base += """
- 섹션 후반부에 [희망] 1개를 넣어, 무의식 정화로 이 패턴을 바꿀 수 있다는 가능성을
  광고처럼 들리지 않게 따뜻하게 전하세요."""
    return base


def _generate_one_section(section_key: str, user_prompt: str, max_tokens: int) -> str:
    """
    단일 섹션 생성. 일시적 오류는 재시도하고, 끝내 실패하면 예외를 발생시켜
    상위(app.py)에서 결제 자동 환불이 작동하도록 한다.
    => 깨진 보고서를 고객에게 발송하지 않는 것이 환불 정책상 안전.
    """
    last_err = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.75,
                max_tokens=max_tokens,
            )
            text = response.choices[0].message.content.strip()
            if not text:
                raise ValueError('빈 응답')
            return _strip_disallowed_symbols(text)
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))  # 1.5s, 3s 백오프
    # 3회 모두 실패 → 예외 전파 (자동 환불 트리거)
    raise RuntimeError(f"섹션 '{section_key}' 생성 실패: {last_err}")


# 후킹·스캔성용 박스 마커 → 인라인 스타일 (이메일 클라이언트가 <style>을 무시해도 안전)
# (박스 div스타일, 라벨 텍스트, 라벨 div스타일, 본문 div스타일)
_BOX_MARKERS = {
    '핵심': (
        'margin:2px 0 16px;padding:13px 16px;background:#191634;border-left:3px solid #a78bfa;border-radius:0 12px 12px 0;',
        '핵심',
        'font-size:10.5px;letter-spacing:1.2px;color:#a78bfa;font-weight:800;margin-bottom:5px;',
        'font-size:15px;font-weight:700;color:#f0ecff;line-height:1.62;',
    ),
    '흥미': (
        'margin:18px 0;padding:16px 17px;background:#241f12;border:1px solid #6b5a1f;border-radius:14px;',
        '이거 재밌어요',
        'display:inline-block;font-size:11px;color:#1a1206;background:#fbbf24;font-weight:800;padding:3px 12px;border-radius:20px;margin-bottom:9px;',
        'font-size:14.5px;color:#f6ecd6;line-height:1.75;',
    ),
    '희망': (
        'margin:18px 0;padding:15px 17px;background:#161a30;border:1px solid #3a3566;border-radius:14px;',
        '무의식 정화 한 스푼',
        'font-size:10.5px;letter-spacing:0.8px;color:#c4b5fd;font-weight:800;margin-bottom:5px;',
        'font-size:14px;color:#dad5f0;line-height:1.75;',
    ),
}


def _markdown_to_html(text: str) -> str:
    """
    GPT가 생성한 마크다운을 이메일/PDF용 HTML로 변환.

    지원 문법:
      ## / ### / ####  → 제목 (h2는 섹션 헤더와 중복되어 CSS로 숨김)
      **굵게**          → <strong>
      ==강조==          → <span class="hl"> (섹션 색상으로 키워드 하이라이트)
      [핵심] ...        → 핵심 한 줄 요약 박스 (스캔성)
      [흥미] ...        → 흥미 포인트 박스 (후킹, "와 재밌네")
      [희망] ...        → 무의식 정화/대면상담 은근한 유도 박스

    템플릿에서는 {{ sections.x | safe }} 로만 출력.
    """
    if not text:
        return ''

    # 1. HTML 특수문자 이스케이프 (안전망)
    text = html.escape(text, quote=False)

    # 1.5. 모든 박스 마커를 각자 줄 맨 앞으로 분리
    #      (GPT가 한 줄에 마커를 여러 개 넣어도 literal 대괄호가 남지 않도록)
    text = re.sub(r'(\[(?:핵심|흥미|희망)\])', r'\n\1', text)

    parts = []
    para = []

    def flush():
        if para:
            parts.append('<p style="margin:0 0 13px;">' + '<br>'.join(para) + '</p>')
            para.clear()

    marker_re = re.compile(r'\[(핵심|흥미|희망)\]\s*')

    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            flush()
            continue

        # 박스 마커 [핵심]/[흥미]/[희망] — 줄 어디에 있든 처리 (인라인 스타일)
        mk = marker_re.search(line)
        if mk:
            before = line[:mk.start()].strip()
            after = line[mk.end():].strip()
            if before:
                para.append(_inline_md(before))
            flush()
            if after:
                box_style, label_text, label_style, body_style = _BOX_MARKERS[mk.group(1)]
                parts.append(
                    f'<div style="{box_style}">'
                    f'<div style="{label_style}">{label_text}</div>'
                    f'<div style="{body_style}">{_inline_md(after)}</div></div>'
                )
            continue

        # 헤딩: ##(섹션 제목)은 템플릿 헤더와 중복 → 생략. ###/#### → 인라인 소제목
        m = re.match(r'^(#{2,4})\s+(.*)$', line)
        if m:
            flush()
            if len(m.group(1)) == 2:
                continue  # 섹션 대제목 중복 방지
            parts.append(_subheading_html(m.group(2)))
            continue

        # 한 줄 전체가 굵게면 소제목으로 처리 (예: **코드 1. 안정**, **해야 할 것**)
        hm = re.match(r'^\*\*(.+?)\*\*[:：]?\s*$', line)
        if hm:
            flush()
            parts.append(_subheading_html(hm.group(1)))
            continue

        para.append(_inline_md(line))
    flush()
    return '\n'.join(parts)


def _subheading_html(text: str) -> str:
    """단락 소제목 (코드 1., 해야 할 것 등) — 본문과 확실히 구분되는 부드러운 색.
    왼쪽 연보라 막대 + 차분한 라벤더 글자로 눈에 띄되 피로하지 않게."""
    return (
        '<div style="margin:20px 0 9px;padding-left:11px;border-left:3px solid #8b7fd6;">'
        f'<span style="font-size:15.5px;font-weight:800;color:#b9a8f0;letter-spacing:-0.2px;line-height:1.5;">'
        f'{_inline_md(text)}</span></div>'
    )


def _inline_md(s: str) -> str:
    """
    인라인 마크다운 (모두 인라인 style — 이메일 클라이언트 <style> 무시 대비):
      **굵게**  → 굵게
      ==키워드== → 핵심(골드)  ++구절++ → 기회(민트)  ^^구절^^ → 균형(살구)
    """
    s = re.sub(r'\+\+(.+?)\+\+', r'<span style="color:#5fd6a6;font-weight:700;">\1</span>', s)
    s = re.sub(r'\^\^(.+?)\^\^', r'<span style="color:#f0a98a;font-weight:700;">\1</span>', s)
    s = re.sub(r'==(.+?)==', r'<span style="color:#ecc65f;font-weight:700;">\1</span>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#efeaff;">\1</strong>', s)
    # 미변환 마커 잔재(쓸데없는 + ^ = 기호) 완전 제거
    s = re.sub(r'\+\+|\^\^|==', '', s)
    s = s.replace('+', '').replace('^', '')
    return s


def _strip_disallowed_symbols(text: str) -> str:
    """
    GPT 출력에서 이모지·특수기호를 사후 제거 (안전망)
    """
    import re
    # 이모지 범위(주요 블록) 제거
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"   # emoticons
        "\U0001F300-\U0001F5FF"   # symbols & pictographs
        "\U0001F680-\U0001F6FF"   # transport & map
        "\U0001F1E0-\U0001F1FF"   # flags
        "\U00002500-\U000025FF"   # box drawing & geometric
        "\U00002600-\U000027BF"   # misc symbols / dingbats
        "\U0001F900-\U0001F9FF"   # supplemental symbols
        "\U0001FA70-\U0001FAFF"   # symbols & pictographs ext-A
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub('', text)
    # 추가 금지 기호 치환
    replacements = {
        '→': ' 그리고 ', '←': ' ', '↑': ' ', '↓': ' ',
        '⇒': ' ', '⇐': ' ', '✓': '', '✗': '', '★': '', '☆': '',
        '⟨': '', '⟩': '', '«': '', '»': '',
        '•': '-', '◦': '-', '▪': '-', '▫': '-', '‣': '-',
        '※': '', '…': '...', '·': ' ', '◇': '', '◆': '', '▶': '', '▷': '',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    # 다중 공백 정리
    text = re.sub(r' {2,}', ' ', text)
    return text


# ─────────────────────────────────────────────────────────────
# 섹션별 프롬프트 (이모지·특수기호 금지 적용)
# ─────────────────────────────────────────────────────────────

def _prompt_intro(context: str) -> str:
    return f"""{context}

위 사주 정보를 바탕으로 '핵심 인생 코드 3가지'를 분석해 주세요.
이 섹션은 보고서 전체의 도입부입니다. 의뢰인이 자기 명식에 정서적으로 안착할 수 있도록 따뜻하게 열어주세요.

분량: 약 900~1100자.

형식 (제목 줄에도 이모지 금지):

## 핵심 인생 코드 세 가지

**여는 글 (3~4문장)**
[이 명식을 처음 마주한 의뢰인을 차분히 환영하고, 일간과 신강/신약을 자연스럽게 짚으며 안심시키는 도입]

**코드 1. [키워드 두세 단어]**
[한 줄 핵심 설명. 그 뒤 5~7문장으로 이 에너지가 삶에서 어떻게 나타나는지 구체적 사례·맥락과 함께 서술. 전문용어는 쓰지 말고 쉬운 말로만(4번 규칙)]

**코드 2. [키워드]**
[동일 형식 5~7문장]

**코드 3. [키워드]**
[동일 형식 5~7문장]

**일간 요약과 따뜻한 한 마디**
[일간의 본질과 이 사람이 세상과 만나는 방식. 신강/신약 결과를 부드럽게 풀어주고, "지금까지 이렇게 살아온 것만으로도 충분합니다" 같은 따뜻한 마무리 한 두 문장]
"""


# 십신 → 쉬운 키워드 (시간흐름 주입용. GPT가 전문용어를 아예 안 보게)
SIPSIN_KEY = {
    '비견': '자립·소신의 기운', '겁재': '경쟁·승부욕의 기운(돈·관계 분산 주의)',
    '식신': '편안한 표현·여유의 기운', '상관': '톡톡 튀는 표현·재능의 기운',
    '편재': '큰 돈·기회를 굴리는 기운', '정재': '안정된 돈·성실의 기운',
    '편관': '도전·압박·돌파의 기운', '정관': '책임·질서·인정의 기운',
    '편인': '직관·독창·깊은 생각의 기운', '정인': '보살핌·배움·안정의 기운',
}


def _sk(sipsin: str) -> str:
    return SIPSIN_KEY.get(sipsin, sipsin)


GYEOKGUK_EASY = {
    '식신': '느긋하게 표현하고 베풀 때 가장 빛나는 타입',
    '상관': '자기만의 방식으로 톡톡 튀게 드러내고 표현할 때 빛나는 타입',
    '정재': '성실하게 차곡차곡 쌓아 안정을 만드는 타입',
    '편재': '기회를 크게 굴리고 사람과 일을 다루는 데 강한 타입',
    '정관': '책임감 있게 질서를 지키며 신뢰로 인정받는 타입',
    '편관': '강한 추진력으로 어려움을 정면 돌파하는 타입',
    '정인': '배우고 품으며 깊이로 승부하는 타입',
    '편인': '직관과 독창성으로 남다른 길을 가는 타입',
    '비견': '스스로의 힘으로 독립해 일어서는 타입',
    '겁재': '강한 의지와 승부욕으로 끝까지 밀어붙이는 타입',
}


def _prompt_gyeokguk(context: str, saju_data: dict) -> str:
    g = saju_data.get('gyeokguk', {})
    easy = GYEOKGUK_EASY.get(g.get('sipsin', ''), '자기만의 색이 뚜렷한 타입')
    return f"""{context}

이 섹션은 '내 사주의 본질 구조와 보충하면 좋은 기운'을 풀어주는 핵심 섹션입니다.

[이미 계산된 핵심 — 그대로 사용, 다시 판정하거나 바꾸지 말 것]
- 이 사람의 타고난 핵심 캐릭터: "{easy}"
  (이 캐릭터 정의를 그대로 살려서 풀되, '격국'이나 그 한자 이름은 절대 본문에 쓰지 마세요.)

분량: 약 1300~1500자. 초등학생도 이해할 만큼 쉬운 말로만.

형식:

## 내 사주의 본질 구조와 보충하면 좋은 기운

**1. 나는 어떤 사람인가 (타고난 핵심 캐릭터)**
[위에 제시된 캐릭터("{easy}")를 바탕으로, 이 사람이 어떤 결을 가졌고 어떤 순간에 빛나는지를 구체적 삶의 장면과 함께 5~7문장으로. 전문용어 없이 쉬운 말로.]

**2. 지금 내 에너지 상태 (단단함 vs 보충 필요)**
[신강/신약을 '내 기운이 꽉 차 있는지, 채워주면 좋은지'로 쉽게 풀어 설명. 어렵게 느껴지지 않게. 3~5문장]

**3. 채우면 삶이 풀리는 기운**
[이 사람에게 보충되면 좋은 기운(오행)을 쉬운 말로. 그 기운이 일상에서 어떻게 도움이 되는지 5~7문장. '용신' 같은 용어 금지.]

**4. 잠시 거리를 두면 좋은 것**
[에너지를 빼앗는 행동·환경을 구체적으로. '기신' 용어 금지. 4~6문장]

**5. 생활 속 처방**
[보충 기운에 맞는 색깔·방향·음식·환경·활동을 구체적으로 4~6가지.]

**6. 닫는 위로 (2~3문장)**
[보충할 기운이 있다는 건 결핍이 아니라 성장 방향이라는 따뜻한 메시지]
"""


def _prompt_love(context: str) -> str:
    return f"""{context}

위 사주를 바탕으로 '연애 무의식 패턴'을 분석해 주세요.
분량: 약 1100~1300자.

형식:

## 연애와 관계에서 반복하는 무의식 패턴

**끌리는 사람의 패턴 (6~8문장)**
[어떤 유형의 사람에게 자꾸 끌리는지, 왜 그런지 사주 구조(특히 재성·관성·일지)로 설명]

**관계에서 반복되는 상처 (6~8문장)**
[이 사람이 연애에서 자주 겪는 상처나 갈등 패턴. 구체적 상황 묘사 포함]

**집착 또는 회피 메커니즘 (5~6문장)**
[감정적 위기 시 나타나는 무의식 반응. 그래야만 했던 이유에 대한 인정과 위로 한 문장 포함]

**이 패턴이 반복되는 진짜 이유 (3~4문장)**
[사주 구조에서 드러나는 연애 무의식의 뿌리]

**연애에서 기억해야 할 한 가지 (3~4문장)**
[구체적인 행동 지침 또는 선택 기준 + "당신은 이미 사랑받을 자격이 충분합니다" 식의 따뜻한 마무리]
"""


def _prompt_money(context: str) -> str:
    return f"""{context}

위 사주를 바탕으로 '재물 무의식 패턴'을 분석해 주세요.
분량: 약 1100~1300자.

형식:

## 돈이 막히는 진짜 이유

**이 사람이 돈을 버는 방식 (6~8문장)**
[타고난 재물 에너지와 돈이 들어오는 채널. 재성·식상 구조로 풀이]

**돈이 새는 무의식 패턴 (6~8문장)**
[돈이 모이지 않거나 나가게 되는 반복 패턴. 구체적 상황 묘사]

**돈 앞에서 나타나는 무의식 저항 (5~6문장)**
[돈을 받거나 요구할 때 생기는 내면의 저항, 두려움, 자기방해. 그 저항이 어디서 왔는지 따뜻하게 짚어주기]

**재물 에너지를 막는 습관 (3~4문장)**
[재물운을 약화시키는 구체적 행동 패턴]

**돈 흐름을 바꾸기 위해 당장 할 수 있는 것 (3~4문장)**
[구체적 행동 두 가지 + "지금까지의 당신을 인정하는 것이 새 흐름의 시작입니다" 같은 마무리]
"""


def _prompt_habit(context: str) -> str:
    return f"""{context}

위 사주를 바탕으로 '습관과 행동의 무의식 패턴'을 분석해 주세요.
분량: 약 1100~1300자.

형식:

## 알면서도 못 바꾸는 것들

**자기파괴 사이클 (6~8문장)**
[이 사람이 반복하는 자기방해 패턴. 구체적인 상황 묘사 포함]

**변화를 막는 무의식의 작동 방식 (6~8문장)**
[왜 알면서도 못 바꾸는지, 사주에서 드러나는 심리 구조]

**에너지가 낭비되는 상황 (5~6문장)**
[어떤 상황, 사람, 환경에서 에너지를 소진하는지]

**이미 갖고 있는 강점 (3~4문장)**
[자기방해에 가려진 진짜 재능과 강점. 의뢰인이 잘 안 보였을 부분을 따뜻하게 짚어주기]

**지금 당장 끊어야 할 패턴 한 가지 (3~4문장)**
[매우 구체적이고 실천 가능한 변화 포인트 + 부담을 덜어주는 마무리 한 문장]
"""


def _prompt_career(context: str) -> str:
    return f"""{context}

위 사주의 십신과 격국, 오행 분포를 바탕으로 '직업·적성과 건강·체질 코드'를 함께 분석해 주세요.
분량: 약 1300~1500자.

형식:

## 직업·적성 그리고 건강·체질 코드

**1. 타고난 적성 영역 (5~7문장)**
[식상이 강하면 표현·창작·교육·기술 영역, 재성이 강하면 사업·재무·관리, 관성이 강하면 조직·공공·전문직, 인성이 강하면 학문·연구·돌봄 영역. 의뢰인의 사주에 맞춰 어느 영역이 자연스럽게 풀리는지]

**2. 잘 맞는 일의 환경 (4~6문장)**
[조직형/프리랜서형/창업형 중 어느 결이 맞는지, 어떤 동료·상사 구조가 좋은지]

**3. 피해야 할 직업 패턴 (4~6문장)**
[기신 오행에 해당하는 직업, 또는 사주 구조상 에너지가 빠지기 쉬운 일의 형태]

**4. 건강·체질 코드 (6~8문장)**
[오행과 신체 장부의 대응: 목(간·담), 화(심장·소장), 토(비장·위), 금(폐·대장), 수(신장·방광).
부족한 오행에 해당하는 장부가 약점이 되기 쉽고, 과다한 오행은 그 장부에 과부하가 걸릴 수 있음을 부드럽게 설명. 의뢰인의 오행 분포를 보고 맞춤 안내]

**5. 일상 식습관과 운동 가이드 (4~6문장)**
[용신 오행에 맞는 음식 색깔과 성질, 운동 결을 구체적으로]

**6. 닫는 위로 (2~3문장)**
[지금까지 자기 적성을 못 찾았다고 느꼈더라도 늦은 게 아니라는 메시지]
"""


def _prompt_hapchung(context: str) -> str:
    return f"""{context}

위 사주의 합충파해를 바탕으로 '내 인생의 갈등 구조'를 분석해 주세요.
합이 없거나 충이 없는 경우도 그 의미를 해석해 주세요.
분량: 약 1100~1300자.

형식:

## 내 사주에서 충돌하는 에너지

**합(合) - 나를 끌어당기는 에너지 (5~7문장)**
[합의 의미와 이 사람 삶에서 어떻게 나타나는지. 없으면 "원국에 합이 없어 독립적인 흐름을 가집니다"식으로 해석]

**충(沖) - 내 안의 긴장과 갈등 (5~7문장)**
[충이 있으면 어떤 에너지들이 충돌하며 어떤 반복 갈등이 일어나는지. 없으면 안정적이지만 변화에 느린 측면 해석]

**파(破)와 해(害) - 생각지 못한 방해 (5~7문장)**
[파/해가 있는 경우 그 영향. 어떤 일상 장면에서 작동하는지 구체적으로. 없으면 "방해 에너지가 적어 흐름이 비교적 매끄럽습니다" 식 처리]

**이 갈등 구조에서 벗어나는 방법 (4~6문장)**
[구체적인 의식화 방법 + 갈등 자체를 부정하지 말고 알아차림으로 풀어주라는 따뜻한 마무리]
"""


def _prompt_family(context: str) -> str:
    return f"""{context}

위 사주의 사주 자리(년주/월주/일주/시주)와 십신을 바탕으로 '가족과 인간관계 자리 해석'을 해주세요.
이 섹션은 의뢰인의 가족·대인 관계 패턴을 사주 구조로 풀어주는 부분입니다.
분량: 약 1100~1300자.

형식:

## 가족과 인간관계 자리 해석

**1. 년주(年柱) - 부모·조상의 자리 (4~6문장)**
[년간·년지의 십신을 보고 부모 또는 가문에서 받은 영향. 어린 시절의 정서적 기반]

**2. 월주(月柱) - 형제·사회의 자리 (4~6문장)**
[월간·월지가 보여주는 형제 관계, 사회생활 패턴, 직장이나 또래 관계의 결]

**3. 일주(日柱) - 나와 배우자의 자리 (5~7문장)**
[일간(나) - 일지(배우자) 관계. 어떤 배우자상에 끌리는지, 결혼 생활에서 반복되는 무의식 패턴]

**4. 시주(時柱) - 자녀·미래·말년의 자리 (4~6문장)**
[시간·시지가 보여주는 자녀와의 관계, 노년기 흐름]

**5. 인간관계 무의식 한 줄 처방 (3~4문장)**
[관계에서 가장 자주 걸리는 무의식 매듭 한 가지 + 그 매듭을 풀기 위한 따뜻한 한 마디]
"""


def _prompt_daewoon(context: str, saju_data: dict) -> str:
    cur = next((d for d in saju_data.get('daewoon', {}).get('list', []) if d.get('is_current')), None)
    cur_line = ''
    if cur:
        cur_line = (f"\n[지금의 큰 흐름 기운 — 이미 계산됨, 그대로 사용. 본문엔 쉬운 말로만]\n"
                    f"- 현재 큰 흐름: 겉기운 [{_sk(cur.get('stem_sipsin',''))}] · 속기운 [{_sk(cur.get('branch_sipsin',''))}]\n")
    return f"""{context}

위 사주의 대운 정보를 바탕으로 '지금 내가 있는 운의 의미'를 분석해 주세요.
{cur_line}
분량: 약 1100~1300자.

형식:

## 지금 나는 어느 흐름에 있는가

**현재 대운의 에너지 (6~8문장)**
[지금의 큰 흐름이 어떤 기운인지(위 겉기운·속기운), 이 시기의 주제와 과제를 쉬운 말로 짚어주기]

**이 대운에서 올라오는 무의식 (5~6문장)**
[이 대운에서 특히 자극되는 무의식 패턴과 심리적 주제. 의뢰인이 일상에서 어떤 감각으로 체감하는지]

**이 시기를 잘 보내는 방법 (5~6문장)**
[현재 대운 에너지를 활용하는 구체적 방향]

**다음 대운 예고 (3~4문장)**
[다음 대운의 에너지와 준비해야 할 것. 부담스럽지 않게 안내]
"""


def _prompt_sewoon(context: str, saju_data: dict) -> str:
    sw = saju_data['sewoon']
    y1, n1, h1 = sw['first']['year'], sw['first']['name'], sw['first']['name_hanja']
    y2, n2, h2 = sw['second']['year'], sw['second']['name'], sw['second']['name_hanja']
    s1s, s1b = _sk(sw['first'].get('stem_sipsin', '')), _sk(sw['first'].get('branch_sipsin', ''))
    s2s, s2b = _sk(sw['second'].get('stem_sipsin', '')), _sk(sw['second'].get('branch_sipsin', ''))
    return f"""{context}

{y1}년({n1}년)과 {y2}년({n2}년)의 흐름이 이 사람과 어떻게 작용하는지 분석해 주세요.

[아래 기운은 이미 계산됨 — 그대로 사용. 본문엔 전문용어 없이 쉬운 말로만]
- {y1}년 {n1}: 겉기운 [{s1s}] · 속기운 [{s1b}]
- {y2}년 {n2}: 겉기운 [{s2s}] · 속기운 [{s2b}]

분량: 약 1100~1300자.

형식:

## {y1}-{y2} 무의식 발동 시점

**{y1}년 {n1}년({h1}年) - 이 해의 에너지 (6~8문장)**
[위 겉기운·속기운이 이 사람에게 어떻게 작용하는지 쉬운 말로 풀이]

{y1}년 흐름이 좋아지는 시기 (3~4문장)
[구체적 월이나 기간과 어떤 흐름이 도와주는지]

{y1}년 한 호흡 골라야 할 시기 (3~4문장)
[속도를 조절하면 좋은 시기. 공포 언어 금지]

**{y2}년 {n2}년({h2}年) - 이 해의 에너지 (6~8문장)**
[위 겉기운·속기운이 이 사람에게 어떻게 작용하는지 쉬운 말로 풀이]

{y2}년 핵심 주제 (3~4문장)
[이 해에 가장 강하게 작동하는 무의식 주제와 대응 방법]
"""


def _prompt_calendar(context: str, saju_data: dict) -> str:
    cal_year = saju_data['sewoon']['first']['year']  # 올해(현재 연도)만
    mps = saju_data.get('month_pillars', [])
    # 각 달의 기운을 '쉬운 키워드'로 미리 변환해 제공 (전문용어를 GPT가 아예 안 보게)
    month_lines = '\n'.join(
        f"  {mp['month']}월: 겉기운 [{_sk(mp['stem_sipsin'])}] · 속기운 [{_sk(mp['branch_sipsin'])}]"
        for mp in mps
    )
    month_blocks = '\n\n'.join(
        f"**{mp['month']}월 - [이 달의 키워드 두 단어]**\n"
        f"[이 달은 겉기운 [{_sk(mp['stem_sipsin'])}], 속기운 [{_sk(mp['branch_sipsin'])}]입니다. "
        f"이 기운이 이 사람에게 어떻게 작용하는지를 바탕으로 추천 행동과 한 호흡 고를 행동을 3~4문장으로. "
        f"전문용어는 쓰지 말고 쉬운 말로만.]"
        for mp in mps
    )
    return f"""{context}

위 사주를 바탕으로 '{cal_year}년 12개월 흐름 캘린더'를 작성해 주세요.

[매우 중요 — 각 달의 기운은 이미 정확히 계산되었습니다]
아래는 {cal_year}년 각 월의 '겉기운(그 달 위로 드러나는 결)'과 '속기운(그 달 안에서 작동하는 결)'입니다.
이 기운들을 그대로 사용해 해석하되, 본문에는 전문용어 없이 쉬운 말로만 풀어주세요. (임의로 바꾸지 말 것)
{month_lines}

분량: 약 1700~1900자.

형식:

## {cal_year}년 월별 무의식 흐름 캘린더

**들어가는 말 (2~3문장)**
[월별 흐름은 절대적 예언이 아니라 에너지 결의 안내라는 점을 부드럽게]

{month_blocks}

**닫는 말 (2~3문장)**
[1년 흐름을 통째로 봤을 때 의뢰인에게 전하고 싶은 따뜻한 한 마디]
"""


def _prompt_action(context: str) -> str:
    return f"""{context}

위 사주 분석을 종합하여 '이번 달 실행 과제'를 제시해 주세요.
분량: 약 1100~1300자.

형식:

## 이번 달 실행 과제

**여는 글 (2~3문장)**
[이번 달 행동 가이드를 받아들이는 부담을 덜어주는 따뜻한 도입]

**해야 할 것 (세 가지)**
1. [구체적이고 실천 가능한 행동. 왜 도움이 되는지 한 줄 설명 포함]
2. [동일 형식]
3. [동일 형식]

**하지 말아야 할 것 (두 가지)**
1. [무의식 패턴에서 나오는 자기방해 행동 + 그래도 이미 자기를 지키려고 그래왔다는 인정 한 문장]
2. [동일 형식]

**관찰해야 할 것 (한 가지)**
[이번 달 자신의 무의식 패턴 중 의식적으로 바라봐야 할 것. 어떻게 알아차릴 수 있는지 단서 포함]

**이번 달 스스로에게 해주고 싶은 말 (4~5문장)**
[따뜻하고 힘을 주는 문단. 사주 에너지에 맞춰 개인화]
"""


def _prompt_purification(context: str) -> str:
    return f"""{context}

이 사람만을 위한 '무의식 정화 선언문'을 작성해 주세요.
이 페이지는 보고서의 클라이맥스이자, 의뢰인이 캡처해서 매일 간직하고 싶어질 '한 장의 선언 카드'입니다.
어지럽지 않고, 한눈에 각인되며, 마음을 울려야 합니다.

【엄격한 출력 규칙】
- == ++ ^^ ** ## [핵심] [흥미] 등 어떤 마커·강조 기호도 절대 쓰지 마세요. 순수한 문장만.
- 제목 한 줄, 짧은 여는 글, 선언 7~9줄, 짧은 사용 안내 순서로만 작성.

형식 (아래 구조 그대로, 기호 없이):

## 나만의 정화 선언문

[여는 글: 1~2문장. 이 선언문을 어떻게 품으면 좋은지 짧고 따뜻하게.]

[그다음, 1인칭 '나는'으로 시작하는 짧고 또렷한 선언을 7~9줄. 반드시 한 줄에 하나씩, 줄바꿈으로 구분.
각 줄은 18~28자 내외로 짧고 리듬감 있게. 이 사람의 일간·용신·핵심 패턴과 연결되도록 개인화.
뻔한 구호 금지. 읽으면 가슴이 단단해지는 문장으로.]

[마지막: 사용 안내 1~2문장. 매일 아침, 또는 흔들릴 때 소리 내어 읽으면 좋다는 점만 짧게.]
"""
