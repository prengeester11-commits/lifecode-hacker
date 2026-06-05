"""
크몽 입점용 '샘플 보고서' 생성 스크립트 (개인정보 없음, 가상 인물).
실제 발송 파이프라인과 동일하게 생성하되, 이메일 대신 독립 HTML 파일로 저장한다.
이미지는 cid 대신 data:URI로 박아넣어 브라우저에서 바로 열린다.

실행: python make_sample.py
결과: static/sample_report.html
"""
import os
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app import app  # Flask app (render_template 컨텍스트용)
from saju.calculator import calculate_saju, saju_to_dict
from ai.interpreter import generate_report_sections, generate_cover_line
from ai.image_gen import generate_persona_image
from flask import render_template

# ── 가상 인물 (개인정보 아님) ──
SAMPLE = {
    'name': '홍길동',
    'email': 'sample@lifecode.kr',
    'year': 1990, 'month': 5, 'day': 15,
    'hour': 14, 'minute': 0,
    'gender': 'M',  # 계산기는 'M'/'F' 형식을 받음 (프론트와 동일)
    'is_lunar': False,
    'city': '',
}


def main():
    print('[1/5] 만세력 계산...')
    saju_result = calculate_saju(
        name=SAMPLE['name'], year=SAMPLE['year'], month=SAMPLE['month'],
        day=SAMPLE['day'], hour=SAMPLE['hour'], minute=SAMPLE['minute'],
        gender=SAMPLE['gender'], is_lunar=SAMPLE['is_lunar'],
    )
    saju_data = saju_to_dict(saju_result)

    print('[2/5] GPT 보고서 13개 섹션 생성 (1~2분 소요)...')
    sections = generate_report_sections(saju_data, astro_context='')

    print('[3/5] 상징 이미지 + 표지 헤드라인 생성...')
    persona_image = generate_persona_image(saju_data)
    cover_line = generate_cover_line(saju_data)

    print('[4/5] HTML 렌더링...')
    report_date = datetime.now().strftime('%Y년 %m월 %d일')
    with app.app_context():
        html_content = render_template(
            'report_email.html',
            name=saju_result.name,
            birth_date=saju_result.birth_date,
            birth_time=saju_result.birth_time,
            gender=saju_result.gender,
            report_date=report_date,
            serial_no='LH-SAMPLE-0000',
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

    # cid:persona → data:URI 치환 (브라우저에서 바로 보이도록)
    if persona_image:
        data_uri = 'data:image/jpeg;base64,' + base64.b64encode(persona_image).decode()
        html_content = html_content.replace('cid:persona', data_uri)

    print('[5/5] 파일 저장...')
    out_dir = os.path.join(os.path.dirname(__file__), 'static')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'sample_report.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f'완료: {out_path}')


if __name__ == '__main__':
    main()
