import stripe
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_variables

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Stripe with your secret key
try:
    stripe.api_key = settings.STRIPE_SECRET_KEY
    logger.info(f"Stripe API key configured successfully: {stripe.api_key[:20]}...")
except Exception as e:
    logger.error(f"Error configuring Stripe: {e}")
    stripe.api_key = None

@csrf_exempt
@require_http_methods(["POST"])
def create_checkout_session(request):
    """
    Create a Stripe checkout session for payment
    """
    try:
        # Debug: Log the request
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request body: {request.body}")
        
        # Parse JSON data
        try:
            data = json.loads(request.body)
            logger.info(f"Parsed data: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return JsonResponse({
                'error': 'Invalid JSON data',
                'details': str(e)
            }, status=400)
        
        # Extract and validate data
        plan_type = data.get('plan_type')
        price = data.get('price')
        currency = data.get('currency', 'gbp')
        name = data.get('name')
        description = data.get('description')
        
        logger.info(f"Plan type: {plan_type}")
        logger.info(f"Price: {price}")
        logger.info(f"Currency: {currency}")
        logger.info(f"Name: {name}")
        logger.info(f"Description: {description}")
        
        # Validate required fields
        if not all([plan_type, price, name, description]):
            missing_fields = []
            if not plan_type: missing_fields.append('plan_type')
            if not price: missing_fields.append('price')
            if not name: missing_fields.append('name')
            if not description: missing_fields.append('description')
            
            logger.error(f"Missing required fields: {missing_fields}")
            return JsonResponse({
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'received_data': data
            }, status=400)
        
        # Validate price is a number
        try:
            price = int(price)
            if price <= 0:
                raise ValueError("Price must be positive")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid price value: {price}, error: {e}")
            return JsonResponse({
                'error': f'Invalid price value: {price}. Price must be a positive integer.',
                'received_data': data
            }, status=400)
        
        # Check if Stripe is properly configured
        if not stripe.api_key:
            logger.error("Stripe is not properly configured")
            return JsonResponse({
                'error': 'Stripe is not properly configured. Please check your settings.',
                'stripe_configured': False
            }, status=500)
        
        # Test Stripe connection
        logger.info(f"Testing Stripe connection with API key: {stripe.api_key[:20]}...")
        try:
            # Make a simple API call to test connection
            account = stripe.Account.retrieve()
            logger.info(f"Stripe connection successful. Account ID: {account.id}")
        except Exception as e:
            logger.error(f"Stripe connection test failed: {e}")
            return JsonResponse({
                'error': f'Stripe connection failed: {str(e)}',
                'stripe_connection_error': True
            }, status=500)
        
        # Create checkout session based on plan type
        if plan_type == 'monthly':
            # Monthly subscription
            logger.info(f"Creating monthly subscription checkout session...")
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': currency,
                            'unit_amount': price,  # Price in pence
                            'recurring': {
                                'interval': 'month',
                            },
                            'product_data': {
                                'name': name,
                                'description': description,
                            },
                        },
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=request.build_absolute_uri('/') + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=request.build_absolute_uri('/'),
                    metadata={
                        'plan_type': plan_type,
                        'user_id': request.user.id if request.user.is_authenticated else 'anonymous'
                    }
                )
                logger.info(f"Monthly subscription checkout session created successfully: {checkout_session.id}")
            except Exception as e:
                logger.error(f"Error creating monthly subscription checkout session: {e}")
                logger.error(f"Error type: {type(e)}")
                raise
        else:
            # One-off payment
            logger.info(f"Creating one-off payment checkout session...")
            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': currency,
                            'unit_amount': price,  # Price in pence
                            'product_data': {
                                'name': name,
                                'description': description,
                            },
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=request.build_absolute_uri('/') + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=request.build_absolute_uri('/'),
                    metadata={
                        'plan_type': plan_type,
                        'user_id': request.user.id if request.user.is_authenticated else 'anonymous'
                    }
                )
                logger.info(f"One-off payment checkout session created successfully: {checkout_session.id}")
            except Exception as e:
                logger.error(f"Error creating one-off payment checkout session: {e}")
                logger.error(f"Error type: {type(e)}")
                raise
        
        logger.info(f"Returning successful response with session ID: {checkout_session.id}")
        return JsonResponse({
            'id': checkout_session.id,
            'url': checkout_session.url
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return JsonResponse({
            'error': str(e),
            'stripe_error': True
        }, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({
            'error': 'An error occurred while creating checkout session',
            'details': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """
    Handle Stripe webhooks for payment events
    """
    try:
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        
        if not sig_header:
            logger.error("No Stripe signature header found")
            return JsonResponse({'error': 'No signature header'}, status=400)
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            logger.error(f"Invalid payload: {e}")
            return JsonResponse({'error': 'Invalid payload'}, status=400)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature: {e}")
            return JsonResponse({'error': 'Invalid signature'}, status=400)
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            # Handle successful payment
            handle_successful_payment(session)
        elif event['type'] == 'invoice.payment_succeeded':
            # Handle successful subscription payment
            handle_subscription_payment(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            # Handle failed subscription payment
            handle_failed_payment(event['data']['object'])
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({'error': 'Webhook processing failed'}, status=500)

def handle_successful_payment(session):
    """
    Handle successful one-time payment
    """
    # Add your payment success logic here
    # For example, update user subscription status, send confirmation email, etc.
    logger.info(f"Payment successful for session: {session.id}")
    logger.info(f"Plan type: {session.metadata.get('plan_type')}")
    logger.info(f"User ID: {session.metadata.get('user_id')}")

def handle_subscription_payment(invoice):
    """
    Handle successful subscription payment
    """
    # Add your subscription payment logic here
    logger.info(f"Subscription payment successful for invoice: {invoice.id}")

def handle_failed_payment(invoice):
    """
    Handle failed subscription payment
    """
    # Add your failed payment logic here
    logger.info(f"Subscription payment failed for invoice: {invoice.id}")

def payment_success(request):
    """
    Payment success page
    """
    session_id = request.GET.get('session_id')
    return JsonResponse({
        'status': 'success',
        'message': 'Payment completed successfully',
        'session_id': session_id
    })

def payment_cancel(request):
    """
    Payment cancellation page
    """
    return JsonResponse({
        'status': 'cancelled',
        'message': 'Payment was cancelled'
    })

def test_stripe_config(request):
    """
    Test endpoint to verify Stripe configuration
    """
    try:
        return JsonResponse({
            'status': 'success',
            'stripe_configured': bool(stripe.api_key),
            'api_key_prefix': stripe.api_key[:20] + '...' if stripe.api_key else 'Not configured',
            'settings_public_key': getattr(settings, 'STRIPE_PUBLIC_KEY', 'Not found'),
            'settings_secret_key': getattr(settings, 'STRIPE_SECRET_KEY', 'Not found')[:20] + '...' if getattr(settings, 'STRIPE_SECRET_KEY', None) else 'Not found'
        })
    except Exception as e:
        logger.error(f"Test config error: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

