from django.shortcuts import render, redirect

# Create your views here.



def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Task 2 માટે basic UI login
        if username == "admin" and password == "admin123":
            request.session["admin_logged_in"] = True
            return redirect("admin_dashboard")

        return render(
            request,
            "admin_login.html",
            {
                "error": "Invalid admin username or password."
            }
        )

    return render(request, "admin_login.html")


def distributor_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Task 2 માટે basic UI login
        if username == "distributor" and password == "dist123":
            request.session["distributor_logged_in"] = True
            return redirect("distributor_dashboard")

        return render(
            request,
            "distributor_login.html",
            {
                "error": "Invalid distributor username or password."
            }
        )

    return render(request, "distributor_login.html")


def admin_dashboard(request):
    if not request.session.get("admin_logged_in"):
        return redirect("admin_login")

    return render(request, "admin_dashboard.html")


def distributor_dashboard(request):
    if not request.session.get("distributor_logged_in"):
        return redirect("distributor_login")

    return render(request, "distributor_dashboard.html")