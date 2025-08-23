from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

app_name = 'users'

urlpatterns = [
    path('superadmin/', views.superadmin_view, name='superadmin'),
    path('create_admin/', views.create_admin_view, name='create_admin'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('create_user/', views.create_user_view, name='create_user'),
    path('forgot_password/', views.forgot_password_view, name='forgot_password'),
    path('reset_password/<str:uidb64>/<str:token>/', views.reset_password_view, name='reset_password'),
    path('api/token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', RedirectView.as_view(pattern_name='login'), name='home'),
    path('logout/', views.custom_logout_view, name='custom_logout'),
    path('business/<str:business_id>/', views.business_details, name='business_details'),
    path('business/<str:business_id>/<str:role>/<str:period>/', views.admin_users_details, name='admin_users_details'),
    path('add_logo/', views.add_logo_view, name='add_logo'),
    path('password-reset-redirect/<str:uidb64>/<str:token>/', views.password_reset_redirect, name='password_reset_redirect'),
    path('superadmin/assign/<uuid:qual_id>/', views.assign_qualification, name='assign_qualification'),
    path('superadmin/dashboard/', views.superadmin_qualifications_dashboard, name='superadmin_qualifications_dashboard'),
    path('main/', views.main_page, name='main_page'),
    path('select_business/', views.select_business, name='select_business'),
]