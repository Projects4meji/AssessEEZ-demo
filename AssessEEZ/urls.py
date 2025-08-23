from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import (
    login_view, learner_view, eqa_view, iqa_view,
    assessor_view, administrator_view, contact_view,
    pricing_view, privacy_policy_view, user_agreement_view, faq_view
)
from django.views.generic import TemplateView
from django.http import HttpResponse

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('users/', include(('users.urls', 'users'), namespace='users')),
    path('qualifications/', include(('qualifications.urls', 'qualifications'), namespace='qualifications')),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('login/', login_view, name='login'),
    path('learner/', learner_view, name='learner'),
    path('eqa/', eqa_view, name='eqa'),
    path('iqa/', iqa_view, name='iqa'),
    path('assessor/', assessor_view, name='assessor'),
    path('administrator/', administrator_view, name='administrator'),
    path('contact/', contact_view, name='contact'),
    path('captcha/', include('captcha.urls')),
    path('pricing/', pricing_view, name='pricing'),
    path('privacy_policy/', privacy_policy_view, name='privacy_policy'),
    path('user_agreement/', user_agreement_view, name='user_agreement'),
    path('faq/', faq_view, name='FAQ'),
    path('api/', include('stripe_payments.urls')),
]

if settings.DEBUG:
   urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

#if settings.DEBUG:
 #   import debug_toolbar
  #  urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
   # urlpatterns += [
    #    path('__debug__/', include(debug_toolbar.urls)),
    #]