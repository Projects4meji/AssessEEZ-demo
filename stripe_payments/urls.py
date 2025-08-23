from django.urls import path
from . import views

app_name = 'stripe_payments'

urlpatterns = [
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('success/', views.payment_success, name='payment_success'),
    path('cancel/', views.payment_cancel, name='payment_cancel'),
    path('test-config/', views.test_stripe_config, name='test_stripe_config'),
]

