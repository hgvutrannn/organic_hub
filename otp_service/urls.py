from django.urls import path
from . import views

app_name = 'otp_service'

urlpatterns = [
    path('verify/<int:user_id>/', views.verify_otp, name='verify'),
    path('resend/<int:user_id>/', views.resend_otp, name='resend'),
]
