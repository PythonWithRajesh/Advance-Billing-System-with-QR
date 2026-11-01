from email import errors
from urllib import request

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


from io import BytesIO
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import get_template
from xhtml2pdf import pisa


import random
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone
from django.core.paginator import Paginator

import json
from decimal import Decimal, InvalidOperation
from django.db import transaction

from .models import PasswordResetOTP, DistributorProfile, Customer, Product, Invoice, InvoiceItem
from .utils import (
    generate_secure_otp,
    mask_email,
    validate_admin_password_complexity,
    send_admin_password_reset_email,
    generate_admin_reset_token,
    verify_admin_reset_token,
)

from django.db import models


def admin_login(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect("admin_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            if user.is_superuser:
                login(request, user)
                return redirect("admin_dashboard")

            messages.error(
                request,
                "You are not authorized to access the Admin Portal."
            )
        else:
            messages.error(
                request,
                "Invalid username or password."
            )

    return render(request, "admin_login.html")


# ==========================================================
# ADMIN USER REGISTRATION (API & WEB)
# ==========================================================

@csrf_exempt
def admin_register_api(request):
    """
    API endpoint to register a new Admin user (superuser & staff).
    Accepts application/json and application/x-www-form-urlencoded POST requests.
    """
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed. Use POST to register an admin user.",
            },
            status=405,
        )

    # Parse request payload (supports JSON body and form data)
    data = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid JSON payload.",
                },
                status=400,
            )
    else:
        data = request.POST.dict()

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password", ""))
    first_name = str(data.get("first_name", data.get("name", ""))).strip()
    last_name = str(data.get("last_name", "")).strip()

    errors = {}

    # 1. Username validation
    if not username:
        errors["username"] = "Username is required."
    elif len(username) < 3:
        errors["username"] = "Username must contain at least 3 characters."
    elif len(username) > 150:
        errors["username"] = "Username cannot exceed 150 characters."
    elif not username.replace("_", "").replace("-", "").replace(".", "").isalnum():
        errors["username"] = "Username can only contain letters, numbers, and @/./+/-/_ characters."
    elif User.objects.filter(username__iexact=username).exists():
        errors["username"] = "An account with this username already exists."

    # 2. Email validation
    if not email:
        errors["email"] = "Email address is required."
    elif "@" not in email or "." not in email.split("@")[-1]:
        errors["email"] = "Please enter a valid email address."
    elif User.objects.filter(email__iexact=email).exists():
        errors["email"] = "An account with this email already exists."

    # 3. Password validation
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 8:
        errors["password"] = "Password must contain at least 8 characters."
    elif not any(c.isupper() for c in password):
        errors["password"] = "Password must contain at least one uppercase letter."
    elif not any(c.islower() for c in password):
        errors["password"] = "Password must contain at least one lowercase letter."
    elif not any(c.isdigit() for c in password):
        errors["password"] = "Password must contain at least one digit."

    # 4. Confirm password check (if provided in payload)
    if confirm_password and password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    if errors:
        return JsonResponse(
            {
                "success": False,
                "message": "Validation failed.",
                "errors": errors,
            },
            status=400,
        )

    # 5. Create the Admin user
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Admin user registered successfully.",
                "data": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "date_joined": user.date_joined.isoformat(),
                },
            },
            status=201,
        )
    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "message": f"Failed to create admin user: {str(exc)}",
            },
            status=500,
        )


