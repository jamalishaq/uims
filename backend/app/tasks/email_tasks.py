import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.tasks.celery_app import celery
from app.core.config import settings


@celery.task
def send_email(to: str, subject: str, html_body: str):
    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.starttls()
        server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
        server.send_message(msg)


@celery.task
def send_admission_decision(to: str, name: str, accepted: bool, reason: str = None):
    if accepted:
        subject = "Congratulations — Your Application has been Accepted"
        body = f"<p>Dear {name},</p><p>We are pleased to offer you admission. Log in to pay your acceptance fee and complete registration.</p>"
    else:
        subject = "Application Decision"
        body = f"<p>Dear {name},</p><p>We regret that your application was unsuccessful.</p>"
        if reason:
            body += f"<p><strong>Reason:</strong> {reason}</p>"

    send_email.delay(to, subject, body)


@celery.task
def send_result_notification(to: str, name: str, semester: str):
    send_email.delay(
        to,
        f"Results Published — {semester}",
        f"<p>Dear {name},</p><p>Your results for <strong>{semester}</strong> are now available. Log in to view your transcript.</p>",
    )


@celery.task
def send_payment_receipt(to: str, name: str, fee_type: str, amount: float, reference: str):
    send_email.delay(
        to,
        "Payment Confirmation",
        f"<p>Dear {name},</p><p>Your payment of <strong>₦{amount:,.2f}</strong> for <strong>{fee_type}</strong> has been confirmed.</p><p>Reference: {reference}</p>",
    )
