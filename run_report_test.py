"""
실제 보고서 생성·발송 테스트 스크립트 (결제 단계 제외, 보고서 파이프라인 전체)
app.py의 /api/payment/confirm 2~5단계를 그대로 재현한다.
"""
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from saju.calculator import calculate_saju, saju_to_dict
from ai.interpreter import generate_report_sections, generate_cover_line
from ai.image_gen import generate_persona_image
from email_sender import send_report_email
from app import app, _make_serial_no

# ── 의뢰인 정보 ──
NAME = '브루스리'
EMAIL = 'prengeester11@gmail.com'
YEAR, MONTH, DAY = 1989, 9, 25
HOUR, MINUTE = 20, 30      # 오후 8시 30분 → 술시
GENDER = 'M'
IS_LUNAR = False
CITY = '서울'  # 기질 보강(출생 차트) 테스트

t0 = time.time()
print('[1/5] 만세력 계산...')
saju_result = calculate_saju(
    name=NAME, year=YEAR, month=MONTH, day=DAY,
    hour=HOUR, minute=MINUTE, gender=GENDER, is_lunar=IS_LUNAR,
)
saju_data = saju_to_dict(saju_result)
p = saju_data['pillars']
print('  일간:', saju_data['ilgan']['name'], '/ 신강신약:', saju_data['ilgan'].get('strength_label'))
print('  사주(시일월년):',
      p['si']['name_hanja'], p['il']['name_hanja'],
      p['wol']['name_hanja'], p['nyeon']['name_hanja'])

print('[2/5] AI 13개 섹션 생성 (3~5분 소요)...')
from ai.astro import build_astro_context
astro_context = build_astro_context(YEAR, MONTH, DAY, HOUR, MINUTE, CITY)
print('  기질 보강 컨텍스트:', '생성됨' if astro_context else '없음')
sections = generate_report_sections(saju_data, astro_context=astro_context)
print('  생성된 섹션 수:', len(sections))
for k, v in sections.items():
    print(f'   - {k}: {len(v)}자')

print('[2.5] 사주 상징 이미지 + 표지 헤드라인 생성...')
persona_image = generate_persona_image(saju_data)
print('  이미지:', f'{len(persona_image)} bytes' if persona_image else '실패(없이 진행)')
cover_line = generate_cover_line(saju_data)
print('  표지 헤드라인:', cover_line)

print('[3/5] HTML 렌더링...')
with app.app_context():
    from flask import render_template
    report_date = datetime.now().strftime('%Y년 %m월 %d일')
    serial_no = _make_serial_no(saju_result.name, EMAIL)
    html_content = render_template(
        'report_email.html',
        name=saju_result.name,
        birth_date=saju_result.birth_date,
        birth_time=saju_result.birth_time,
        gender=saju_result.gender,
        report_date=report_date,
        serial_no=serial_no,
        pillars=saju_data['pillars'],
        ilgan=saju_data['ilgan'],
        ohaeng=saju_data['ohaeng'],
        hapchung=saju_data['hapchung'],
        daewoon_list=saju_data['daewoon']['list'],
        sewoon=saju_data['sewoon'],
        sections=sections,
        has_persona_image=bool(persona_image),
        cover_line=cover_line,
    )
print('  HTML 길이:', len(html_content))

# 마크다운 잔여물 검사
print('  literal ## 잔여:', '##' in html_content)
print('  literal ** 잔여:', '**' in html_content)

print('[4/5] 로컬 백업 저장...')
with open('last_report_preview.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print('  저장: last_report_preview.html')

print('[5/5] 이메일 발송 (PDF 첨부 + 표지 이미지 포함)...')
ok = send_report_email(to_email=EMAIL, to_name=NAME, html_content=html_content, image_bytes=persona_image)
print('  발송 결과:', ok)

print(f'완료. 총 소요: {time.time()-t0:.1f}초')