def admin_register(request):
    """
    Web registration view for Admin users.
    """
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("admin_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        name = request.POST.get("name", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        errors = {}
        if not username:
            errors["username"] = "Username is required."
        elif len(username) < 3:
            errors["username"] = "Username must be at least 3 characters."
        elif User.objects.filter(username__iexact=username).exists():
            errors["username"] = "An account with this username already exists."

        if not email:
            errors["email"] = "Email address is required."
        elif "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Please enter a valid email address."
        elif User.objects.filter(email__iexact=email).exists():
            errors["email"] = "An account with this email already exists."

        if not password:
            errors["password"] = "Password is required."
        elif len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        elif not any(c.isupper() for c in password):
            errors["password"] = "Password must contain at least one uppercase letter."
        elif not any(c.islower() for c in password):
            errors["password"] = "Password must contain at least one lowercase letter."
        elif not any(c.isdigit() for c in password):
            errors["password"] = "Password must contain at least one number."

        if password != confirm_password:
            errors["confirm_password"] = "Passwords do not match."

        if errors:
            return render(
                request,
                "admin_register.html",
                {
                    "errors": errors,
                    "username": username,
                    "email": email,
                    "name": name,
                },
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save()

        messages.success(request, f"Admin account '{username}' registered successfully! Please login.")
        return redirect("admin_login")

    return render(request, "admin_register.html")


def distributor_login(request):
    if request.user.is_authenticated:
        if not request.user.is_superuser:
            return redirect("distributor_dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            if not user.is_superuser:
                login(request, user)
                return redirect("distributor_dashboard")

            messages.error(
                request,
                "Admin account cannot access the Distributor Portal."
            )
        else:
            messages.error(
                request,
                "Invalid username or password."
            )

    return render(request, "distributor_login.html")


@login_required(login_url="admin_login")
def admin_dashboard(request):
    if not request.user.is_superuser:
        logout(request)
        messages.error(
            request,
            "Admin access required."
        )
        return redirect("admin_login")

    return render(
        request,
        "admin_dashboard.html"
    )


@login_required(login_url="distributor_login")
def distributor_dashboard(request):
    if request.user.is_superuser:
        logout(request)
        messages.error(
            request,
            "Distributor access required."
        )
        return redirect("distributor_login")

    return render(
        request,
        "distributor_dashboard.html"
    )


def user_logout(request):
    logout(request)

    messages.success(
        request,
        "You have been logged out successfully."
    )

    return redirect("admin_login")


# ==========================================================
# ADMIN PASSWORD RECOVERY - WEB VIEWS
# ==========================================================

def forgot_password(request):
    """
    Web view: Request OTP for Admin password recovery.
    Accepts admin username or email address.
    """
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("admin_dashboard")

    if request.method == "POST":
        identifier = request.POST.get("username", request.POST.get("identifier", "")).strip()

        if not identifier:
            return render(
                request,
                "forgot_password.html",
                {"error": "Please enter your admin username or email address."},
            )

        # Lookup user by username or email (case-insensitive)
        user = User.objects.filter(
            models.Q(username__iexact=identifier) | models.Q(email__iexact=identifier)
        ).first()

        if not user:
            return render(
                request,
                "forgot_password.html",
                {"error": "No account found matching this username or email."},
            )

        # Enforce that the account must be an Administrator
        if not (user.is_staff or user.is_superuser):
            return render(
                request,
                "forgot_password.html",
                {"error": "Access denied. Only Administrator accounts can recover passwords through this portal."},
            )

        # Invalidate previous unused OTPs
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        # Generate cryptographically secure 6-digit OTP
        otp = generate_secure_otp(6)
        PasswordResetOTP.objects.create(user=user, otp=otp)

        # Dispatch email and console notification
        send_admin_password_reset_email(user, otp)

        # Store session state
        request.session["reset_user_id"] = user.id
        request.session["reset_is_admin"] = True
        request.session["otp_attempts"] = 0
        request.session["last_otp_sent_at"] = timezone.now().isoformat()

        masked = mask_email(user.email) if user.email else user.username
        messages.success(
            request,
            f"A 6-digit verification code has been dispatched to {masked}."
        )
        return redirect("verify_otp")

    return render(request, "forgot_password.html")


def verify_otp(request):
    """
    Web view: Verify the 6-digit OTP for Admin password recovery.
    Includes rate-limiting (max 5 failed attempts) and 10-minute expiry check.
    """
    user_id = request.session.get("reset_user_id")
    if not user_id:
        messages.error(request, "Session expired or invalid. Please request a new OTP.")
        return redirect("forgot_password")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        request.session.flush()
        return redirect("forgot_password")

    if not (user.is_staff or user.is_superuser):
        messages.error(request, "Access denied. Only Administrator accounts can recover passwords.")
        return redirect("admin_login")

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        if not entered_otp:
            return render(
                request,
                "verify_otp.html",
                {"error": "Please enter the 6-digit verification code."},
            )

        # Brute-force protection: track attempts
        attempts = request.session.get("otp_attempts", 0) + 1
        request.session["otp_attempts"] = attempts
        if attempts > 5:
            PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)
            return render(
                request,
                "verify_otp.html",
                {"error": "Maximum verification attempts exceeded. For security, please request a new OTP."},
            )

        # Find latest unused OTP
        otp_record = PasswordResetOTP.objects.filter(
            user=user,
            otp=entered_otp,
            is_used=False,
        ).order_by("-created_at").first()

        if not otp_record:
            return render(
                request,
                "verify_otp.html",
                {"error": "Invalid verification code. Please check and try again."},
            )

        # Expiry check (10 minutes)
        if otp_record.is_expired(expiry_minutes=10):
            otp_record.is_used = True
            otp_record.save()
            return render(
                request,
                "verify_otp.html",
                {"error": "Verification code has expired. Please request a new OTP."},
            )

        # Mark OTP as successfully used
        otp_record.is_used = True
        otp_record.save()

        # Mark session as verified
        request.session["otp_verified"] = True
        request.session["otp_verified_at"] = timezone.now().isoformat()

        return redirect("reset_password")

    return render(request, "verify_otp.html")


def resend_otp(request):
    """
    Web view: Resend fresh OTP to the admin's email.
    Includes 30-second rate-limiting cooldown.
    """
    user_id = request.session.get("reset_user_id")
    if not user_id:
        return redirect("forgot_password")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect("forgot_password")

    if not (user.is_staff or user.is_superuser):
        return redirect("admin_login")

    # Rate limiting cooldown (30 seconds)
    last_sent_str = request.session.get("last_otp_sent_at")
    if last_sent_str:
        try:
            from django.utils.dateparse import parse_datetime
            last_sent = parse_datetime(last_sent_str)
            if last_sent and (timezone.now() - last_sent).total_seconds() < 30:
                messages.warning(request, "Please wait at least 30 seconds before requesting another code.")
                return redirect("verify_otp")
        except Exception:
            pass

    # Invalidate previous unused OTPs
    PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate and save new OTP
    otp = generate_secure_otp(6)
    PasswordResetOTP.objects.create(user=user, otp=otp)

    # Send email and log to console
    send_admin_password_reset_email(user, otp)

    # Reset attempt count and update timestamp
    request.session["otp_attempts"] = 0
    request.session["last_otp_sent_at"] = timezone.now().isoformat()

    messages.success(request, "A new verification code has been dispatched.")
    return redirect("verify_otp")


def reset_password(request):
    """
    Web view: Reset password for Admin user.
    Enforces enterprise complexity: 8+ chars, uppercase, lowercase, digit, and confirmation match.
    """
    if not request.session.get("otp_verified"):
        messages.error(request, "Please complete OTP verification first.")
        return redirect("forgot_password")

    user_id = request.session.get("reset_user_id")
    if not user_id:
        return redirect("forgot_password")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect("forgot_password")

    if not (user.is_staff or user.is_superuser):
        messages.error(request, "Access denied. Only Administrator accounts can reset password here.")
        return redirect("admin_login")

    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        # Validate Admin password complexity
        is_valid, error_msg = validate_admin_password_complexity(password, confirm_password)
        if not is_valid:
            return render(
                request,
                "reset_password.html",
                {"error": error_msg},
            )

        # Set new password
        user.set_password(password)
        user.save()

        # Invalidate all remaining OTPs for this user
        PasswordResetOTP.objects.filter(user=user).update(is_used=True)

        # Clear password reset session keys
        for key in ["reset_user_id", "otp_verified", "otp_verified_at", "reset_is_admin", "otp_attempts", "last_otp_sent_at"]:
            request.session.pop(key, None)

        messages.success(
            request,
            "Your Admin password has been reset successfully. Please log in with your new credentials.",
        )
        return redirect("admin_login")

    return render(request, "reset_password.html")


# Aliases for explicit admin naming
admin_forgot_password = forgot_password
admin_verify_otp = verify_otp
admin_resend_otp = resend_otp
admin_reset_password = reset_password


# ==========================================================
# ADMIN PASSWORD RECOVERY - REST API ENDPOINTS
# ==========================================================

@csrf_exempt
def admin_password_reset_request_api(request):
    """
    API Endpoint: Request an OTP for Admin password recovery.
    POST /api/admin/password-reset/request/
    Payload: {"identifier": "admin_username_or_email"}
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed. Use POST to request password reset."},
            status=405,
        )

    data = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)
    else:
        data = request.POST.dict()

    identifier = str(data.get("identifier", data.get("username", data.get("email", "")))).strip()
    if not identifier:
        return JsonResponse(
            {"success": False, "message": "Admin username or email is required."},
            status=400,
        )

    # Find user by username or email (case-insensitive)
    user = User.objects.filter(
        models.Q(username__iexact=identifier) | models.Q(email__iexact=identifier)
    ).first()

    if not user:
        return JsonResponse(
            {"success": False, "message": "No account found matching the provided identifier."},
            status=404,
        )

    if not (user.is_staff or user.is_superuser):
        return JsonResponse(
            {"success": False, "message": "Access denied. Only Administrator accounts can recover passwords."},
            status=403,
        )

    # Invalidate previous unused OTPs
    PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate cryptographically secure OTP
    otp = generate_secure_otp(6)
    PasswordResetOTP.objects.create(user=user, otp=otp)

    # Dispatch email and console notice
    send_admin_password_reset_email(user, otp)

    return JsonResponse(
        {
            "success": True,
            "message": "Verification code dispatched to your registered email.",
            "data": {
                "username": user.username,
                "email_masked": mask_email(user.email) if user.email else "",
                "expires_in_minutes": 10,
            },
        },
        status=200,
    )


@csrf_exempt
def admin_password_reset_verify_api(request):
    """
    API Endpoint: Verify 6-digit OTP for Admin password recovery.
    POST /api/admin/password-reset/verify-otp/
    Payload: {"identifier": "admin_username_or_email", "otp": "123456"}
    Returns a signed reset_token on success.
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed. Use POST to verify OTP."},
            status=405,
        )

    data = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)
    else:
        data = request.POST.dict()

    identifier = str(data.get("identifier", data.get("username", data.get("email", "")))).strip()
    entered_otp = str(data.get("otp", "")).strip()

    if not identifier:
        return JsonResponse({"success": False, "message": "Admin identifier is required."}, status=400)
    if not entered_otp:
        return JsonResponse({"success": False, "message": "6-digit OTP is required."}, status=400)

    user = User.objects.filter(
        models.Q(username__iexact=identifier) | models.Q(email__iexact=identifier)
    ).first()

    if not user or not (user.is_staff or user.is_superuser):
        return JsonResponse({"success": False, "message": "Invalid credentials or unauthorized."}, status=403)

    otp_record = PasswordResetOTP.objects.filter(
        user=user,
        otp=entered_otp,
        is_used=False,
    ).order_by("-created_at").first()

    if not otp_record:
        return JsonResponse(
            {"success": False, "message": "Invalid or already used verification code."},
            status=400,
        )

    if otp_record.is_expired(expiry_minutes=10):
        otp_record.is_used = True
        otp_record.save()
        return JsonResponse(
            {"success": False, "message": "Verification code has expired. Please request a new code."},
            status=400,
        )

    # Valid OTP -> Mark used and generate signed reset token
    otp_record.is_used = True
    otp_record.save()

    reset_token = generate_admin_reset_token(user, otp_record.id)

    return JsonResponse(
        {
            "success": True,
            "message": "OTP verified successfully.",
            "data": {
                "reset_token": reset_token,
                "expires_in_minutes": 15,
            },
        },
        status=200,
    )


