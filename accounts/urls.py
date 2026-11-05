from django.contrib.auth import views as auth_views
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api, views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("logout-all/", views.logout_all, name="logout_all"),
    path("api/me/", api.me, name="api_me"),
    path("api/token/", obtain_auth_token, name="api_token"),
    path("api/token/logout/", api.token_logout, name="token_logout"),
    path("api/jwt/", TokenObtainPairView.as_view(), name="api_jwt"),
    path("api/jwt/refresh/", TokenRefreshView.as_view(), name="jwt_refresh"),
    path("api/jwt/logout/", api.jwt_logout, name="jwt_logout"),
]
