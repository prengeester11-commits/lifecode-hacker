"""
sample_out/sample_full.png 를 크몽 업로드용 조각 이미지로 분할.
실행: python slice_sample.py
"""
import os
from PIL import Image

BASE = os.path.dirname(__file__)
OUT = os.path.join(BASE, 'sample_out')
SRC = os.path.join(OUT, 'sample_full.png')
SLICE_H = 2600  # 조각 높이(px). device_scale_factor=2 기준 보기 좋은 크기

img = Image.open(SRC).convert('RGB')
w, h = img.size
print(f'원본 크기: {w} x {h}')

# 기존 조각 정리
for f in os.listdir(OUT):
    if f.startswith('sample_page_') and f.endswith('.jpg'):
        os.remove(os.path.join(OUT, f))

n = 0
y = 0
while y < h:
    box = (0, y, w, min(y + SLICE_H, h))
    n += 1
    crop = img.crop(box)
    out = os.path.join(OUT, f'sample_page_{n:02d}.jpg')
    crop.save(out, 'JPEG', quality=88)
    y += SLICE_H

print(f'조각 {n}장 저장 완료 → {OUT}')