@csrf_exempt
def admin_password_reset_confirm_api(request):
    """
    API Endpoint: Reset password using signed reset_token.
    POST /api/admin/password-reset/confirm/
    Payload: {"reset_token": "...", "password": "...", "confirm_password": "..."}
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed. Use POST to confirm password reset."},
            status=405,
        )

    data = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)
    else:
        data = request.POST.dict()

    reset_token = str(data.get("reset_token", "")).strip()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password", ""))

    if not reset_token:
        return JsonResponse({"success": False, "message": "Reset token is required."}, status=400)

    user, error_msg = verify_admin_reset_token(reset_token, max_age=900)
    if not user:
        return JsonResponse({"success": False, "message": error_msg or "Invalid reset token."}, status=400)

    is_valid, pwd_err = validate_admin_password_complexity(password, confirm_password)
    if not is_valid:
        return JsonResponse({"success": False, "message": pwd_err}, status=400)

    # Update password
    user.set_password(password)
    user.save()

    # Invalidate all remaining OTPs for this user
    PasswordResetOTP.objects.filter(user=user).update(is_used=True)

    return JsonResponse(
        {
            "success": True,
            "message": "Admin password has been reset successfully. You may now log in with your new credentials.",
        },
        status=200,
    )


@csrf_exempt
def admin_password_reset_resend_api(request):
    """
    API Endpoint: Resend fresh OTP for Admin password recovery.
    POST /api/admin/password-reset/resend-otp/
    Payload: {"identifier": "admin_username_or_email"}
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed. Use POST to resend OTP."},
            status=405,
        )

    data = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)
    else:
        data = request.POST.dict()

    identifier = str(data.get("identifier", data.get("username", data.get("email", "")))).strip()
    if not identifier:
        return JsonResponse({"success": False, "message": "Admin identifier is required."}, status=400)

    user = User.objects.filter(
        models.Q(username__iexact=identifier) | models.Q(email__iexact=identifier)
    ).first()

    if not user or not (user.is_staff or user.is_superuser):
        return JsonResponse({"success": False, "message": "Invalid identifier or unauthorized."}, status=403)

    # Invalidate previous unused OTPs
    PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate fresh OTP
    otp = generate_secure_otp(6)
    PasswordResetOTP.objects.create(user=user, otp=otp)

    # Send email and log to console
    send_admin_password_reset_email(user, otp)

    return JsonResponse(
        {
            "success": True,
            "message": "A new verification code has been dispatched to your email.",
            "data": {
                "email_masked": mask_email(user.email) if user.email else "",
            },
        },
        status=200,
    )



