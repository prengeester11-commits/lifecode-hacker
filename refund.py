"""
토스페이먼츠 결제 취소(환불) 모듈

설계 원칙:
  - 멱등성(idempotency): 이미 취소된 결제는 '성공'으로 간주 (중복 환불 안전)
  - 상태 검증: 취소 전 결제 상태를 조회해 취소 가능 여부 확인
  - 오류 격리: 네트워크/인증/상태 오류를 명확한 코드로 반환
  - 개발 모드: TOSS_SECRET_KEY 미설정 시 실제 호출 없이 mock 성공

토스 결제 상태 흐름:
  READY → IN_PROGRESS → DONE → (CANCELED | PARTIAL_CANCELED)
  취소 가능 상태: DONE (전액/부분), PARTIAL_CANCELED (잔액 부분취소)
"""
import os
import base64
import logging
import requests

log = logging.getLogger(__name__)

TOSS_API_BASE = 'https://api.tosspayments.com/v1/payments'
_TIMEOUT = 10


def _secret_key() -> str:
    """런타임에 환경변수를 읽어 키 변경 즉시 반영"""
    return os.environ.get('TOSS_SECRET_KEY', '')


def _auth_header() -> dict:
    credentials = base64.b64encode(f'{_secret_key()}:'.encode()).decode()
    return {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/json',
    }


def get_payment(payment_key: str) -> dict:
    """
    결제 단건 조회
    Returns: {'success': True, 'data': {...}} 또는 {'error': '...', 'code': '...'}
    """
    if not _secret_key():
        # 개발 모드: 조회 불가 → DONE으로 가정
        return {'success': True, 'data': {'status': 'DONE', 'balanceAmount': 0}, 'dev': True}

    try:
        resp = requests.get(
            f'{TOSS_API_BASE}/{payment_key}',
            headers=_auth_header(),
            timeout=_TIMEOUT,
        )
        data = resp.json()
        if resp.status_code != 200:
            return {
                'error': data.get('message', '결제 조회 실패'),
                'code': data.get('code', 'UNKNOWN'),
            }
        return {'success': True, 'data': data}
    except requests.Timeout:
        return {'error': '결제 조회 시간 초과', 'code': 'TIMEOUT'}
    except Exception as e:
        return {'error': f'결제 조회 오류: {e}', 'code': 'EXCEPTION'}


def get_payment_key_by_order_id(order_id: str) -> dict:
    """
    주문번호(orderId)로 결제를 조회해 paymentKey를 얻는다.
    관리자가 orderId만으로 환불할 수 있게 하는 편의 함수.
    Returns: {'success': True, 'paymentKey': '...', 'status': '...'} 또는 {'error': ...}
    """
    if not order_id:
        return {'error': '주문번호가 없습니다.', 'code': 'NO_ORDER_ID'}

    if not _secret_key():
        return {'success': True, 'paymentKey': f'dev_{order_id}', 'status': 'DONE', 'dev': True}

    try:
        resp = requests.get(
            f'{TOSS_API_BASE}/orders/{order_id}',
            headers=_auth_header(),
            timeout=_TIMEOUT,
        )
        data = resp.json()
        if resp.status_code != 200:
            return {
                'error': data.get('message', '주문 조회 실패'),
                'code': data.get('code', 'UNKNOWN'),
            }
        return {
            'success': True,
            'paymentKey': data.get('paymentKey'),
            'status': data.get('status'),
        }
    except requests.Timeout:
        return {'error': '주문 조회 시간 초과', 'code': 'TIMEOUT'}
    except Exception as e:
        return {'error': f'주문 조회 오류: {e}', 'code': 'EXCEPTION'}


def cancel_payment(
    payment_key: str,
    reason: str,
    cancel_amount: int = None,
) -> dict:
    """
    결제 취소(환불)

    Args:
        payment_key: 토스 결제 키
        reason: 취소 사유 (필수, 토스 정책)
        cancel_amount: 부분 취소 금액 (None이면 전액 취소)

    Returns:
        성공: {'success': True, 'status': 'CANCELED', 'already': bool}
        실패: {'error': '...', 'code': '...'}

    멱등성: 이미 취소된 결제(ALREADY_CANCELED_PAYMENT)는 success=True, already=True 로 반환
    """
    if not payment_key:
        return {'error': '결제 키가 없습니다.', 'code': 'NO_PAYMENT_KEY'}

    # ── 개발 모드 ──
    if not _secret_key():
        log.warning(f'[DEV] 환불 mock 처리: {payment_key} / 사유: {reason}')
        return {'success': True, 'status': 'CANCELED', 'already': False, 'dev': True}

    # ── 1. 상태 선조회 (멱등성·중복 환불 방지) ──
    status_result = get_payment(payment_key)
    if 'success' in status_result:
        current_status = status_result['data'].get('status', '')
        if current_status in ('CANCELED', 'PARTIAL_CANCELED') and cancel_amount is None:
            # 이미 전액 취소됨 → 멱등 성공
            log.info(f'환불 멱등 처리(이미 취소됨): {payment_key} status={current_status}')
            return {'success': True, 'status': current_status, 'already': True}
        if current_status not in ('DONE', 'PARTIAL_CANCELED'):
            # DONE이 아니면 취소 대상 아님 (READY/IN_PROGRESS/ABORTED/EXPIRED)
            return {
                'error': f'취소 불가능한 결제 상태입니다: {current_status}',
                'code': 'NOT_CANCELABLE',
                'status': current_status,
            }
    # 조회 실패해도 취소 시도는 진행 (토스가 최종 판단)

    # ── 2. 취소 요청 ──
    body = {'cancelReason': reason or '서비스 제공 실패에 따른 자동 환불'}
    if cancel_amount is not None:
        body['cancelAmount'] = int(cancel_amount)

    try:
        resp = requests.post(
            f'{TOSS_API_BASE}/{payment_key}/cancel',
            headers=_auth_header(),
            json=body,
            timeout=_TIMEOUT,
        )
        data = resp.json()

        if resp.status_code == 200:
            status = data.get('status', 'CANCELED')
            log.info(f'환불 성공: {payment_key} status={status} 사유={reason}')
            return {'success': True, 'status': status, 'already': False, 'data': data}

        # ── 오류 코드별 처리 ──
        code = data.get('code', 'UNKNOWN')
        msg = data.get('message', '결제 취소 실패')

        # 이미 취소된 결제 → 멱등 성공
        if code in ('ALREADY_CANCELED_PAYMENT',):
            log.info(f'환불 멱등 처리(토스 ALREADY_CANCELED): {payment_key}')
            return {'success': True, 'status': 'CANCELED', 'already': True}

        log.error(f'환불 실패: {payment_key} code={code} msg={msg}')
        return {'error': msg, 'code': code}

    except requests.Timeout:
        log.error(f'환불 요청 시간 초과: {payment_key}')
        return {'error': '결제 취소 서버 응답 시간 초과', 'code': 'TIMEOUT'}
    except Exception as e:
        log.error(f'환불 요청 예외: {payment_key} {e}')
        return {'error': f'결제 취소 중 오류: {e}', 'code': 'EXCEPTION'}
