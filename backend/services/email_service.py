"""
Email Service — Gmail SMTP OTP Delivery

Uses Python's built-in smtplib with STARTTLS for secure delivery.
If SMTP credentials are not configured, OTP is printed to the console
so development still works without an email account.

Configuration (in .env):
  SMTP_USERNAME=your@gmail.com
  SMTP_PASSWORD=xxxx xxxx xxxx xxxx   ← Gmail App Password (16 chars)
  SMTP_ENABLED=True
"""

from __future__ import annotations

import smtplib
import textwrap
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from config import settings

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------

def _build_otp_html(username: str, otp: str, expire_minutes: int) -> str:
    return textwrap.dedent(f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width,initial-scale=1.0">
      <title>Compliance Leader — Email Verification</title>
    </head>
    <body style="margin:0;padding:0;background:#080C14;font-family:Inter,Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#080C14;padding:40px 0;">
        <tr><td align="center">
          <table width="520" cellpadding="0" cellspacing="0"
                 style="background:#0D1421;border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;">

            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(135deg,#00D4FF,#7B2FBE);padding:28px 36px;">
                <div style="font-size:22px;font-weight:800;color:#080C14;letter-spacing:-0.02em;">
                  🏦 The Compliance Leader
                </div>
                <div style="font-size:13px;color:rgba(8,12,20,0.7);margin-top:4px;">
                  Banking-Grade Compliance Intelligence
                </div>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:36px;">
                <h2 style="margin:0 0 8px;font-size:20px;color:#F0F6FF;font-weight:700;">
                  Email Verification
                </h2>
                <p style="margin:0 0 24px;color:#8A95A8;font-size:14px;line-height:1.6;">
                  Hello <strong style="color:#F0F6FF;">{username}</strong>, use the code below to
                  verify your email address and activate your account.
                </p>

                <!-- OTP Box -->
                <div style="background:#080C14;border:2px solid #00D4FF;border-radius:12px;
                            padding:24px;text-align:center;margin-bottom:24px;">
                  <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;
                              color:#8A95A8;margin-bottom:10px;font-weight:600;">
                    Your Verification Code
                  </div>
                  <div style="font-size:44px;font-weight:900;letter-spacing:0.18em;
                              color:#00D4FF;font-family:'Courier New',monospace;
                              text-shadow:0 0 20px rgba(0,212,255,0.5);">
                    {otp}
                  </div>
                  <div style="font-size:12px;color:#4A5568;margin-top:10px;">
                    Valid for {expire_minutes} minutes
                  </div>
                </div>

                <!-- Security notice -->
                <div style="background:rgba(255,184,0,0.08);border:1px solid rgba(255,184,0,0.25);
                            border-radius:8px;padding:14px;margin-bottom:24px;">
                  <div style="font-size:12px;color:#FFB800;font-weight:600;margin-bottom:4px;">
                    ⚠️ Security Notice
                  </div>
                  <div style="font-size:12px;color:#8A95A8;line-height:1.5;">
                    Never share this code with anyone. Compliance Leader staff will never ask
                    for your OTP. If you did not request this, please ignore this email.
                  </div>
                </div>

                <p style="color:#4A5568;font-size:12px;margin:0;">
                  This code expires at: <strong style="color:#8A95A8;">
                  {datetime.utcnow().strftime("%Y-%m-%d %H:%M")} UTC + {expire_minutes} min
                  </strong>
                </p>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding:20px 36px;border-top:1px solid rgba(255,255,255,0.06);">
                <p style="margin:0;font-size:11px;color:#4A5568;line-height:1.6;">
                  This is an automated message from The Compliance Leader platform.<br>
                  ISO 20022 · SWIFT CBPR+ · Banking Compliance Intelligence
                </p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """).strip()


def _build_otp_plain(username: str, otp: str, expire_minutes: int) -> str:
    return textwrap.dedent(f"""
    The Compliance Leader — Email Verification
    ==========================================

    Hello {username},

    Your email verification code is:

        {otp}

    This code is valid for {expire_minutes} minutes.

    Security Notice: Never share this code with anyone. If you did not
    request this, please ignore this email.

    — The Compliance Leader Platform
    """).strip()


# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------

class EmailService:
    """Thin wrapper around smtplib for STARTTLS Gmail delivery."""

    def send_otp(self, to_email: str, username: str, otp: str) -> bool:
        """
        Send OTP email.
        Returns True on success, False on failure.
        Falls back to console logging when SMTP is disabled or unconfigured.
        """
        expire = settings.OTP_EXPIRE_MINUTES

        if not settings.SMTP_ENABLED or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            # Development fallback — print to console
            log.warning(
                "email_smtp_not_configured_otp_printed_to_console",
                to=to_email,
                username=username,
                otp=otp,
                expires_in_minutes=expire,
            )
            print(f"\n{'='*60}")
            print(f"  ⚠️  SMTP NOT CONFIGURED — DEV MODE OTP")
            print(f"  To: {to_email}  |  User: {username}")
            print(f"  OTP: {otp}  (expires in {expire} min)")
            print(f"{'='*60}\n")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Your Compliance Leader Verification Code"
            msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USERNAME}>"
            msg["To"]      = to_email
            msg["X-Mailer"] = "Compliance Leader Auth System"

            plain_part = MIMEText(_build_otp_plain(username, otp, expire), "plain", "utf-8")
            html_part  = MIMEText(_build_otp_html(username, otp, expire),  "html",  "utf-8")

            # Per RFC 2046: last part is preferred
            msg.attach(plain_part)
            msg.attach(html_part)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USERNAME, to_email, msg.as_string())

            log.info("otp_email_sent", to=to_email, username=username)
            return True

        except smtplib.SMTPAuthenticationError:
            log.error(
                "smtp_auth_error",
                hint="Check SMTP_USERNAME and SMTP_PASSWORD (use Gmail App Password, not account password)",
            )
            return False
        except smtplib.SMTPException as exc:
            log.error("smtp_send_failed", error=str(exc))
            return False
        except Exception as exc:
            log.error("email_unexpected_error", error=str(exc))
            return False

    def send_password_reset_notification(self, to_email: str, username: str) -> bool:
        """Notify user that an admin has reset their password."""
        if not settings.SMTP_ENABLED or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            log.info("password_reset_notification_skipped_no_smtp", to=to_email)
            return True
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "Compliance Leader — Password Reset by Administrator"
            msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USERNAME}>"
            msg["To"]      = to_email
            body = f"""
            Hello {username},
            
            An administrator has reset your password. You will be required to set a new
            password on your next login.
            
            If you did not expect this, please contact your system administrator immediately.
            
            — The Compliance Leader Platform
            """
            msg.attach(MIMEText(body, "plain", "utf-8"))
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
                s.starttls()
                s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                s.sendmail(settings.SMTP_USERNAME, to_email, msg.as_string())
            return True
        except Exception as exc:
            log.error("password_reset_email_failed", error=str(exc))
            return False


email_service = EmailService()