def distributor_register(request):

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        errors = {}

        # ==========================================
        # NAME VALIDATION
        # ==========================================

        if not name:
            errors["name"] = "Full name is required."

        elif len(name) < 2:
            errors["name"] = (
                "Name must contain at least 2 characters."
            )

        elif not all(
            character.isalpha() or character.isspace()
            for character in name
        ):
            errors["name"] = (
                "Name can contain only letters and spaces."
            )


        # ==========================================
        # EMAIL VALIDATION
        # ==========================================

        if not email:
            errors["email"] = (
                "Email address is required."
            )

        elif "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = (
                "Please enter a valid email address."
            )

        elif User.objects.filter(
            email__iexact=email
        ).exists():
            errors["email"] = (
                "An account with this email already exists."
            )


        # ==========================================
        # PHONE VALIDATION
        # ==========================================

        if not phone:
            errors["phone"] = (
                "Phone number is required."
            )

        elif not phone.isdigit():
            errors["phone"] = (
                "Phone number must contain only digits."
            )

        elif len(phone) != 10:
            errors["phone"] = (
                "Phone number must contain exactly 10 digits."
            )


        # ==========================================
        # PASSWORD VALIDATION
        # ==========================================

        if not password:
            errors["password"] = (
                "Password is required."
            )

        elif len(password) < 8:
            errors["password"] = (
                "Password must contain at least 8 characters."
            )

        elif not any(
            character.isupper()
            for character in password
        ):
            errors["password"] = (
                "Password must contain at least one uppercase letter."
            )

        elif not any(
            character.islower()
            for character in password
        ):
            errors["password"] = (
                "Password must contain at least one lowercase letter."
            )

        elif not any(
            character.isdigit()
            for character in password
        ):
            errors["password"] = (
                "Password must contain at least one number."
            )


        # ==========================================
        # CONFIRM PASSWORD
        # ==========================================

        if not confirm_password:

            errors["confirm_password"] = (
                "Please confirm your password."
            )

        elif password != confirm_password:

            errors["confirm_password"] = (
                "Passwords do not match."
            )


        # ==========================================
        # IF VALIDATION ERRORS
        # ==========================================

        if errors:

            return render(
                request,
                "distributor_register.html",
                {
                    "errors": errors,
                    "name": name,
                    "email": email,
                    "phone": phone,
                }
            )


        # ==========================================
        # CREATE DISTRIBUTOR USER
        # ==========================================

        username = email


        # Extra safety check for username
        if User.objects.filter(
            username=username
        ).exists():

            return render(
                request,
                "distributor_register.html",
                {
                    "errors": {
                        "email":
                        "An account with this email already exists."
                    },
                    "name": name,
                    "email": email,
                    "phone": phone,
                }
            )


        # Create Django User

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=name
        )

        user.is_staff = False
        user.is_superuser = False
        user.save()

        DistributorProfile.objects.create(
            user=user,
            phone=phone
        )


        # ==========================================
        # SUCCESS MESSAGE
        # ==========================================

        messages.success(request,"Distributor account created successfully! " "You can now login with your registered email.")


        # ==========================================
        # REDIRECT TO LOGIN
        # ==========================================

        return redirect("distributor_login")


    # ==============================================
    # GET REQUEST
    # ==============================================

    return render(
        request,
        "distributor_register.html"
    )


@login_required
def distributor_profile(request):

    user = request.user

    try:
        profile = user.distributor_profile
    except DistributorProfile.DoesNotExist:
        profile = None

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()

        errors = {}

        # =========================
        # NAME VALIDATION
        # =========================

        if not name:
            errors["name"] = "Full name is required."

        elif len(name) < 2:
            errors["name"] = "Name must contain at least 2 characters."

        elif not all(
            character.isalpha() or character.isspace()
            for character in name
        ):
            errors["name"] = "Name can contain only letters and spaces."

        # =========================
        # EMAIL VALIDATION
        # =========================

        if not email:
            errors["email"] = "Email address is required."

        elif "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Please enter a valid email address."

        elif User.objects.filter(
            email__iexact=email
        ).exclude(
            id=user.id
        ).exists():
            errors["email"] = "This email is already registered."

        # =========================
        # PHONE VALIDATION
        # =========================

        if not phone:
            errors["phone"] = "Phone number is required."

        elif not phone.isdigit():
            errors["phone"] = "Phone number must contain only digits."

        elif len(phone) != 10:
            errors["phone"] = "Phone number must contain exactly 10 digits."

        # =========================
        # IF VALIDATION FAILS
        # =========================

        if errors:

            return render(
                request,
                "distributor_profile.html",
                {
                    "user": user,
                    "profile": profile,
                    "errors": errors,
                    "form_name": name,
                    "form_email": email,
                    "form_phone": phone,
                    "edit_mode": True,
                }
            )

        # =========================
        # UPDATE USER
        # =========================

        user.first_name = name
        user.email = email

        # Username is being used as email in Task 8
        user.username = email

        user.save()

        # =========================
        # UPDATE PROFILE
        # =========================

        if profile:
            profile.phone = phone
            profile.save()

        else:
            DistributorProfile.objects.create(
                user=user,
                phone=phone
            )

        # =========================
        # SUCCESS MESSAGE
        # =========================

        messages.success(
            request,
            "Profile updated successfully."
        )

        return redirect("distributor_profile")

    # =========================
    # GET REQUEST
    # =========================

    return render(
        request,
        "distributor_profile.html",
        {
            "user": user,
            "profile": profile,
            "edit_mode": request.GET.get("edit") == "1",
        }
    )


