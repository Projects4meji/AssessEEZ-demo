from django.contrib.auth.models import AnonymousUser
from users.models import UserBusiness 
from qualifications.models import MessageRecipient 


def user_context(request):
    context = {
        'full_name': '',
        'business': None,
        'unread_count': 0,
    }
    
    if request.user.is_authenticated and not isinstance(request.user, AnonymousUser):
        context['full_name'] = request.user.full_name or request.user.email
        business_id = request.session.get('business_id')
        if business_id:
            try:
                user_business = UserBusiness.objects.get(user=request.user, business__business_id=business_id)
                context['business'] = user_business.business
                context['unread_count'] = MessageRecipient.objects.filter(
                    recipient=user_business,
                    is_read=False,
                    message__recipients__recipient__business__business_id=business_id
                ).count()
            except UserBusiness.DoesNotExist:
                pass
    
    return context