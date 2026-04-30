"""
Fix My Name Online — Flask Web Server
Serves the FMNOL landing page + Stripe webhook endpoint.

For full app functionality (dashboard, bombardment, AI Sarah),
run the Streamlit app separately with:
    streamlit run app.py

Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

import os
import stripe
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS

# =============================================================================
# FLASK APP
# =============================================================================

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# =============================================================================
# STRIPE CONFIGURATION
# =============================================================================

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_placeholder')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_placeholder')
DOMAIN = os.environ.get('DOMAIN', 'https://fixmynameonline.com')

# Tier prices (monthly) — match landing page
TIER_PRICES = {
    'free': 0,
    'sentinel': 97,
    'starter': 297,
    'pro': 997,
    'premium': 1997,
    'concierge': 4997,
}

# Tier Stripe price IDs (monthly)
TIER_PRICE_IDS = {
    'sentinel': os.environ.get('STRIPE_PRICE_SENTINEL', 'price_sentinel'),
    'starter': os.environ.get('STRIPE_PRICE_STARTER', 'price_starter'),
    'pro': os.environ.get('STRIPE_PRICE_PRO', 'price_pro'),
    'premium': os.environ.get('STRIPE_PRICE_PREMIUM', 'price_premium'),
    'concierge': os.environ.get('STRIPE_PRICE_CONCIERGE', 'price_concierge'),
}

# Tier Stripe price IDs (annual)
TIER_PRICE_IDS_ANNUAL = {
    'sentinel': os.environ.get('STRIPE_PRICE_SENTINEL_ANNUAL', 'price_sentinel_annual'),
    'starter': os.environ.get('STRIPE_PRICE_STARTER_ANNUAL', 'price_starter_annual'),
    'pro': os.environ.get('STRIPE_PRICE_PRO_ANNUAL', 'price_pro_annual'),
    'premium': os.environ.get('STRIPE_PRICE_PREMIUM_ANNUAL', 'price_premium_annual'),
    'concierge': os.environ.get('STRIPE_PRICE_CONCIERGE_ANNUAL', 'price_concierge_annual'),
}


# =============================================================================
# LANDING PAGE ROUTES
# =============================================================================

@app.route('/')
def landing():
    """Serve the FMNOL landing page."""
    return send_from_directory('.', 'landing_page_v2.html')


@app.route('/pricing')
def pricing():
    """Redirect to landing page pricing section."""
    return redirect('/#pricing', code=302)


@app.route('/how-it-works')
def how_it_works():
    """Redirect to landing page how-it-works section."""
    return redirect('/#how-it-works', code=302)


@app.route('/faq')
def faq():
    """Redirect to landing page FAQ section."""
    return redirect('/#faq', code=302)


@app.route('/contact')
def contact():
    """Contact page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Contact — Fix My Name Online™</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: white; padding: 40px; }
            .container { max-width: 600px; margin: 0 auto; text-align: center; }
            h1 { color: #ff4444; font-size: 2em; margin-bottom: 20px; }
            .contact-method { background: #1a1a2e; padding: 20px; margin: 15px 0; border-radius: 12px; }
            a { color: #ff4444; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Contact Us</h1>
            <div class="contact-method">
                <h3>Email</h3>
                <p><a href="mailto:support@fixmynameonline.com">support@fixmynameonline.com</a></p>
            </div>
            <div class="contact-method">
                <h3>Live Chat</h3>
                <p>Available 24/7 via the app dashboard</p>
            </div>
            <div class="contact-method">
                <h3>Telegram Support</h3>
                <p><a href="https://t.me/fixmynameonline">@FixMyNameOnline</a></p>
            </div>
            <p style="color: #888; margin-top: 30px;">© 2026 MadisonJade Pty Ltd. All Rights Reserved.</p>
        </div>
    </body>
    </html>
    """


# =============================================================================
# STRIPE CHECKOUT ROUTES
# =============================================================================

@app.route('/checkout/<tier>')
def checkout(tier):
    """Redirect to Stripe Checkout for specified tier."""
    
    if tier not in TIER_PRICE_IDS or tier == 'free':
        return jsonify({'error': 'Invalid tier'}), 400
    
    try:
        billing = request.args.get('billing', 'monthly')
        if billing == 'annual':
            price_id = TIER_PRICE_IDS_ANNUAL.get(tier)
        else:
            price_id = TIER_PRICE_IDS.get(tier)
        
        checkout_session = stripe.checkout.Session.create(
            mode='subscription',
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            success_url=f'{DOMAIN}/success.html?tier={tier}',
            cancel_url=f'{DOMAIN}/cancel.html',
            allow_promotion_codes=True,
            subscription_data={
                'metadata': {
                    'tier': tier,
                    'billing': billing,
                }
            }
        )
        
        return redirect(checkout_session.url, code=302)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/create-portal-session', methods=['POST'])
def create_portal_session():
    """Create Stripe billing portal session."""
    
    try:
        data = request.get_json()
        customer_id = data.get('customer_id')
        
        if not customer_id:
            return jsonify({'error': 'Missing customer_id'}), 400
        
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f'{DOMAIN}/'
        )
        
        return jsonify({'url': session.url})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# STRIPE WEBHOOK
# =============================================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events."""
    
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    
    # Handle events
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        _handle_checkout_completed(session)
    
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        _handle_subscription_created(subscription)
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        _handle_subscription_updated(subscription)
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        _handle_subscription_deleted(subscription)
    
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        _handle_payment_failed(invoice)
    
    return '', 200


def _handle_checkout_completed(session):
    """Handle successful checkout."""
    print(f"Checkout completed: {session.get('customer_email')} - {session.get('metadata', {}).get('tier')}")
    # In production: activate customer account, send welcome email


def _handle_subscription_created(subscription):
    """Handle new subscription."""
    print(f"Subscription created: {subscription.get('id')} - {subscription.get('status')}")
    # In production: activate customer account


def _handle_subscription_updated(subscription):
    """Handle subscription update (upgrade/downgrade)."""
    print(f"Subscription updated: {subscription.get('id')} - {subscription.get('status')}")
    # In production: update customer tier


def _handle_subscription_deleted(subscription):
    """Handle subscription cancellation."""
    print(f"Subscription deleted: {subscription.get('id')}")
    # In production: downgrade to free tier


def _handle_payment_failed(invoice):
    """Handle failed payment."""
    print(f"Payment failed: {invoice.get('id')} - {invoice.get('customer_email')}")
    # In production: notify customer, pause service


# =============================================================================
# SUCCESS / CANCEL PAGES
# =============================================================================

@app.route('/success.html')
def success():
    """Payment success page."""
    tier = request.args.get('tier', 'unknown')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Welcome! — Fix My Name Online™</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: white; padding: 40px; text-align: center; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            h1 {{ color: #00ff00; font-size: 2.5em; margin-bottom: 20px; }}
            .tier-badge {{ background: #ff0000; padding: 10px 30px; border-radius: 30px; font-size: 1.2em; display: inline-block; margin: 20px 0; }}
            .next-steps {{ background: #1a1a2e; padding: 30px; border-radius: 12px; margin: 30px 0; text-align: left; }}
            .next-steps li {{ margin: 10px 0; }}
            a {{ color: #ff4444; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ Welcome to Fix My Name Online!</h1>
            <div class="tier-badge">★ {tier.upper()} TIER ★</div>
            <p>Your subscription is now active. Welcome to the suppression revolution.</p>
            <div class="next-steps">
                <h3>Next Steps:</h3>
                <ol>
                    <li>Check your email for login details</li>
                    <li>Access your dashboard and add your keyword</li>
                    <li>Start generating and publishing content</li>
                    <li>Track your suppression score in real-time</li>
                </ol>
            </div>
            <a href="/">← Back to Home</a>
        </div>
    </body>
    </html>
    """


@app.route('/cancel.html')
def cancel():
    """Payment cancelled page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cancelled — Fix My Name Online™</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: white; padding: 40px; text-align: center; }
            .container { max-width: 600px; margin: 0 auto; }
            h1 { color: #ffaa00; font-size: 2em; margin-bottom: 20px; }
            a { color: #ff4444; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Checkout Cancelled</h1>
            <p>No worries — your payment wasn't processed.</p>
            <p>You can always start with our <strong>FREE tier</strong> and upgrade later.</p>
            <br>
            <a href="/">← Back to Home</a>
        </div>
    </body>
    </html>
    """


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'fixmynameonline',
        'version': '1.0.0',
        'domain': DOMAIN
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
