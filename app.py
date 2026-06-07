"""
라이프코드 해커 - Flask 메인 서버
사주 신청, 토스페이먼츠 결제, 보고서 생성, Gmail 발송
"""
import os
import json
import hashlib
import threading
import requests
from datetime import datetime, date
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, abort
from flask_cors import CORS


def _make_serial_no(name: str, email: str) -> str:
    """보고서 일련번호 생성 (이름·이메일·발행일 해시 8자리)"""
    today = datetime.now().strftime('%Y%m%d')
    base = f"{name}|{email}|{today}".encode('utf-8')
    digest = hashlib.sha256(base).hexdigest()[:8].upper()
    return f"LH-{today}-{digest}"

load_dotenv()

from saju.calculator import calculate_saju, saju_to_dict
from ai.interpreter import generate_report_sections, generate_cover_line
from ai.image_gen import generate_persona_image
from ai.astro import build_astro_context, build_transit_hook_context
from email_sender import send_report_email, send_report_link_email, send_notification
from refund import cancel_payment, get_payment_key_by_order_id

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'lifecoder-hacker-dev-key')

# ── CORS: Netlify 도메인 + 로컬 개발 허용 ──
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    'ALLOWED_ORIGINS',
    'https://dapper-praline-c90ab1.netlify.app,http://localhost:5000,http://127.0.0.1:5000'
).split(',') if o.strip()]
CORS(app, resources={r"/api/*": {"origins": _ALLOWED_ORIGINS}})

TOSS_SECRET_KEY  = os.environ.get('TOSS_SECRET_KEY', '')
TOSS_CLIENT_KEY  = os.environ.get('TOSS_CLIENT_KEY', '')
ADMIN_KEY        = os.environ.get('ADMIN_KEY', '')  # 관리자 환불 인증 키
FREE_CODE        = os.environ.get('FREE_CODE', '')  # 지인 무료 체험 코드 (빈 값이면 비활성)
REPORT_PRICE     = 8900  # 원


# ─────────────────────────────────────────────
# 페이지 라우트
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', toss_client_key=TOSS_CLIENT_KEY)


# ── 후기(리뷰) ──
REVIEWS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reviews.json')


