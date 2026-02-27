from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm


@login_required
def profile_view(request):
    profile = getattr(request.user, "profile", None)

    # In case any old user exists without profile
    if profile is None:
        from .models import Profile
        profile = Profile.objects.create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    return render(request, "accounts/profile.html", {"form": form})


def _redirect_after_login(user):
    # Admin/staff go to frontend admin dashboard
    if user.is_staff:
        return redirect("control:dashboard")
    # Normal users
    return redirect("menu:home")


def login_view(request):
    # If already logged in, route correctly
    if request.user.is_authenticated:
        return _redirect_after_login(request.user)

    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        user = authenticate(request, username=email, password=password)
        if user is None:
            error = "Invalid email or password."
        else:
            login(request, user)
            return _redirect_after_login(user)

    return render(request, "accounts/login.html", {"error": error})


def register_view(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request.user)

    error = None

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        if not full_name or not email or not phone or not password1 or not password2:
            error = "Please fill all fields."
        elif password1 != password2:
            error = "Passwords do not match."
        elif User.objects.filter(username=email).exists():
            error = "An account with this email already exists."
        else:
            user = User.objects.create_user(username=email, email=email, password=password1)
            user.first_name = full_name
            user.save()

            # profile is auto-created by signal
            user.profile.phone = phone
            user.profile.save()

            login(request, user)
            return _redirect_after_login(user)

    return render(request, "accounts/register.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("menu:home")