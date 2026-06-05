"""
이메일 발송 모듈.

Render 무료 플랜은 외부 SMTP 포트(465/587)를 차단하므로, 운영 환경에서는
Brevo HTTP API(HTTPS 443)로 발송한다. BREVO_API_KEY 가 설정돼 있으면 Brevo를 쓰고,
없으면 Gmail SMTP로 폴백한다(로컬 개발용).
"""
import os
import io
import base64
import logging
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formataddr

log = logging.getLogger(__name__)

GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
SENDER_NAME = '라이프코드 해커'

# Brevo (HTTP 발송) 설정
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
# 발신 주소: Brevo에서 '인증된 발신자(verified sender)'여야 함. 기본은 Gmail 주소.
BREVO_SENDER = os.environ.get('BREVO_SENDER', GMAIL_ADDRESS)
BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _send_via_brevo(to_email: str, to_name: str, subject: str,
                    html_content: str, text_content: str = '') -> bool:
    """Brevo HTTP API로 메일 발송. 실패 시 예외."""
    payload = {
        'sender': {'name': SENDER_NAME, 'email': BREVO_SENDER},
        'to': [{'email': to_email, 'name': to_name or to_email}],
        'subject': subject,
        'htmlContent': html_content,
        'replyTo': {'email': BREVO_SENDER, 'name': SENDER_NAME},
    }
    if text_content:
        payload['textContent'] = text_content
    resp = requests.post(
        BREVO_API_URL,
        headers={'api-key': BREVO_API_KEY, 'content-type': 'application/json',
                 'accept': 'application/json'},
        json=payload, timeout=30,
    )
    if resp.status_code in (200, 201):
        log.info(f'Brevo 발송 성공: {to_email} (msgId={resp.json().get("messageId","?")})')
        return True
    raise RuntimeError(f'Brevo 발송 실패 status={resp.status_code} body={resp.text[:300]}')


def send_notification(subject: str, text: str) -> bool:
    """관리자(본인)에게 보내는 가벼운 텍스트 알림 메일. 실패해도 예외를 던지지 않는다."""
    try:
        if BREVO_API_KEY:
            return _send_via_brevo(GMAIL_ADDRESS, SENDER_NAME, subject,
                                   f'<pre>{text}</pre>', text)
        if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
            return False
        msg = MIMEText(text, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = formataddr((SENDER_NAME, GMAIL_ADDRESS))
        msg['To'] = GMAIL_ADDRESS
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())
        return True
    except Exception as e:
        log.warning(f'알림 메일 실패: {e}')
        return False


def html_to_pdf_bytes(html_content: str) -> bytes:
    """HTML 보고서를 PDF 바이트로 변환 (WeasyPrint → xhtml2pdf 폴백). 둘 다 실패 시 None."""
    try:
        from weasyprint import HTML
        return HTML(string=html_content).write_pdf()
    except Exception as e:
        log.warning(f'WeasyPrint PDF 변환 실패, xhtml2pdf로 시도: {e}')
    try:
        from xhtml2pdf import pisa
        buf = io.BytesIO()
        result = pisa.CreatePDF(src=html_content, dest=buf, encoding='utf-8')
        if result.err:
            log.warning(f'xhtml2pdf 변환 오류 코드: {result.err}')
            return None
        return buf.getvalue()
    except Exception as e:
        log.warning(f'xhtml2pdf PDF 변환 실패: {e}')
        return None


def send_report_email(
    to_email: str,
    to_name: str,
    html_content: str,
    pdf_filename: str = None,
    image_bytes: bytes = None,
    image_cid: str = 'persona',
) -> bool:
    """
    보고서 HTML 이메일 발송.
    - BREVO_API_KEY 설정 시: Brevo HTTP API (Render 무료에서도 동작). 표지 이미지는 data:URI로 인라인.
    - 미설정 시: Gmail SMTP (로컬 개발용), CID 인라인 이미지 + 선택적 PDF 첨부.
    """
    subject = f'[라이프코드 해커] {to_name}님의 사주 무의식 패턴 보고서가 도착했습니다'
    text_fallback = (
        f'{to_name}님의 사주 무의식 패턴 보고서입니다.\n'
        'HTML을 지원하는 이메일 클라이언트에서 확인해 주세요.'
    )

    # ── 운영: Brevo HTTP API ──
    if BREVO_API_KEY:
        if not BREVO_SENDER:
            raise ValueError('BREVO_SENDER(발신 주소)가 설정되지 않았습니다.')
        html_for_api = html_content
        if image_bytes:
            data_uri = 'data:image/jpeg;base64,' + base64.b64encode(image_bytes).decode()
            html_for_api = html_content.replace(f'cid:{image_cid}', data_uri)
        return _send_via_brevo(to_email, to_name, subject, html_for_api, text_fallback)

    # ── 로컬 개발: Gmail SMTP ──
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise ValueError('발송 설정이 없습니다. BREVO_API_KEY 또는 Gmail 정보를 설정하세요.')

    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = formataddr((SENDER_NAME, GMAIL_ADDRESS))
    msg['To'] = formataddr((to_name, to_email))
    msg['Reply-To'] = GMAIL_ADDRESS

    related = MIMEMultipart('related')
    body = MIMEMultipart('alternative')
    body.attach(MIMEText(text_fallback, 'plain', 'utf-8'))
    body.attach(MIMEText(html_content, 'html', 'utf-8'))
    related.attach(body)

    if image_bytes:
        img_part = MIMEImage(image_bytes, _subtype='jpeg')
        img_part.add_header('Content-ID', f'<{image_cid}>')
        img_part.add_header('Content-Disposition', 'inline', filename='persona.jpg')
        related.attach(img_part)
    msg.attach(related)

    pdf_bytes = None
    if os.environ.get('ENABLE_PDF', '').lower() == 'true':
        pdf_source_html = html_content
        if image_bytes:
            data_uri = 'data:image/jpeg;base64,' + base64.b64encode(image_bytes).decode()
            pdf_source_html = html_content.replace(f'cid:{image_cid}', data_uri)
        pdf_bytes = html_to_pdf_bytes(pdf_source_html)
    if pdf_bytes:
        if not pdf_filename:
            safe_name = ''.join(c for c in to_name if c.isalnum() or c in '_-')
            pdf_filename = f'lifecoder_hacker_report_{safe_name or "report"}.pdf'
        pdf_part = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_part.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
        msg.attach(pdf_part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        raise ValueError('Gmail 인증 실패. 앱 비밀번호를 확인하세요.')
    except Exception as e:
        raise RuntimeError(f'이메일 발송 실패: {str(e)}')