@login_required
def add_customer(request):

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        pincode = request.POST.get("pincode", "").strip()

        errors = {}

        # =========================
        # NAME VALIDATION
        # =========================

        if not name:
            errors["name"] = "Customer name is required."

        elif len(name) < 2:
            errors["name"] = "Name must contain at least 2 characters."

        elif not all(
            character.isalpha() or character.isspace()
            for character in name
        ):
            errors["name"] = "Name can contain only letters and spaces."

        # =========================
        # EMAIL VALIDATION
        # =========================

        if not email:
            errors["email"] = "Email address is required."

        elif "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Please enter a valid email address."

        # =========================
        # PHONE VALIDATION
        # =========================

        if not phone:
            errors["phone"] = "Phone number is required."

        elif not phone.isdigit():
            errors["phone"] = "Phone number must contain only digits."

        elif len(phone) != 10:
            errors["phone"] = "Phone number must contain exactly 10 digits."

        # =========================
        # ADDRESS VALIDATION
        # =========================

        if not address:
            errors["address"] = "Address is required."

        elif len(address) < 5:
            errors["address"] = "Please enter a valid address."

        # =========================
        # CITY VALIDATION
        # =========================

        if not city:
            errors["city"] = "City is required."

        elif len(city) < 2:
            errors["city"] = "Please enter a valid city."

        # =========================
        # STATE VALIDATION
        # =========================

        if not state:
            errors["state"] = "State is required."

        elif len(state) < 2:
            errors["state"] = "Please enter a valid state."

        # =========================
        # PINCODE VALIDATION
        # =========================

        if not pincode:
            errors["pincode"] = "Pincode is required."

        elif not pincode.isdigit():
            errors["pincode"] = "Pincode must contain only digits."

        elif len(pincode) != 6:
            errors["pincode"] = "Pincode must contain exactly 6 digits."

        # =========================
        # VALIDATION FAILED
        # =========================

        if errors:

            return render(
                request,
                "add_customer.html",
                {
                    "errors": errors,
                    "form_name": name,
                    "form_email": email,
                    "form_phone": phone,
                    "form_address": address,
                    "form_city": city,
                    "form_state": state,
                    "form_pincode": pincode,
                }
            )

        # =========================
        # SAVE CUSTOMER
        # =========================

        Customer.objects.create(
            name=name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            state=state,
            pincode=pincode,
        )

        # =========================
        # SUCCESS MESSAGE
        # =========================

        messages.success(
            request,
            f"Customer '{name}' added successfully."
        )

        return redirect("add_customer")

    return render(
        request,
        "add_customer.html"
    )


@login_required
def customer_list(request):

    search_query = request.GET.get("search", "").strip()

    customers = Customer.objects.all()

    if search_query:
        customers = customers.filter(
            models.Q(name__icontains=search_query)
            | models.Q(email__icontains=search_query)
            | models.Q(phone__icontains=search_query)
            | models.Q(city__icontains=search_query)
            | models.Q(state__icontains=search_query)
            | models.Q(pincode__icontains=search_query)
        )

    context = {
        "customers": customers,
        "search_query": search_query,
        "total_customers": Customer.objects.count(),
        "showing_customers": customers.count(),
    }

    return render(
        request,
        "customer_list.html",
        context
    )

@login_required
def edit_customer(request, customer_id):

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, "Customer not found.")
        return redirect("customer_list")

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        pincode = request.POST.get("pincode", "").strip()

        errors = {}

        # Name validation
        if not name:
            errors["name"] = "Customer name is required."
        elif len(name) < 2:
            errors["name"] = "Name must contain at least 2 characters."
        elif not all(
            character.isalpha() or character.isspace()
            for character in name
        ):
            errors["name"] = "Name can contain only letters and spaces."

        # Email validation
        if not email:
            errors["email"] = "Email address is required."
        elif "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Please enter a valid email address."

        # Phone validation
        if not phone:
            errors["phone"] = "Phone number is required."
        elif not phone.isdigit():
            errors["phone"] = "Phone number must contain only digits."
        elif len(phone) != 10:
            errors["phone"] = "Phone number must contain exactly 10 digits."

        # Address validation
        if not address:
            errors["address"] = "Address is required."
        elif len(address) < 5:
            errors["address"] = "Please enter a valid address."

        # City validation
        if not city:
            errors["city"] = "City is required."
        elif len(city) < 2:
            errors["city"] = "Please enter a valid city."

        # State validation
        if not state:
            errors["state"] = "State is required."
        elif len(state) < 2:
            errors["state"] = "Please enter a valid state."

        # Pincode validation
        if not pincode:
            errors["pincode"] = "Pincode is required."
        elif not pincode.isdigit():
            errors["pincode"] = "Pincode must contain only digits."
        elif len(pincode) != 6:
            errors["pincode"] = "Pincode must contain exactly 6 digits."

        # If validation errors
        if errors:
            return render(
                request,
                "edit_customer.html",
                {
                    "customer": customer,
                    "errors": errors,
                    "form_name": name,
                    "form_email": email,
                    "form_phone": phone,
                    "form_address": address,
                    "form_city": city,
                    "form_state": state,
                    "form_pincode": pincode,
                }
            )

        # Update customer
        customer.name = name
        customer.email = email
        customer.phone = phone
        customer.address = address
        customer.city = city
        customer.state = state
        customer.pincode = pincode

        customer.save()

        messages.success(
            request,
            f"Customer '{name}' updated successfully."
        )

        return redirect("customer_list")

    # GET request
    return render(
        request,
        "edit_customer.html",
        {
            "customer": customer
        }
    )

