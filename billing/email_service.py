"""
Advance Billing System — Password Recovery Email Service.
Handles multi-part (HTML & Plain Text) email generation and dispatching for OTP-based password recovery.
"""

import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger("billing.email_service")


def get_client_ip(request):
    """
    Safely extract client IP address from HttpRequest headers.
    Handles proxies and reverse proxy configurations (X-Forwarded-For).
    """
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def mask_email_address(email):
    """
    Mask email address for secure presentation in UI and logs.
    Example: admin.john@enterprise.com -> a***n@enterprise.com
    """
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def send_password_recovery_otp_email(user, otp, expiry_minutes=10, ip_address=None):
    """
    Render and dispatch a professional multi-part HTML & text OTP email for password recovery.

    Parameters:
        user (User): The target user object.
        otp (str): The 6-digit numeric OTP code.
        expiry_minutes (int): Minutes until code expiration (default 10).
        ip_address (str): Optional IP address of requesting client for security audit.

    Returns:
        tuple (success: bool, message: str)
    """
    if not user.email:
        warning_msg = f"User '{user.username}' does not have a registered email address."
        logger.warning(warning_msg)
        print(f"[EMAIL WARNING] {warning_msg}")
        return False, warning_msg

    now = timezone.now()
    expiry_time = now + timedelta(minutes=expiry_minutes)
    recipient_name = user.get_full_name() or user.username

    support_email = getattr(settings, "SUPPORT_EMAIL", "support@advancebilling.com")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "Advance Billing <no-reply@advancebilling.com>")
    subject = "Advance Billing — Your Password Recovery Code"

    context = {
        "user": user,
        "username": user.username,
        "recipient_name": recipient_name,
        "otp": str(otp),
        "otp_digits": list(str(otp)),
        "expiry_minutes": expiry_minutes,
        "expiry_time_str": expiry_time.strftime("%I:%M %p UTC"),
        "request_time_str": now.strftime("%d %b %Y, %I:%M %p UTC"),
        "ip_address": ip_address,
        "support_email": support_email,
    }

    try:
        # Render HTML and Plain Text versions
        html_content = render_to_string("emails/password_reset_otp.html", context)
        text_content = render_to_string("emails/password_reset_otp.txt", context)

        # Construct Multi-Part MIME message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        # Print prominent security banner for local developer visibility
        print("=" * 64)
        print(f"[SECURITY EMAIL DISPATCHED] OTP for '{user.username}' <{user.email}>")
        print(f"OTP CODE: {otp} | EXPIRES IN: {expiry_minutes}m ({expiry_time.strftime('%I:%M %p')})")
        if ip_address:
            print(f"CLIENT IP: {ip_address}")
        print("=" * 64)

        logger.info(f"Password recovery OTP email sent to {user.email} (User: {user.username})")
        return True, "Verification email dispatched successfully."

    except Exception as exc:
        err_msg = f"Failed to dispatch OTP email to {user.email}: {str(exc)}"
        logger.error(err_msg, exc_info=True)
        print(f"[EMAIL ERROR] {err_msg}")
        return False, err_msg


def send_password_reset_success_email(user, ip_address=None):
    """
    Send an audit confirmation notification email when an administrator's password is reset.

    Parameters:
        user (User): The target user object.
        ip_address (str): Optional IP address of client who finalized reset.

    Returns:
        tuple (success: bool, message: str)
    """
    if not user.email:
        return False, "User has no email."

    now = timezone.now()
    recipient_name = user.get_full_name() or user.username
    support_email = getattr(settings, "SUPPORT_EMAIL", "support@advancebilling.com")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "Advance Billing <no-reply@advancebilling.com>")
    subject = "Advance Billing — Security Alert: Password Changed"

    context = {
        "user": user,
        "username": user.username,
        "recipient_name": recipient_name,
        "timestamp": now.strftime("%d %b %Y, %I:%M %p UTC"),
        "ip_address": ip_address,
        "support_email": support_email,
    }

    try:
        html_content = render_to_string("emails/password_reset_success.html", context)
        text_content = render_to_string("emails/password_reset_success.txt", context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)

        logger.info(f"Password reset confirmation email sent to {user.email}")
        return True, "Confirmation email dispatched."

    except Exception as exc:
        logger.warning(f"Could not dispatch password reset success notification: {exc}")
        return False, str(exc)
