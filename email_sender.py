"""
Gmail SMTP 이메일 발송 모듈
보고서 HTML과 PDF 첨부를 함께 발송
"""
import os
import io
import base64
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.utils import formataddr


GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
SENDER_NAME = '라이프코드 해커'


def send_notification(subject: str, text: str) -> bool:
    """관리자(본인)에게 보내는 가벼운 텍스트 알림 메일 (후기 백업 등).
    실패해도 예외를 던지지 않는다(부가 기능)."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False
    try:
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
log = logging.getLogger(__name__)


def html_to_pdf_bytes(html_content: str) -> bytes:
    """
    HTML 보고서를 PDF 바이트로 변환
    우선 WeasyPrint 시도, 실패 시 xhtml2pdf로 fallback
    둘 다 실패하면 None 반환 (호출자가 PDF 없이 진행하도록)
    """
    # 1차: WeasyPrint (CSS3·그라데이션·웹폰트 지원)
    try:
        from weasyprint import HTML
        return HTML(string=html_content).write_pdf()
    except Exception as e:
        log.warning(f'WeasyPrint PDF 변환 실패, xhtml2pdf로 시도: {e}')

    # 2차: xhtml2pdf (가벼움, CSS 제한)
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
    보고서 HTML을 이메일로 발송 (가능하면 PDF 첨부 + 표지 인라인 이미지 포함)
    image_bytes: 표지에 삽입할 사주 상징 이미지(JPEG). HTML은 src="cid:persona" 참조.
    Returns: True(성공) / False(실패)
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise ValueError('Gmail 계정 정보가 설정되지 않았습니다. .env 파일을 확인하세요.')

    # 멀티파트 mixed: [related(본문+인라인이미지)] + [PDF 첨부]
    msg = MIMEMultipart('mixed')
    msg['Subject'] = f'[라이프코드 해커] {to_name}님의 사주 무의식 패턴 보고서가 도착했습니다'
    msg['From'] = formataddr((SENDER_NAME, GMAIL_ADDRESS))
    msg['To'] = formataddr((to_name, to_email))
    msg['Reply-To'] = GMAIL_ADDRESS

    # ── 본문 + 인라인 이미지 (related) ──
    related = MIMEMultipart('related')
    body = MIMEMultipart('alternative')
    text_part = MIMEText(
        f'{to_name}님의 사주 무의식 패턴 보고서입니다.\n'
        '이 이메일은 HTML 형식으로 작성되었습니다. HTML을 지원하는 이메일 클라이언트에서 확인해 주세요.\n'
        'PDF 첨부 파일도 함께 보내드렸으니 인쇄나 보관용으로 활용하세요.',
        'plain', 'utf-8'
    )
    html_part = MIMEText(html_content, 'html', 'utf-8')
    body.attach(text_part)
    body.attach(html_part)
    related.attach(body)

    # 인라인 이미지 (Gmail은 data:URI를 차단하므로 CID 방식 사용)
    if image_bytes:
        img_part = MIMEImage(image_bytes, _subtype='jpeg')
        img_part.add_header('Content-ID', f'<{image_cid}>')
        img_part.add_header('Content-Disposition', 'inline', filename='persona.jpg')
        related.attach(img_part)
        log.info(f'표지 인라인 이미지 첨부: {len(image_bytes)} bytes')

    msg.attach(related)

    # ── PDF용 HTML: cid 참조를 data:URI로 치환 (WeasyPrint는 cid를 못 읽음) ──
    pdf_source_html = html_content
    if image_bytes:
        data_uri = 'data:image/jpeg;base64,' + base64.b64encode(image_bytes).decode()
        pdf_source_html = html_content.replace(f'cid:{image_cid}', data_uri)

    # ── PDF 첨부 (변환 성공 시에만) ──
    pdf_bytes = html_to_pdf_bytes(pdf_source_html)
    if pdf_bytes:
        if not pdf_filename:
            safe_name = ''.join(c for c in to_name if c.isalnum() or c in '_-')
            pdf_filename = f'lifecoder_hacker_report_{safe_name or "report"}.pdf'
        pdf_part = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_part.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
        msg.attach(pdf_part)
        log.info(f'PDF 첨부 완료: {pdf_filename} ({len(pdf_bytes)} bytes)')
    else:
        log.warning('PDF 변환 실패 - HTML 이메일만 발송됩니다.')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        raise ValueError(
            'Gmail 인증 실패. Gmail 앱 비밀번호를 확인하세요.\n'
            '설정 방법: Google 계정 보안 2단계 인증 앱 비밀번호'
        )
    except Exception as e:
        raise RuntimeError(f'이메일 발송 실패: {str(e)}')