@login_required
def delete_customer(request, customer_id):

    if request.method != "POST":
        return redirect("customer_list")

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        messages.error(request, "Customer not found.")
        return redirect("customer_list")

    customer_name = customer.name

    customer.delete()

    messages.success(
        request,
        f"Customer '{customer_name}' deleted successfully."
    )

    return redirect("customer_list")


@login_required
def add_product(request):

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        category = request.POST.get("category", "").strip()
        price = request.POST.get("price", "").strip()
        stock = request.POST.get("stock", "").strip()
        gst_rate = request.POST.get("gst_rate", "").strip()
        description = request.POST.get("description", "").strip()

        errors = {}

        # ================= NAME VALIDATION =================

        if not name:
            errors["name"] = "Product name is required."

        elif len(name) < 2:
            errors["name"] = (
                "Product name must contain at least 2 characters."
            )

        # ================= CATEGORY VALIDATION =================

        valid_categories = [
            value
            for value, label in Product.CATEGORY_CHOICES
        ]

        if not category:
            errors["category"] = "Please select a category."

        elif category not in valid_categories:
            errors["category"] = "Please select a valid category."

        # ================= PRICE VALIDATION =================

        price_value = None

        if not price:
            errors["price"] = "Price is required."

        else:
            try:
                price_value = float(price)

                if price_value <= 0:
                    errors["price"] = "Price must be greater than 0."

            except ValueError:
                errors["price"] = "Please enter a valid price."

        # ================= STOCK VALIDATION =================

        stock_value = None

        if not stock:
            errors["stock"] = "Stock quantity is required."

        else:
            try:
                stock_value = int(stock)

                if stock_value < 0:
                    errors["stock"] = (
                        "Stock cannot be negative."
                    )

            except ValueError:
                errors["stock"] = (
                    "Stock must be a valid whole number."
                )

        # ================= GST VALIDATION =================

        gst_value = None

        if not gst_rate:
            errors["gst_rate"] = "GST rate is required."

        else:
            try:
                gst_value = float(gst_rate)

                if gst_value < 0:
                    errors["gst_rate"] = (
                        "GST rate cannot be negative."
                    )

                elif gst_value > 100:
                    errors["gst_rate"] = (
                        "GST rate cannot be greater than 100%."
                    )

            except ValueError:
                errors["gst_rate"] = (
                    "Please enter a valid GST rate."
                )

        # ================= SAVE =================

        if errors:

            return render(
                request,
                "add_product.html",
                {
                    "errors": errors,
                    "form_name": name,
                    "form_category": category,
                    "form_price": price,
                    "form_stock": stock,
                    "form_gst_rate": gst_rate,
                    "form_description": description,
                    "categories": Product.CATEGORY_CHOICES,
                }
            )

        Product.objects.create(
            name=name,
            category=category,
            price=price_value,
            stock=stock_value,
            gst_rate=gst_value,
            description=description,
        )

        messages.success(
            request,
            f"Product '{name}' added successfully."
        )

        return redirect("add_product")

    return render(
        request,
        "add_product.html",
        {
            "categories": Product.CATEGORY_CHOICES,
        }
    )

@login_required
def product_list(request):

    search_query = request.GET.get("search", "").strip()

    products = Product.objects.all()

    # ================= SEARCH =================

    if search_query:
        products = products.filter(
            models.Q(name__icontains=search_query)
            | models.Q(category__icontains=search_query)
            | models.Q(description__icontains=search_query)
        )

    # ================= PAGINATION =================

    paginator = Paginator(products, 8)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    context = {
        "products": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "total_products": Product.objects.count(),
        "showing_products": products.count(),
    }

    return render(
        request,
        "product_list.html",
        context
    )

@login_required
def edit_product(request, product_id):

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect("product_list")

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        category = request.POST.get("category", "").strip()
        price = request.POST.get("price", "").strip()
        stock = request.POST.get("stock", "").strip()
        gst_rate = request.POST.get("gst_rate", "").strip()
        description = request.POST.get("description", "").strip()

        errors = {}

        valid_categories = [
            value
            for value, label in Product.CATEGORY_CHOICES
        ]

        # -----------------------------
        # PRODUCT NAME VALIDATION
        # -----------------------------

        if not name:
            errors["name"] = "Product name is required."

        elif len(name) < 2:
            errors["name"] = (
                "Product name must contain at least 2 characters."
            )

        # -----------------------------
        # CATEGORY VALIDATION
        # -----------------------------

        if not category:
            errors["category"] = "Please select a category."

        elif category not in valid_categories:
            errors["category"] = "Please select a valid category."

        # -----------------------------
        # PRICE VALIDATION
        # -----------------------------

        price_value = None

        if not price:
            errors["price"] = "Price is required."

        else:
            try:
                price_value = float(price)

                if price_value <= 0:
                    errors["price"] = (
                        "Price must be greater than 0."
                    )

            except ValueError:
                errors["price"] = (
                    "Please enter a valid price."
                )

        # -----------------------------
        # STOCK VALIDATION
        # -----------------------------

        stock_value = None

        if not stock:
            errors["stock"] = "Stock quantity is required."

        else:
            try:
                stock_value = int(stock)

                if stock_value < 0:
                    errors["stock"] = (
                        "Stock cannot be negative."
                    )

            except ValueError:
                errors["stock"] = (
                    "Stock must be a valid whole number."
                )

        # -----------------------------
        # GST VALIDATION
        # -----------------------------

        gst_value = None

        if not gst_rate:
            errors["gst_rate"] = (
                "GST rate is required."
            )

        else:
            try:
                gst_value = float(gst_rate)

                if gst_value < 0:
                    errors["gst_rate"] = (
                        "GST rate cannot be negative."
                    )

                elif gst_value > 100:
                    errors["gst_rate"] = (
                        "GST rate cannot be greater than 100%."
                    )

            except ValueError:
                errors["gst_rate"] = (
                    "Please enter a valid GST rate."
                )

        # -----------------------------
        # SHOW ERRORS
        # -----------------------------

        if errors:

            return render(
                request,
                "edit_product.html",
                {
                    "product": product,
                    "errors": errors,

                    "form_name": name,
                    "form_category": category,
                    "form_price": price,
                    "form_stock": stock,
                    "form_gst_rate": gst_rate,
                    "form_description": description,

                    "categories": Product.CATEGORY_CHOICES,
                }
            )

        # -----------------------------
        # UPDATE PRODUCT
        # -----------------------------

        product.name = name
        product.category = category
        product.price = price_value
        product.stock = stock_value
        product.gst_rate = gst_value
        product.description = description

        product.save()

        messages.success(
            request,
            f"Product '{name}' updated successfully."
        )

        return redirect("product_list")

    # -----------------------------
    # GET REQUEST
    # PRE-FILLED FORM
    # -----------------------------

    return render(
        request,
        "edit_product.html",
        {
            "product": product,
            "categories": Product.CATEGORY_CHOICES,
        }
    )

