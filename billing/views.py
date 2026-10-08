from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
import random
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import redirect, render


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

        username = request.POST.get("username", "").strip()

        if not username:
            return render(
                request,
                "forgot_password.html",
                {
                    "error": "Please enter your username."
                }
            )

        try:
            user = User.objects.get(username=username)

            # Generate 6 digit OTP
            otp = str(random.randint(100000, 999999))

            # Store OTP in session
            request.session["reset_user_id"] = user.id
            request.session["reset_otp"] = otp

            # OTP expiry: 5 minutes
            request.session["otp_created_at"] = (
                __import__("time").time()
            )

            # Development purpose
            print("=" * 50)
            print(f"PASSWORD RESET OTP for {username}: {otp}")
            print("=" * 50)

            return redirect("verify_otp")

        except User.DoesNotExist:

            return render(
                request,
                "forgot_password.html",
                {
                    "error": "No account found with this username."
                }
            )

    return render(
        request,
        "forgot_password.html"
    )


def verify_otp(request):
    if "reset_user_id" not in request.session:
        return redirect("forgot_password")

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()
        stored_otp = request.session.get("reset_otp")

        if entered_otp == stored_otp:

            request.session["otp_verified"] = True

            return redirect("reset_password")

        return render(
            request,
            "verify_otp.html",
            {
                "error": "Invalid OTP. Please try again."
            }
        )

    return render(
        request,
        "verify_otp.html"
    )


def resend_otp(request):

    user_id = request.session.get("reset_user_id")

    if not user_id:
        return redirect("forgot_password")

    try:

        user = User.objects.get(id=user_id)

        # Generate new OTP
        otp = str(random.randint(100000, 999999))

        request.session["reset_otp"] = otp
        request.session["otp_created_at"] = (
            __import__("time").time()
        )

        print("=" * 50)
        print(f"NEW PASSWORD RESET OTP for {user.username}: {otp}")
        print("=" * 50)

        messages.success(
            request,
            "A new OTP has been generated."
        )

        return redirect("verify_otp")

    except User.DoesNotExist:

        return redirect("forgot_password")


def reset_password(request):

    if not request.session.get("otp_verified"):
        return redirect("forgot_password")

    user_id = request.session.get("reset_user_id")

    try:
        user = User.objects.get(id=user_id)

    except User.DoesNotExist:
        return redirect("forgot_password")

    if request.method == "POST":

        password = request.POST.get("password")
        confirm_password = request.POST.get(
            "confirm_password"
        )

        if not password or not confirm_password:

            return render(
                request,
                "reset_password.html",
                {
                    "error": "Please fill both password fields."
                }
            )

        if password != confirm_password:

            return render(
                request,
                "reset_password.html",
                {
                    "error": "Passwords do not match."
                }
            )

        if len(password) < 6:

            return render(
                request,
                "reset_password.html",
                {
                    "error": "Password must contain at least 6 characters."
                }
            )

        user.set_password(password)
        user.save()

        # Clear reset session data
        request.session.pop("reset_user_id", None)
        request.session.pop("reset_otp", None)
        request.session.pop("otp_created_at", None)
        request.session.pop("otp_verified", None)

        messages.success(
            request,
            "Password reset successfully. Please login."
        )

        return redirect("admin_login")

    return render(
        request,
        "reset_password.html"
    )