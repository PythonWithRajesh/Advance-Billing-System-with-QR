from django.urls import path
from . import views


urlpatterns = [

    # Admin
    path(
        "admin-login/",
        views.admin_login,
        name="admin_login"
    ),

    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),

    # Distributor
    path(
        "distributor-login/",
        views.distributor_login,
        name="distributor_login"
    ),
    path(
        "distributor-register/",
        views.distributor_register,
        name="distributor_register"
    ),

    path(
        "distributor-profile/",
        views.distributor_profile,
        name="distributor_profile"
    ),

    path(
        "distributor-dashboard/",
        views.distributor_dashboard,
        name="distributor_dashboard"
    ),

    # Logout
    path(
        "logout/",
        views.user_logout,
        name="user_logout"
    ),

    # Forgot Password
    path(
        "forgot-password/",
        views.forgot_password,
        name="forgot_password"
    ),

    path(
        "verify-otp/",
        views.verify_otp,
        name="verify_otp"
    ),

    path(
        "resend-otp/",
        views.resend_otp,
        name="resend_otp"
    ),

    path(
        "reset-password/",
        views.reset_password,
        name="reset_password"
    ),

    path(
        "add-customer/",
        views.add_customer,
        name="add_customer"
    ),

    path(
        "customers/",
        views.customer_list,
        name="customer_list"
    ),

    path(
        "customers/edit/<int:customer_id>/",
        views.edit_customer,
        name="edit_customer"
    ),

    path(
        "customers/delete/<int:customer_id>/",
        views.delete_customer,
        name="delete_customer"
    ),

    path(
        "add-product/",
        views.add_product,
        name="add_product"
    ),

    path(
        "products/",
        views.product_list,
        name="product_list"
    ),

    path(
        "products/edit/<int:product_id>/",
        views.edit_product,
        name="edit_product"
    ),

    path(
        "products/delete/<int:product_id>/",
        views.delete_product,
        name="delete_product"
    ),

    path(
        "invoices/create/",
        views.create_invoice,
        name="create_invoice",
    ),
]