@login_required
def delete_product(request, product_id):

    if request.method != "POST":
        return redirect("product_list")

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        messages.error(request, "Product not found.")
        return redirect("product_list")

    product_name = product.name

    product.delete()

    messages.success(
        request,
        f"Product '{product_name}' deleted successfully."
    )

    return redirect("product_list")


@login_required
def create_invoice(request):
    customers = Customer.objects.all().order_by("name")
    products = Product.objects.all().order_by("name")

    if request.method == "POST":
        customer_id = request.POST.get("customer")
        payment_status = request.POST.get("payment_status", "Pending")
        notes = request.POST.get("notes", "").strip()
        items_json = request.POST.get("items_json", "")

        errors = []

        # Validate customer
        try:
            customer = Customer.objects.get(id=int(customer_id))
        except (Customer.DoesNotExist, TypeError, ValueError):
            customer = None
            errors.append("Please select a valid customer.")

        # Validate payment status
        valid_statuses = [
            value for value, label in Invoice.PAYMENT_STATUS_CHOICES
        ]

        if payment_status not in valid_statuses:
            errors.append("Please select a valid payment status.")

        # Validate product rows
        try:
            submitted_items = json.loads(items_json)
            if not isinstance(submitted_items, list) or not submitted_items:
                errors.append("Please add at least one product.")
        except (json.JSONDecodeError, TypeError):
            submitted_items = []
            errors.append("Invalid product data. Please try again.")

        prepared_items = []
        subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_gst = Decimal("0.00")

        if not errors:
            for row in submitted_items:
                try:
                    product_id = int(row.get("product_id"))
                    quantity = int(row.get("quantity"))
                    discount_type = row.get("discount_type", "amount")
                    discount_value = Decimal(str(row.get("discount_value", "0")))

                    product = Product.objects.get(id=product_id)

                    if quantity <= 0:
                        errors.append(
                            f"Quantity for {product.name} must be greater than zero."
                        )
                        continue

                    if quantity > product.stock:
                        errors.append(
                            f"Insufficient stock for {product.name}. "
                            f"Available stock: {product.stock}."
                        )
                        continue

                    if discount_value < 0:
                        errors.append("Discount cannot be negative.")
                        continue

                    unit_price = product.price
                    gst_rate = product.gst_rate

                    line_subtotal = (
                        unit_price * quantity
                    ).quantize(Decimal("0.01"))

                    if discount_type == "percent":
                        if discount_value > 100:
                            errors.append("Percentage discount cannot exceed 100%.")
                            continue

                        line_discount = (
                            line_subtotal * discount_value / Decimal("100")
                        ).quantize(Decimal("0.01"))

                    elif discount_type == "amount":
                        line_discount = discount_value.quantize(
                            Decimal("0.01")
                        )

                    else:
                        errors.append("Invalid discount type.")
                        continue

                    if line_discount > line_subtotal:
                        errors.append(
                            f"Discount cannot exceed subtotal for {product.name}."
                        )
                        continue

                    taxable_amount = line_subtotal - line_discount

                    line_gst = (
                        taxable_amount * gst_rate / Decimal("100")
                    ).quantize(Decimal("0.01"))

                    line_total = taxable_amount + line_gst

                    prepared_items.append({
                        "product": product,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "gst_rate": gst_rate,
                        "subtotal": line_subtotal,
                        "discount": line_discount,
                        "gst_amount": line_gst,
                        "total_price": line_total,
                    })

                    subtotal += line_subtotal
                    total_discount += line_discount
                    total_gst += line_gst

                except (Product.DoesNotExist, TypeError, ValueError, InvalidOperation):
                    errors.append("Invalid product, quantity, or discount value.")

            if not prepared_items and not errors:
                errors.append("Please add at least one valid product.")

        if errors:
            for error in errors:
                messages.error(request, error)

            return render(
                request,
                "create_invoice.html",
                {
                    "customers": customers,
                    "products": products,
                    "form_customer": customer_id,
                    "form_payment_status": payment_status,
                    "form_notes": notes,
                    "payment_status_choices": Invoice.PAYMENT_STATUS_CHOICES,
                },
            )

        grand_total = subtotal - total_discount + total_gst

        # Save invoice and items together, so partial invoices are not saved.
        try:
            with transaction.atomic():
                last_invoice = (
                    Invoice.objects.select_for_update()
                    .order_by("-id")
                    .first()
                )

                next_number = (
                    last_invoice.id + 1 if last_invoice else 1
                )
                invoice_number = f"INV-{next_number:06d}"

                # Avoid collision if invoice numbers have gaps.
                while Invoice.objects.filter(
                    invoice_number=invoice_number
                ).exists():
                    next_number += 1
                    invoice_number = f"INV-{next_number:06d}"

                invoice = Invoice.objects.create(
                    invoice_number=invoice_number,
                    customer=customer,
                    subtotal=subtotal,
                    gst_amount=total_gst,
                    grand_total=grand_total,
                    payment_status=payment_status,
                    notes=notes,
                )

                for item in prepared_items:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        product=item["product"],
                        quantity=item["quantity"],
                        unit_price=item["unit_price"],
                        gst_rate=item["gst_rate"],
                        gst_amount=item["gst_amount"],
                        total_price=item["total_price"],
                    )

                    # Reduce stock for the sold quantity.
                    product = Product.objects.select_for_update().get(
                        id=item["product"].id
                    )

                    if product.stock < item["quantity"]:
                        raise ValueError(
                            f"Stock changed for {product.name}. "
                            "Please try again."
                        )

                    product.stock -= item["quantity"]
                    product.save(update_fields=["stock", "updated_at"])

        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))
            return redirect("create_invoice")

        messages.success(
            request,
            f"Invoice {invoice.invoice_number} created successfully!"
        )
        return redirect("invoice_list")

    return render(
        request,
        "create_invoice.html",
        {
            "customers": customers,
            "products": products,
            "payment_status_choices": Invoice.PAYMENT_STATUS_CHOICES,
        },
    )