def _load_reviews():
    try:
        with open(REVIEWS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_reviews(reviews):
    with open(REVIEWS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)


@app.route('/reviews')
def reviews_page():
    reviews = _load_reviews()
    # 최신순
    reviews = sorted(reviews, key=lambda r: r.get('date', ''), reverse=True)
    avg = round(sum(r.get('rating', 5) for r in reviews) / len(reviews), 1) if reviews else 0
    return render_template('reviews.html', reviews=reviews, avg=avg, count=len(reviews))


@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    reviews = _load_reviews()
    reviews = sorted(reviews, key=lambda r: r.get('date', ''), reverse=True)
    return jsonify(reviews)


@app.route('/api/reviews', methods=['POST'])
def submit_review():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()[:20]
    text = (data.get('text') or '').strip()[:500]
    try:
        rating = int(data.get('rating', 5))
    except (TypeError, ValueError):
        rating = 5
    rating = max(1, min(5, rating))

    if not name or len(text) < 5:
        return jsonify({'error': '이름과 5자 이상의 후기를 입력해 주세요.'}), 400

    reviews = _load_reviews()
    review = {
        'name': name,
        'rating': rating,
        'text': text,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
    }
    reviews.append(review)
    _save_reviews(reviews)
    # 백업: 후기를 관리자 메일로도 발송 (클라우드 파일 초기화 대비, 영구 보존)
    try:
        send_notification(
            f'[후기] {name} ({rating}점)',
            f"별점: {rating}/5\n이름: {name}\n날짜: {review['date']}\n\n{text}",
        )
    except Exception:
        pass
    return jsonify({'success': True})


@app.route('/payment/success')
def payment_success():
    return render_template('payment_success.html')


@app.route('/payment/fail')
def payment_fail():
    reason = request.args.get('message', '결제가 취소되었습니다.')
    return f"""
    <!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>결제 실패</title>
    <style>
      body{{background:#07070f;color:#e8e8f4;font-family:sans-serif;
           min-height:100vh;display:flex;align-items:center;justify-content:center;
           text-align:center;padding:40px 20px;}}
      h1{{font-size:22px;color:#f87171;margin-bottom:12px;}}
      p{{color:#8888aa;font-size:14px;line-height:1.8;}}
      a{{display:inline-block;margin-top:24px;background:#7c3aed;color:#fff;
         padding:14px 28px;border-radius:12px;text-decoration:none;font-weight:700;}}
    </style></head><body>
    <div>
      <h1>결제가 실패했습니다</h1>
      <p>{reason}</p>
      <a href="/">다시 시도하기</a>
    </div></body></html>
    """, 400


# ─────────────────────────────────────────────
# API 라우트
# ─────────────────────────────────────────────

@app.route('/api/payment/confirm', methods=['POST'])
def confirm_payment():
    """
    토스페이먼츠 결제 확인 → 사주 계산 → GPT 해석 → 이메일 발송
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': '잘못된 요청입니다.'}), 400

    payment_key = data.get('paymentKey')
    order_id    = data.get('orderId')
    amount      = data.get('amount')

    # 필수 필드 검증
    required = ['paymentKey', 'orderId', 'amount', 'name', 'email',
                'year', 'month', 'day', 'hour', 'gender']
    for field in required:
        if field not in data:
            return jsonify({'error': f'필드 누락: {field}'}), 400

    # ── 1. 토스페이먼츠 결제 최종 승인 ──
    toss_result = _confirm_toss_payment(payment_key, order_id, amount)
    if 'error' in toss_result:
        # 승인 자체가 실패 = 돈이 빠져나가지 않음 → 환불 불필요
        return jsonify({'error': toss_result['error']}), 400

    # ─────────────────────────────────────────────
    # 이 시점부터 결제 승인 완료 = 고객 돈이 차감됨.
    # 아래 단계(사주·GPT·렌더링·이메일) 중 하나라도 실패하면
    # '발송 전' 상태이므로 반드시 자동 환불한다. (핵심 안전장치)
    # ─────────────────────────────────────────────
    # 보고서 생성(2~3분)은 백그라운드로. 실패 시 백그라운드에서 자동 환불.
    token = _secrets.token_urlsafe(8)
    _REPORTS[token] = {'ready': False, 'error': None, 'name': data.get('name', '')}
    _spawn_report(data, payment_key=payment_key, order_id=order_id, token=token)

    return jsonify({
        'success': True,
        'email': data['email'],
        'token': token,
        'report_url': f'/report/{token}',
        'message': '결제가 완료되었습니다. 보고서를 만들고 있어요.',
    })


@app.route('/friends')
def friends_page():
    return render_template('friends.html')


@app.route('/api/friend-report', methods=['POST'])
def friend_report():
    """지인 전용 무료 보고서 — 코드 불필요, URL이 접근 제어 역할."""
    data = request.get_json(silent=True) or {}
    required = ['name', 'email', 'year', 'month', 'day', 'hour', 'gender']
    for field in required:
        if field not in data:
            return jsonify({'error': f'필드 누락: {field}'}), 400
    token = _secrets.token_urlsafe(8)
    _REPORTS[token] = {'ready': False, 'error': None, 'name': data.get('name', '')}
    _spawn_report(data, token=token)
    return jsonify({
        'success': True,
        'email': data['email'],
        'token': token,
        'report_url': f'/report/{token}',
        'message': '보고서를 만들고 있어요. 이 화면에서 잠시만 기다리면 바로 보여드려요.',
    })


@app.route('/api/free-report', methods=['POST'])
def free_report():
    """
    지인 무료 체험: 올바른 체험 코드를 입력하면 결제 없이 보고서를 발송.
    실제 고객 흐름(결제)과 완전히 분리됨.
    """
    data = request.get_json(silent=True) or {}

    # ── 체험 코드 인증 ──
    if not FREE_CODE:
        return jsonify({'error': '무료 체험이 현재 비활성화되어 있습니다.'}), 403
    if (data.get('code') or '').strip() != FREE_CODE:
        return jsonify({'error': '체험 코드가 올바르지 않습니다.'}), 403

    # 필수 필드 검증
    required = ['name', 'email', 'year', 'month', 'day', 'hour', 'gender']
    for field in required:
        if field not in data:
            return jsonify({'error': f'필드 누락: {field}'}), 400

    # 토큰 발급 후 백그라운드 생성 → 즉시 응답 (웹 링크로 제공)
    token = _secrets.token_urlsafe(8)
    _REPORTS[token] = {'ready': False, 'error': None, 'name': data.get('name', '')}
    _spawn_report(data, token=token)

    return jsonify({
        'success': True,
        'email': data['email'],
        'token': token,
        'report_url': f'/report/{token}',
        'message': '체험 보고서를 만들고 있어요. 이 화면에서 잠시만 기다리면 바로 보여드려요.',
    })


# 진단용: 마지막 백그라운드 보고서 작업의 단계/예외를 메모리에 기록.
# Render 런타임 로그 없이도 /api/last-report-status 로 실패 지점을 확인하기 위함.
import traceback as _traceback
import secrets as _secrets
_LAST_REPORT = {'stage': None, 'error': None, 'traceback': None, 'started': None, 'finished': None, 'email': None}

# ── 웹 링크 방식 보고서 저장소 ──
# Render 무료는 SMTP가 막혀 메일 발송이 안 되므로, 보고서를 웹페이지로 제공한다.
# 메모리 + 디스크 둘 다 저장(워커 재시작 대비). 디스크는 인스턴스 수명 동안 유지됨.
_REPORTS = {}  # token -> {'ready': bool, 'error': str|None, 'name': str}
_REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_store')
os.makedirs(_REPORT_DIR, exist_ok=True)


def _report_path(token: str) -> str:
    safe = ''.join(c for c in token if c.isalnum() or c in '-_')
    return os.path.join(_REPORT_DIR, f'{safe}.html')


def _save_report_html(token: str, html: str, name: str = ''):
    try:
        with open(_report_path(token), 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception as e:
        app.logger.warning(f'보고서 디스크 저장 실패(메모리만 사용): {e}')
    _REPORTS[token] = {'ready': True, 'error': None, 'name': name}


def _load_report_html(token: str):
    try:
        with open(_report_path(token), encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


def _report_stage(stage: str, email: str = None):
    _LAST_REPORT['stage'] = stage
    if email:
        _LAST_REPORT['email'] = email
    app.logger.info(f'[보고서단계] {stage}')


def _spawn_report(data: dict, payment_key: str = None, order_id: str = None, token: str = None):
    """보고서 생성·발송을 백그라운드 스레드에서 처리.
    결제 건(payment_key)에서 실패하면 자동 환불한다.
    token이 있으면 완성된 보고서를 웹 링크(/report/<token>)로 제공한다."""
    def worker():
        with app.app_context():
            _LAST_REPORT.update({'stage': '시작', 'error': None, 'traceback': None,
                                 'started': datetime.now().isoformat(), 'finished': None,
                                 'email': data.get('email')})
            try:
                _build_and_send_report(data, token=token)
                _LAST_REPORT['stage'] = '완료'
                _LAST_REPORT['finished'] = datetime.now().isoformat()
            except Exception as e:
                _LAST_REPORT['error'] = f'{type(e).__name__}: {e}'
                _LAST_REPORT['traceback'] = _traceback.format_exc()[-1500:]
                _LAST_REPORT['finished'] = datetime.now().isoformat()
                if token:
                    _REPORTS[token] = {'ready': False, 'error': str(e), 'name': data.get('name', '')}
                app.logger.error(f'백그라운드 보고서 실패(orderId={order_id}): {e}')
                if payment_key:
                    refund = cancel_payment(payment_key, '보고서 생성 실패에 따른 자동 환불')
                    if refund.get('success'):
                        app.logger.info(f'자동 환불 완료(orderId={order_id}, 기존취소={refund.get("already")})')
                    else:
                        app.logger.critical(
                            f'[수동환불필요] 자동환불 실패! orderId={order_id} '
                            f'paymentKey={payment_key} 오류={refund.get("error")}({refund.get("code")})')
    threading.Thread(target=worker, daemon=True).start()


def _build_and_send_report(data: dict, token: str = None):
    """만세력 계산 → GPT 해석 → 상징 이미지 → 렌더링 → 웹 저장 + 이메일(가능 시).
    생성 실패 시 예외를 던진다 (결제 흐름에서는 상위에서 자동 환불).
    이메일 발송 실패는 비치명적(웹 링크가 주 전달 수단)."""
    # ── 만세력 계산 ──
    year   = int(data['year'])
    month  = int(data['month'])
    day    = int(data['day'])
    hour   = int(data['hour'])
    minute = int(data.get('minute', 0))
    gender = data['gender']
    is_lunar = data.get('is_lunar', False)
    if isinstance(is_lunar, str):
        is_lunar = is_lunar.lower() == 'true'

    saju_result = calculate_saju(
        name=data['name'],
        year=year, month=month, day=day,
        hour=hour, minute=minute,
        gender=gender,
        is_lunar=is_lunar,
    )
    saju_data = saju_to_dict(saju_result)

    # ── 기질 보강(출생 차트) + 현재 트랜짓 컨텍스트 ──
    astro_context    = ''
    transit_context  = ''
    city = (data.get('city') or '').strip()
    if city:
        try:
            astro_context = build_astro_context(year, month, day, hour, minute, city)
        except Exception as e:
            app.logger.warning(f'기질 보강 생략(오류): {e}')
        try:
            transit_context = build_transit_hook_context(year, month, day, hour, minute, city)
        except Exception as e:
            app.logger.warning(f'트랜짓 후킹 생략(오류): {e}')

    # ── GPT 보고서 섹션 생성 (15개) ──
    _report_stage('섹션생성', data.get('email'))
    sections = generate_report_sections(saju_data, astro_context=astro_context, transit_context=transit_context)

    # ── 사주 상징 이미지 + 표지 헤드라인 (실패해도 보고서는 진행) ──
    _report_stage('이미지생성')
    try:
        persona_image = generate_persona_image(saju_data)
    except Exception as e:
        app.logger.warning(f'[보고서] 상징 이미지 실패(생략): {e}')
        persona_image = None
    cover_line = generate_cover_line(saju_data)

    # ── HTML 이메일 렌더링 ──
    report_date = datetime.now().strftime('%Y년 %m월 %d일')
    serial_no = _make_serial_no(saju_result.name, data['email'])
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

    # ── 웹 링크 저장 (주 전달 수단) ──
    # cid 인라인 이미지는 웹에서 안 보이므로 data:URI로 치환해 저장.
    if token:
        _report_stage('웹저장')
        web_html = html_content
        if persona_image:
            import base64 as _b64
            data_uri = 'data:image/jpeg;base64,' + _b64.b64encode(persona_image).decode()
            web_html = html_content.replace('cid:persona', data_uri)
        _save_report_html(token, web_html, name=saju_result.name)

    # ── 이메일 발송 (가능 시, 비치명적) ──
    # 신청 후 페이지를 닫아도 받을 수 있도록 '보고서 링크' 메일을 보낸다.
    # (본문 통째로 넣으면 Gmail이 잘라내므로 링크 방식)
    _report_stage('이메일발송')
    try:
        if token:
            public_base = os.environ.get('PUBLIC_BASE_URL', 'https://lifecode-hacker1.onrender.com').rstrip('/')
            send_report_link_email(
                to_email=data['email'],
                to_name=data['name'],
                report_url=f'{public_base}/report/{token}',
                cover_line=cover_line,
            )
        else:
            send_report_email(
                to_email=data['email'],
                to_name=data['name'],
                html_content=html_content,
                image_bytes=persona_image,
            )
        _report_stage('발송완료')
    except Exception as e:
        # 이메일 실패해도 웹 링크가 있으므로 보고서 전달은 성공으로 본다.
        app.logger.warning(f'[보고서] 이메일 발송 실패(웹 링크로 대체): {e}')
        _report_stage('이메일생략(웹링크제공)')


def _refund_and_respond(payment_key: str, order_id: str, error_detail: str):
    """
    보고서 처리 실패 시 자동 환불 후 적절한 응답 생성.
    환불 성공/실패에 따라 고객 안내 메시지가 달라진다.
    """
    refund_result = cancel_payment(
        payment_key,
        reason='보고서 생성/발송 실패에 따른 자동 환불',
    )

    if refund_result.get('success'):
        already = refund_result.get('already', False)
        app.logger.info(
            f'자동 환불 완료(orderId={order_id}, 기존취소={already})'
        )
        return jsonify({
            'error': (
                '보고서 생성 중 문제가 발생하여 결제가 자동으로 취소(환불)되었습니다. '
                '카드사에 따라 환불 반영까지 영업일 기준 3~5일이 걸릴 수 있습니다. '
                '잠시 후 다시 시도해 주세요.'
            ),
            'refunded': True,
        }), 502

    # 환불까지 실패 = 수동 개입 필요 (가장 위험한 케이스 → 명확히 로깅)
    app.logger.critical(
        f'[수동환불필요] 자동 환불 실패! orderId={order_id} '
        f'paymentKey={payment_key} '
        f'보고서오류={error_detail} '
        f'환불오류={refund_result.get("error")} ({refund_result.get("code")})'
    )
    return jsonify({
        'error': (
            '보고서 생성에 실패했습니다. 결제 자동 취소가 일시적으로 지연되어 '
            '담당자가 직접 빠르게 환불 처리해 드리겠습니다. '
            '불편을 드려 죄송합니다. 문의해 주시면 즉시 확인하겠습니다.'
        ),
        'refunded': False,
        'order_id': order_id,
    }), 502


def _confirm_toss_payment(payment_key: str, order_id: str, amount: int) -> dict:
    """토스페이먼츠 결제 최종 승인 API 호출"""
    if not TOSS_SECRET_KEY:
        # 개발 모드: 토스 키가 없으면 skip
        app.logger.warning('TOSS_SECRET_KEY 미설정 — 개발 모드로 결제 확인 건너뜀')
        return {'success': True}

    if int(amount) != REPORT_PRICE:
        return {'error': f'결제 금액이 올바르지 않습니다. 예상: {REPORT_PRICE}원'}

    import base64
    credentials = base64.b64encode(f'{TOSS_SECRET_KEY}:'.encode()).decode()

    try:
        response = requests.post(
            f'https://api.tosspayments.com/v1/payments/confirm',
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json',
            },
            json={
                'paymentKey': payment_key,
                'orderId': order_id,
                'amount': int(amount),
            },
            timeout=10,
        )
        result = response.json()

        if response.status_code != 200:
            error_msg = result.get('message', '결제 확인 실패')
            app.logger.error(f'토스 결제 확인 실패: {result}')
            return {'error': error_msg}

        if result.get('status') != 'DONE':
            return {'error': f"결제 상태 이상: {result.get('status')}"}

        return {'success': True, 'toss_data': result}

    except requests.Timeout:
        return {'error': '결제 서버 응답 시간 초과. 다시 시도해 주세요.'}
    except Exception as e:
        return {'error': f'결제 확인 중 오류: {str(e)}'}


@app.route('/api/admin/refund', methods=['POST'])
def admin_refund():
    """
    관리자 수동 환불 (예외 케이스용: 중복결제, 발송 전 고객요청 등)
    인증: 헤더 X-Admin-Key 또는 본문 admin_key 가 ADMIN_KEY와 일치해야 함.
    환불 대상: paymentKey 직접 지정 또는 orderId로 조회.
    """
    # ── 인증 ──
    body = request.get_json(silent=True) or {}
    provided = request.headers.get('X-Admin-Key', '') or body.get('admin_key', '')
    if not ADMIN_KEY:
        app.logger.error('ADMIN_KEY 미설정 — 관리자 환불 비활성화 상태')
        return jsonify({'error': '관리자 환불 기능이 설정되지 않았습니다.'}), 503
    if provided != ADMIN_KEY:
        app.logger.warning('관리자 환불 인증 실패')
        return jsonify({'error': '권한이 없습니다.'}), 403

    payment_key   = body.get('paymentKey')
    order_id      = body.get('orderId')
    reason        = body.get('reason', '고객 요청에 따른 수동 환불')
    cancel_amount = body.get('cancelAmount')  # None이면 전액

    # ── paymentKey가 없으면 orderId로 조회 ──
    if not payment_key:
        if not order_id:
            return jsonify({'error': 'paymentKey 또는 orderId가 필요합니다.'}), 400
        lookup = get_payment_key_by_order_id(order_id)
        if not lookup.get('success'):
            return jsonify({'error': lookup.get('error'), 'code': lookup.get('code')}), 400
        payment_key = lookup['paymentKey']

    # ── 환불 실행 ──
    result = cancel_payment(payment_key, reason, cancel_amount)
    if result.get('success'):
        app.logger.info(f'관리자 수동 환불 성공: orderId={order_id} paymentKey={payment_key}')
        return jsonify({
            'success': True,
            'status': result.get('status'),
            'already_canceled': result.get('already', False),
        })
    app.logger.error(f'관리자 수동 환불 실패: {result.get("error")} ({result.get("code")})')
    return jsonify({'error': result.get('error'), 'code': result.get('code')}), 400


# ─────────────────────────────────────────────
# 테스트 전용 라우트 (개발/검증용)
# ─────────────────────────────────────────────

TEST_FORM_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>사주 테스트</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d0d1a; color: #e8e8f4; font-family: 'Apple SD Gothic Neo', sans-serif;
         min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 40px 20px; }
  .card { background: #13131f; border: 1px solid #2a2a3e; border-radius: 20px;
          padding: 36px; max-width: 480px; width: 100%; }
  h1 { font-size: 20px; font-weight: 700; color: #a78bfa; margin-bottom: 6px; }
  .sub { color: #6666aa; font-size: 13px; margin-bottom: 28px; }
  label { display: block; font-size: 12px; color: #8888aa; margin-bottom: 6px; margin-top: 16px; }
  input, select { width: 100%; background: #1a1a2e; border: 1px solid #2a2a3e; border-radius: 10px;
                  color: #e8e8f4; padding: 12px 14px; font-size: 14px; outline: none; }
  input:focus, select:focus { border-color: #7c3aed; }
  .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .toggle-row { display: flex; gap: 10px; margin-top: 16px; }
  .toggle-btn { flex: 1; padding: 11px; border-radius: 10px; border: 1px solid #2a2a3e;
                background: #1a1a2e; color: #8888aa; cursor: pointer; font-size: 13px;
                transition: all .2s; text-align: center; }
  .toggle-btn.active { background: #2e1065; border-color: #7c3aed; color: #a78bfa; font-weight: 700; }
  .btn { width: 100%; margin-top: 28px; padding: 16px; background: linear-gradient(135deg, #7c3aed, #a855f7);
         border: none; border-radius: 14px; color: #fff; font-size: 16px; font-weight: 700;
         cursor: pointer; transition: opacity .2s; }
  .btn:hover { opacity: .9; }
  .note { margin-top: 14px; font-size: 11px; color: #555588; text-align: center; line-height: 1.6; }
</style>
</head>
<body>
<div class="card">
  <h1>보고서 미리보기 테스트</h1>
  <p class="sub">결제 없이 보고서 전체를 확인합니다 (개발용)</p>
  <form method="POST" action="/test-report">
    <label>이름</label>
    <input name="name" placeholder="홍길동" value="테스트">

    <label>생년월일</label>
    <div class="row">
      <input name="year"  type="number" placeholder="년" min="1930" max="2010" value="1990">
      <input name="month" type="number" placeholder="월" min="1"    max="12"   value="3">
      <input name="day"   type="number" placeholder="일" min="1"    max="31"   value="15">
    </div>

    <label>출생시간 (시진 선택)</label>
    <select name="hour">
      <option value="-1">모름 (오시 적용)</option>
      <option value="0">자시 (子時) KST 23:30~01:30</option>
      <option value="2">축시 (丑時) KST 01:30~03:30</option>
      <option value="4">인시 (寅時) KST 03:30~05:30</option>
      <option value="6">묘시 (卯時) KST 05:30~07:30</option>
      <option value="8">진시 (辰時) KST 07:30~09:30</option>
      <option value="10" selected>사시 (巳時) KST 09:30~11:30</option>
      <option value="12">오시 (午時) KST 11:30~13:30</option>
      <option value="14">미시 (未時) KST 13:30~15:30</option>
      <option value="16">신시 (申時) KST 15:30~17:30</option>
      <option value="18">유시 (酉時) KST 17:30~19:30</option>
      <option value="20">술시 (戌時) KST 19:30~21:30</option>
      <option value="22">해시 (亥時) KST 21:30~23:30</option>
    </select>

    <label>양력/음력</label>
    <div class="toggle-row">
      <div class="toggle-btn active" onclick="setLunar(this, false)" id="solar">☀️ 양력</div>
      <div class="toggle-btn" onclick="setLunar(this, true)" id="lunar">🌙 음력</div>
    </div>
    <input type="hidden" name="is_lunar" id="is_lunar_val" value="false">

    <label>성별</label>
    <div class="toggle-row">
      <div class="toggle-btn active" onclick="setGender(this, 'M')" id="male">♂ 남성</div>
      <div class="toggle-btn" onclick="setGender(this, 'F')" id="female">♀ 여성</div>
    </div>
    <input type="hidden" name="gender" id="gender_val" value="M">

    <label>이메일 (AI 사용 시 발송 테스트)</label>
    <input name="email" type="email" placeholder="test@example.com" value="">

    <label>AI 보고서</label>
    <select name="use_ai">
      <option value="false">❌ 스킵 (명식만 확인)</option>
      <option value="true">✅ GPT 실행 (API 키 필요)</option>
    </select>

    <button type="submit" class="btn">보고서 생성하기</button>
    <p class="note">이 페이지는 개발/테스트용입니다. 실제 서비스에서는 결제 후 생성됩니다.</p>
  </form>
</div>
<script>
function setLunar(el, val) {
  document.getElementById('solar').classList.toggle('active', !val);
  document.getElementById('lunar').classList.toggle('active', val);
  document.getElementById('is_lunar_val').value = val;
}
function setGender(el, val) {
  document.getElementById('male').classList.toggle('active', val === 'M');
  document.getElementById('female').classList.toggle('active', val === 'F');
  document.getElementById('gender_val').value = val;
}
</script>
</body>
</html>"""


@app.route('/test-report', methods=['GET', 'POST'])
def test_report():
    """결제 없이 보고서 미리보기 (개발/테스트 전용)"""
    if request.method == 'GET':
        return TEST_FORM_HTML

    # ── POST: 폼 데이터 처리 ──
    form = request.form
    name     = form.get('name', '테스트')
    year     = int(form.get('year', 1990))
    month    = int(form.get('month', 3))
    day      = int(form.get('day', 15))
    hour     = int(form.get('hour', 9))
    gender   = form.get('gender', 'M')
    is_lunar = form.get('is_lunar', 'false').lower() == 'true'
    use_ai   = form.get('use_ai', 'false').lower() == 'true'
    email    = form.get('email', '')

    if hour < 0:
        hour = 12  # 시간 모름 → 오시 기본

    # ── 만세력 계산 ──
    try:
        saju_result = calculate_saju(name, year, month, day, hour, 0, gender, is_lunar)
        saju_data   = saju_to_dict(saju_result)
    except Exception as e:
        return f"<pre style='color:red;background:#111;padding:20px'>사주 계산 오류:\n{e}</pre>", 500

    # ── AI 보고서 ──
    sections = {}
    ai_error = None
    if use_ai:
        try:
            sections = generate_report_sections(saju_data)
        except Exception as e:
            ai_error = str(e)
            sections = _dummy_sections(saju_data)
    else:
        sections = _dummy_sections(saju_data)

    # ── HTML 렌더링 ──
    try:
        report_date = datetime.now().strftime('%Y년 %m월 %d일')
        serial_no = _make_serial_no(saju_result.name, email or 'test@test.local')
        html = render_template(
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
        )
    except Exception as e:
        return f"<pre style='color:red;background:#111;padding:20px'>렌더링 오류:\n{e}</pre>", 500

    # 이메일 발송 테스트 (선택)
    if email and use_ai and not ai_error:
        try:
            send_report_email(email, name, html)
            app.logger.info(f'테스트 이메일 발송: {email}')
        except Exception as e:
            app.logger.warning(f'테스트 이메일 발송 실패: {e}')

    # 상단에 테스트 배너 삽입
    banner_color = '#dc2626' if ai_error else '#7c3aed'
    banner_msg   = f'AI 오류: {ai_error} - 더미 텍스트 표시 중' if ai_error else \
                   ('GPT 실행됨' if use_ai else '테스트 모드 - AI 스킵 (더미 텍스트)')
    banner = f"""<div style="background:{banner_color};color:#fff;text-align:center;padding:10px 20px;
                 font-family:sans-serif;font-size:13px;position:sticky;top:0;z-index:999">
                 {banner_msg} &nbsp;|&nbsp;
                 <a href="/test-report" style="color:#fff;text-decoration:underline">다시 테스트하기</a>
                 </div>"""
    return banner + html


def _dummy_sections(saju_data: dict) -> dict:
    """AI 없이 명식 요약만 넣은 더미 섹션 (레이아웃 확인용)"""
    pillars = saju_data['pillars']
    p_str = '  '.join([
        f"{pillars[k]['stem_hanja']}{pillars[k]['branch_hanja']}({pillars[k]['stem_kor']}{pillars[k]['branch_kor']})"
        for k in ['si', 'il', 'wol', 'nyeon']
    ])
    il = saju_data['ilgan']
    hc = saju_data['hapchung']
    dw = saju_data['daewoon']
    sw = saju_data['sewoon']

    hapchung_lines = []
    if hc['haps']:   hapchung_lines.append(f"<b>합</b>: {', '.join(hc['haps'])}")
    if hc['chungs']: hapchung_lines.append(f"<b>충</b>: {', '.join(hc['chungs'])}")
    if hc['pas']:    hapchung_lines.append(f"<b>파</b>: {', '.join(hc['pas'])}")
    if hc['haes']:   hapchung_lines.append(f"<b>해</b>: {', '.join(hc['haes'])}")
    hapchung_text = '<br>'.join(hapchung_lines) if hapchung_lines else '합충파해 없음'

    dw_cur = dw.get('current', {})
    dw_name = dw_cur.get('name', '?') if dw_cur else '계산 중'

    # 신강/신약 상세 (있으면 표시)
    sd = il.get('strength_detail', {})
    strength_summary = (
        f"월령 {'득령' if sd.get('weolryeong') else '실령'} | "
        f"득지 {'성공' if sd.get('deukji') else '실패'} | "
        f"득세 {sd.get('score_deukse', '?')}점 | "
        f"총점 {sd.get('total', '?')}점"
        if sd else '신강/신약 상세 정보 없음'
    )

    return {
        'transit_hook': "[AI 스킵] 지금 당신에게 일어나고 있는 일 (트랜짓 팩폭 후킹) 섹션입니다.",
        'intro':        f"[테스트 모드] 원국 {p_str}<br>일간 {il['name']}({il['ohaeng']}) {il['strength_label']}<br>GPT API 키를 입력하면 실제 해석이 생성됩니다.",
        'gyeokguk':     f"[AI 스킵] 격국·용신 섹션입니다.<br>{strength_summary}<br>월령 본기 기준 격국과 신강/신약 기반 용신을 분석합니다.",
        'love':         f"[AI 스킵] 연애 무의식 패턴 섹션입니다.<br>일간 {il['name']}의 관성·재성을 기반으로 분석됩니다.",
        'money':        f"[AI 스킵] 재물 패턴 섹션입니다.<br>재성·식상 분포를 기반으로 분석됩니다.",
        'habit':        f"[AI 스킵] 습관·행동 패턴 섹션입니다.<br>비겁·인성 배치를 기반으로 분석됩니다.",
        'career':       f"[AI 스킵] 직업·적성 + 건강·체질 코드 섹션입니다.<br>오행 분포와 십신으로 진로와 신체 약점을 분석합니다.",
        'hapchung':     f"[AI 스킵] 합충파해 섹션입니다.<br>{hapchung_text}",
        'family':       f"[AI 스킵] 가족·인간관계 자리 해석 섹션입니다.<br>년주(부모), 월주(형제·사회), 일주(배우자), 시주(자녀·미래) 자리별 분석.",
        'daewoon':      f"[AI 스킵] 현재 대운: <b>{dw_name}</b> ({dw['start_age']}세부터)",
        'sewoon':       f"[AI 스킵] 세운 분석입니다.",
        'calendar':     f"[AI 스킵] 12개월 월별 캘린더 섹션입니다.",
        'action':       "[AI 스킵] 이번 달 실천 가이드 섹션입니다.",
        'science':      "[AI 스킵] 왜 이게 맞는가 - 과학적 근거 섹션입니다.",
        'purification': "[AI 스킵] 무의식 정화 선언문 섹션입니다.",
        'family_hook':  "[AI 스킵] 가족 재구매 후킹 섹션입니다.",
    }


# ─────────────────────────────────────────────
# 헬스체크
# ─────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'lifecoder-hacker'})


# 배포 검증용: 실제로 어느 코드가 떠 있는지 curl로 확인하기 위한 마커.
# 값이 바뀌어 보이면 최신 푸시가 정상 배포된 것.
@app.route('/report/<token>')
def view_report(token):
    """완성된 보고서를 웹페이지로 제공."""
    html = _load_report_html(token)
    if html is None:
        info = _REPORTS.get(token)
        if info and info.get('error'):
            return ('<div style="font-family:sans-serif;max-width:560px;margin:80px auto;'
                    'text-align:center;color:#333;">보고서 생성 중 문제가 발생했습니다. '
                    '잠시 후 다시 시도해 주세요.</div>'), 500
        return ('<div style="font-family:sans-serif;max-width:560px;margin:80px auto;'
                'text-align:center;color:#333;">아직 보고서를 준비 중이거나 만료된 링크입니다.</div>'), 404
    return html


@app.route('/api/report-ready/<token>')
def report_ready(token):
    """폴링용: 보고서 준비 상태 반환."""
    info = _REPORTS.get(token)
    if info and info.get('ready'):
        return jsonify({'ready': True, 'url': f'/report/{token}'})
    if info and info.get('error'):
        return jsonify({'ready': False, 'error': True})
    return jsonify({'ready': False})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
