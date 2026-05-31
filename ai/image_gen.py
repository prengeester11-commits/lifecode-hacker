"""
사주 기반 '그 사람을 상징하는' 프리미엄 이미지 생성 (gpt-image-1)

일간 오행을 중심 모티프로, 가장 강한 오행을 보조 모티프로,
신강/신약을 분위기로 삼아 수묵화풍의 고급 상징 이미지를 만든다.
사람·글자 없이 자연 상징으로 표현해 '선물' 같은 표지 이미지를 연출.

실패해도 None을 반환 — 보고서 발송은 정상 진행(graceful degradation).
"""
import os
import io
import base64
import logging

log = logging.getLogger(__name__)

# 오행별 상징 모티프 (자연 이미지)
_ELEMENT_MOTIF = {
    '목': 'an ancient towering tree and a quiet bamboo grove, fresh living green energy, new sprouts',
    '화': 'a radiant dawn sun and a gentle warm flame, luminous crimson and amber light',
    '토': 'a solitary majestic mountain rising over vast tranquil earth, grounded and timeless',
    '금': 'a luminous full moon over crisp white stone and clear autumn air, refined stillness',
    '수': 'a deep flowing river and a serene mirror lake under soft moonlight, gentle currents',
}


def generate_persona_image(saju_data: dict) -> bytes | None:
    """
    사주 데이터로 상징 이미지(JPEG bytes) 생성. 실패 시 None.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None

    try:
        from openai import OpenAI

        ilgan_oh = saju_data.get('ilgan', {}).get('ohaeng', '토')
        oh = saju_data.get('ohaeng', {})
        # 가장 강한 오행(보조 모티프)
        try:
            dominant = max(['목', '화', '토', '금', '수'],
                           key=lambda k: oh.get(k, {}).get('pct', 0))
        except Exception:
            dominant = ilgan_oh
        strength = saju_data.get('ilgan', {}).get('strength_label', '')
        mood = ('majestic, grounded, powerful and calm presence'
                if '신강' in strength else
                'gentle, serene, quietly resilient, soft and tender atmosphere')

        central = _ELEMENT_MOTIF.get(ilgan_oh, _ELEMENT_MOTIF['토'])
        second = _ELEMENT_MOTIF.get(dominant, '') if dominant != ilgan_oh else ''

        prompt = (
            "A premium traditional East-Asian ink-wash painting (sumukhwa) blended with a subtle modern gradient glow. "
            f"Central motif: {central}. "
            + (f"Subtle distant accents of {second}. " if second else "")
            + f"Overall mood: {mood}. "
            "Palette: deep indigo, midnight blue, and elegant muted gold. "
            "Mystical, atmospheric, serene negative space, museum-quality fine art, balanced centered composition. "
            "Absolutely no text, no letters, no words, no numbers, no people, no human figures, no faces."
        )

        client = OpenAI(api_key=api_key)
        resp = client.images.generate(
            model='gpt-image-1',
            prompt=prompt,
            size='1024x1024',
            quality='medium',
            n=1,
        )
        raw = base64.b64decode(resp.data[0].b64_json)
        return _compress_for_email(raw)

    except Exception as e:
        log.warning(f'페르소나 이미지 생성 실패(보고서는 정상 진행): {e}')
        return None


def _compress_for_email(raw: bytes) -> bytes:
    """이메일·PDF용으로 768px JPEG 압축 (원본 ~2MB → ~100KB대)"""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert('RGB')
        w, h = img.size
        target = 768
        if w > target:
            img = img.resize((target, int(h * target / w)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=82, optimize=True)
        return buf.getvalue()
    except Exception as e:
        log.warning(f'이미지 압축 실패, 원본 사용: {e}')
        return raw
