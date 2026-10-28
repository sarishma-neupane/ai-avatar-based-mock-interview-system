from django.urls import path
from . import api_views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('register/', api_views.register_api, name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # get JWT access & refresh tokens
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # refresh token
]
