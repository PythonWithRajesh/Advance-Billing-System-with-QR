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
from django.core.paginator import Paginator

import json
from decimal import Decimal, InvalidOperation
from django.db import transaction

from .models import PasswordResetOTP, DistributorProfile, Customer, Product, Invoice, InvoiceItem

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
        total_gst = Decimal("0.00")

        if not errors:
            for row in submitted_items:
                try:
                    product_id = int(row.get("product_id"))
                    quantity = int(row.get("quantity"))

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

                    unit_price = product.price
                    gst_rate = product.gst_rate

                    line_subtotal = unit_price * quantity
                    line_gst = (
                        line_subtotal * gst_rate / Decimal("100")
                    ).quantize(Decimal("0.01"))

                    line_total = line_subtotal + line_gst

                    prepared_items.append({
                        "product": product,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "gst_rate": gst_rate,
                        "gst_amount": line_gst,
                        "total_price": line_total,
                    })

                    subtotal += line_subtotal
                    total_gst += line_gst

                except (Product.DoesNotExist, TypeError, ValueError):
                    errors.append(
                        "One of the selected products is invalid."
                    )
                except (InvalidOperation, ArithmeticError):
                    errors.append(
                        "Unable to calculate a product total."
                    )

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
                },
            )

        grand_total = subtotal + total_gst

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
        return redirect("create_invoice")

    return render(
        request,
        "create_invoice.html",
        {
            "customers": customers,
            "products": products,
            "payment_status_choices": Invoice.PAYMENT_STATUS_CHOICES,
        },
    )