# ==========================================================
# INVOICE LIST VIEW (FETCH ALL EXISTING INVOICES WITH PAGINATION & QR)
# ==========================================================

@login_required
def invoice_list(request):
    """
    Fetches all existing invoice data from the database,
    provides search, status filter, summary statistics,
    QR code generation for each invoice, and pagination.
    """
    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "").strip()

    # Query all invoices with related customer and items
    invoices = (
        Invoice.objects.select_related("customer")
        .prefetch_related("items__product")
        .all()
        .order_by("-invoice_date")
    )

    # Search filter by Invoice Number, Customer Name, Phone, Email
    if search_query:
        invoices = invoices.filter(
            models.Q(invoice_number__icontains=search_query)
            | models.Q(customer__name__icontains=search_query)
            | models.Q(customer__phone__icontains=search_query)
            | models.Q(customer__email__icontains=search_query)
        )

    # Status filter
    valid_statuses = [choice[0] for choice in Invoice.PAYMENT_STATUS_CHOICES]
    if status_filter in valid_statuses:
        invoices = invoices.filter(payment_status=status_filter)

    # Calculate overall statistics
    all_invoices = Invoice.objects.all()
    total_invoices_count = all_invoices.count()
    total_revenue = all_invoices.aggregate(total=models.Sum("grand_total"))["total"] or Decimal("0.00")
    paid_count = all_invoices.filter(payment_status="Paid").count()
    pending_count = all_invoices.filter(payment_status="Pending").count()

    # Pagination: 8 invoices per page
    paginator = Paginator(invoices, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Attach generated QR code (base64) to each invoice in the current page
    for inv in page_obj:
        inv.qr_base64 = inv.generate_qr_base64()

    context = {
        "page_obj": page_obj,
        "invoices": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "total_invoices": total_invoices_count,
        "showing_invoices": invoices.count(),
        "total_revenue": total_revenue,
        "paid_count": paid_count,
        "pending_count": pending_count,
        "payment_status_choices": Invoice.PAYMENT_STATUS_CHOICES,
    }

    return render(request, "invoice_list.html", context)


# ==========================================================
# INVOICE DETAIL VIEW
# ==========================================================

@login_required
def invoice_detail(request, invoice_id):
    """
    View a single invoice with full customer information,
    product breakdown, summary totals, and large QR code.
    """
    try:
        invoice = (
            Invoice.objects.select_related("customer")
            .prefetch_related("items__product")
            .get(id=invoice_id)
        )
    except Invoice.DoesNotExist:
        messages.error(request, "Invoice not found.")
        return redirect("invoice_list")

    qr_code = invoice.generate_qr_base64()

    return render(
        request,
        "invoice_detail.html",
        {
            "invoice": invoice,
            "qr_code": qr_code,
        },
    )


# ==========================================================
# INVOICE PDF DOWNLOAD / VIEW
# ==========================================================

@login_required
def invoice_pdf_view(request, invoice_id):
    """
    Generate and stream or download a PDF invoice with embedded QR code.
    """
    try:
        invoice = (
            Invoice.objects.select_related("customer")
            .prefetch_related("items__product")
            .get(id=invoice_id)
        )
    except Invoice.DoesNotExist:
        messages.error(request, "Invoice not found.")
        return redirect("invoice_list")

    from .utils import render_to_pdf

    qr_code = invoice.generate_qr_base64()

    pdf_bytes = render_to_pdf(
        "invoice_pdf.html",
        {
            "invoice": invoice,
            "qr_code": qr_code,
        },
    )

    if not pdf_bytes:
        messages.error(request, "Unable to generate invoice PDF.")
        return redirect("invoice_list")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    download = request.GET.get("download")
    disposition = "attachment" if download == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{invoice.invoice_number}.pdf"'
    return response


# ==========================================================
# INVOICE RAW QR CODE IMAGE STREAM
# ==========================================================

@login_required
def invoice_qr_image(request, invoice_id):
    """
    Stream raw PNG image of the invoice QR code.
    """
    try:
        invoice = (
            Invoice.objects.select_related("customer")
            .prefetch_related("items__product")
            .get(id=invoice_id)
        )
    except Invoice.DoesNotExist:
        return HttpResponse("Invoice not found", status=404)

    from .utils import generate_invoice_qr_bytes

    qr_bytes = generate_invoice_qr_bytes(invoice)
    return HttpResponse(qr_bytes, content_type="image/png")