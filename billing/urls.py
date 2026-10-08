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
]