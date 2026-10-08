from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


import random
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import PasswordResetOTP, DistributorProfile, Customer

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


def forgot_password(request):

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        if not username:

            return render(
                request,
                "forgot_password.html",
                {
                    "error": "Please enter your username."
                }
            )

        try:

            user = User.objects.get(
                username=username
            )

        except User.DoesNotExist:

            return render(
                request,
                "forgot_password.html",
                {
                    "error": "No account found with this username."
                }
            )

        # Invalidate previous unused OTPs
        PasswordResetOTP.objects.filter(
            user=user,
            is_used=False
        ).update(
            is_used=True
        )

        # Generate random 6 digit OTP
        otp = str(
            random.randint(
                100000,
                999999
            )
        )

        # Save OTP in database
        PasswordResetOTP.objects.create(
            user=user,
            otp=otp
        )

        # Store user ID in session
        request.session["reset_user_id"] = user.id

        # Development purpose
        print("=" * 50)
        print(
            f"PASSWORD RESET OTP for "
            f"{user.username}: {otp}"
        )
        print("=" * 50)

        return redirect("verify_otp")

    return render(
        request,
        "forgot_password.html"
    )


def verify_otp(request):

    user_id = request.session.get(
        "reset_user_id"
    )

    if not user_id:

        return redirect(
            "forgot_password"
        )

    if request.method == "POST":

        entered_otp = request.POST.get(
            "otp",
            ""
        ).strip()

        if not entered_otp:

            return render(
                request,
                "verify_otp.html",
                {
                    "error": "Please enter the OTP."
                }
            )

        try:

            otp_record = PasswordResetOTP.objects.filter(
                user_id=user_id,
                otp=entered_otp,
                is_used=False
            ).latest(
                "created_at"
            )

        except PasswordResetOTP.DoesNotExist:

            return render(
                request,
                "verify_otp.html",
                {
                    "error": "Invalid or already used OTP."
                }
            )

        # OTP expiry = 5 minutes
        expiry_time = (
            otp_record.created_at
            + timedelta(minutes=5)
        )

        if timezone.now() > expiry_time:

            otp_record.is_used = True
            otp_record.save()

            return render(
                request,
                "verify_otp.html",
                {
                    "error": "OTP has expired. Please request a new OTP."
                }
            )

        # OTP is valid
        otp_record.is_used = True
        otp_record.save()

        request.session["otp_verified"] = True

        return redirect(
            "reset_password"
        )

    return render(
        request,
        "verify_otp.html"
    )

def resend_otp(request):

    user_id = request.session.get(
        "reset_user_id"
    )

    if not user_id:

        return redirect(
            "forgot_password"
        )

    try:

        user = User.objects.get(
            id=user_id
        )

    except User.DoesNotExist:

        return redirect(
            "forgot_password"
        )

    # Disable previous OTPs
    PasswordResetOTP.objects.filter(
        user=user,
        is_used=False
    ).update(
        is_used=True
    )

    # Generate new OTP
    otp = str(
        random.randint(
            100000,
            999999
        )
    )

    # Save new OTP
    PasswordResetOTP.objects.create(
        user=user,
        otp=otp
    )

    print("=" * 50)
    print(
        f"NEW PASSWORD RESET OTP for "
        f"{user.username}: {otp}"
    )
    print("=" * 50)

    messages.success(
        request,
        "A new OTP has been generated."
    )

    return redirect(
        "verify_otp"
    )

def reset_password(request):

    if not request.session.get(
        "otp_verified"
    ):
        return redirect(
            "forgot_password"
        )

    user_id = request.session.get(
        "reset_user_id"
    )

    try:

        user = User.objects.get(
            id=user_id
        )

    except User.DoesNotExist:

        return redirect(
            "forgot_password"
        )

    if request.method == "POST":

        password = request.POST.get(
            "password"
        )

        confirm_password = request.POST.get(
            "confirm_password"
        )

        if not password or not confirm_password:

            return render(
                request,
                "reset_password.html",
                {
                    "error":
                    "Please fill both password fields."
                }
            )

        if password != confirm_password:

            return render(
                request,
                "reset_password.html",
                {
                    "error":
                    "Passwords do not match."
                }
            )

        if len(password) < 6:

            return render(
                request,
                "reset_password.html",
                {
                    "error":
                    "Password must contain at least 6 characters."
                }
            )

        user.set_password(password)
        user.save()

        # Clear password reset session
        request.session.pop(
            "reset_user_id",
            None
        )

        request.session.pop(
            "otp_verified",
            None
        )

        messages.success(
            request,
            "Password reset successfully. Please login."
        )

        return redirect(
            "admin_login"
        )

    return render(
        request,
        "reset_password.html"
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