"""
sample_report.html → 크몽 업로드용 이미지/ PDF 변환.
Playwright(크롬 엔진)로 실제 렌더링하여 화질 손실 없이 저장한다.

생성물 (sample_out/ 폴더):
  - sample_full.png      : 보고서 전체 한 장 (긴 세로 이미지)
  - sample.pdf           : 보고서 전체 PDF (다운로드/인쇄용)
  - sample_page_01.jpg.. : 업로드하기 좋게 잘라낸 조각 이미지들

실행: python render_sample.py
"""
import os
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(__file__)
SRC = os.path.join(BASE, 'static', 'sample_report.html')
OUT = os.path.join(BASE, 'sample_out')
WIDTH = 820          # 보고서 본문 폭에 맞춘 뷰포트
SLICE_H = 1400       # 조각 이미지 한 장 높이(px)


def main():
    os.makedirs(OUT, exist_ok=True)
    url = 'file:///' + SRC.replace('\\', '/')

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': WIDTH, 'height': 1200},
                                device_scale_factor=2)
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(1500)

        total_h = page.evaluate('document.body.scrollHeight')
        print(f'페이지 높이: {total_h}px')

        # 1) 전체 한 장 PNG
        full_png = os.path.join(OUT, 'sample_full.png')
        page.screenshot(path=full_png, full_page=True)
        print(f'저장: {full_png}')

        # 2) 전체 PDF
        pdf_path = os.path.join(OUT, 'sample.pdf')
        page.pdf(path=pdf_path, width=f'{WIDTH}px',
                 height=f'{total_h}px', print_background=True)
        print(f'저장: {pdf_path}')

        # 3) 업로드용 조각 JPG (세로로 SLICE_H 씩)
        n = 0
        y = 0
        while y < total_h:
            h = min(SLICE_H, total_h - y)
            n += 1
            clip = {'x': 0, 'y': y, 'width': WIDTH, 'height': h}
            out = os.path.join(OUT, f'sample_page_{n:02d}.jpg')
            page.screenshot(path=out, clip=clip, type='jpeg', quality=90)
            y += SLICE_H
        print(f'조각 이미지 {n}장 저장 완료')

        browser.close()
    print(f'\n완료. 결과 폴더: {OUT}')


if __name__ == '__main__':
    main()
