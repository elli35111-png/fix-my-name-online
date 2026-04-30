"""
Fix My Name Online — Stripe Products & Prices Setup
Run ONCE to create all FMNOL products and prices in Stripe Dashboard.

Usage: python setup_stripe_products.py
Requires: STRIPE_SECRET_KEY env var set

Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

import os
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
if not stripe.api_key:
    print("❌ Set STRIPE_SECRET_KEY environment variable first")
    exit(1)

# =============================================================================
# PRODUCT DEFINITIONS
# =============================================================================

TIERS = [
    {
        "id": "sentinel",
        "name": "Sentinel — Fix My Name Online",
        "description": "DIY reputation monitoring & alerts. Monitor your name across 40+ platforms, receive instant alerts for new mentions, and access our AI Lawyer agents for removal requests.",
        "monthly": 97,
        "annual": 970,  # 2 months free
        "features": [
            "Unlimited keyword tracking",
            "40+ platform monitoring",
            "Real-time Google alert integration",
            "RTBF letter generator (UK/EU)",
            "DCMA template generator (US)",
            "Monthly email evidence pack",
            "Community support"
        ]
    },
    {
        "id": "starter",
        "name": "Starter — Fix My Name Online",
        "description": "Active content generation & publishing. Generate SEO-optimized content about yourself and push it live across Medium, Quora, Substack, WordPress, Reddit, and more.",
        "monthly": 297,
        "annual": 2970,
        "features": [
            "Everything in Sentinel, plus:",
            "20 content pieces/month",
            "AI-generated articles (500-1500 words)",
            "AI-generated social posts",
            "Auto-publish to: Medium, Quora, Substack, WordPress, Reddit, Tumblr, Pinterest",
            "Quarterly PDF evidence pack",
            "Email support"
        ]
    },
    {
        "id": "pro",
        "name": "Pro — Fix My Name Online",
        "description": "FPS owned-media publishing with professional templates. Your content gets published to firstpagestrategy.org — a real news site with real Google domain authority.",
        "monthly": 997,
        "annual": 9970,
        "features": [
            "Everything in Starter, plus:",
            "50 content pieces/month",
            "FPS owned-media publishing (firstpagestrategy.org)",
            "FPS owned-media publishing (firstpageacademy.org)",
            "Professional article templates",
            "Enhanced bombardment scheduling",
            "Bi-monthly PDF evidence pack",
            "Priority support"
        ]
    },
    {
        "id": "premium",
        "name": "Premium — Fix My Name Online",
        "description": "Full-service suppression with dedicated researcher and dedicated bombardment. Everything we can legally do to protect your reputation.",
        "monthly": 1997,
        "annual": 19970,
        "features": [
            "Everything in Pro, plus:",
            "150 content pieces/month",
            "Dedicated researcher (2 per Premium client)",
            "Dedicated bombardment schedule",
            "Manual outreach & contact management",
            "Custom article briefings",
            "Monthly PDF evidence pack",
            "Direct researcher access",
            "Priority everything"
        ]
    },
    {
        "id": "concierge",
        "name": "Concierge — Fix My Name Online",
        "description": "Personal reputation command center. Named account manager, weekly video reports from Sarah Chen, white-glove service, and unlimited everything.",
        "monthly": 4997,
        "annual": 49970,
        "features": [
            "Everything in Premium, plus:",
            "Unlimited content pieces",
            "Named account manager",
            "Sarah Chen — weekly video evidence pack",
            "Direct WhatsApp support",
            "Crisis response team (48hr SLA)",
            "Custom platform strategy",
            "Quarterly strategy calls",
            "Unlimited bombardment",
            "Full white-glove service"
        ]
    }
]


# =============================================================================
# CREATE PRODUCTS & PRICES
# =============================================================================

def create_tier_products():
    """Create all Stripe products and prices."""
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║     FIX MY NAME ONLINE — STRIPE PRODUCTS SETUP                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    created = []
    
    for tier in TIERS:
        print(f"\n📦 Creating: {tier['name']}")
        
        # Create product
        product = stripe.Product.create(
            name=tier['name'],
            description=tier['description'],
            metadata={
                'tier': tier['id'],
                'features': '|'.join(tier['features']),
            }
        )
        print(f"  ✅ Product: {product.id}")
        
        # Monthly price
        monthly_price = stripe.Price.create(
            product=product.id,
            unit_amount=tier['monthly'] * 100,  # cents
            currency='usd',
            recurring={'interval': 'month'},
            metadata={'billing': 'monthly', 'tier': tier['id']}
        )
        print(f"  ✅ Monthly: ${tier['monthly']}/mo → {monthly_price.id}")
        
        # Annual price (2 months free = 10 months billed)
        annual_price = stripe.Price.create(
            product=product.id,
            unit_amount=tier['annual'] * 100,  # cents
            currency='usd',
            recurring={'interval': 'year'},
            metadata={'billing': 'annual', 'tier': tier['id']}
        )
        print(f"  ✅ Annual: ${tier['annual']}/yr → {annual_price.id}")
        
        created.append({
            'tier': tier['id'],
            'product_id': product.id,
            'monthly_price_id': monthly_price.id,
            'annual_price_id': annual_price.id,
        })
    
    # Print summary
    print("""
╔══════════════════════════════════════════════════════════════════╗
║     SETUP COMPLETE — COPY THESE IDs TO RENDER ENV VARS          ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    for item in created:
        print(f"""
TIER: {item['tier'].upper()}
  STRIPE_PRICE_{item['tier'].upper()}=price_xxx
  STRIPE_PRICE_{item['tier'].upper()}_ANNUAL=price_xxx
  
→ Product: https://dashboard.stripe.com/products/{item['product_id']}
→ Monthly: {item['monthly_price_id']}
→ Annual: {item['annual_price_id']}
        """)
    
    # Save to file for reference
    import json
    with open('stripe_products.json', 'w') as f:
        json.dump(created, f, indent=2)
    
    print("✅ Product IDs saved to stripe_products.json")
    print("\n📋 Next steps:")
    print("   1. Copy price IDs to Render environment variables")
    print("   2. Update server.py with price IDs")
    print("   3. Test checkout flow")
    print("   4. Update Stripe webhook endpoint URL")


if __name__ == '__main__':
    try:
        create_tier_products()
    except stripe.error.AuthenticationError:
        print("❌ Invalid Stripe API key. Check STRIPE_SECRET_KEY")
    except Exception as e:
        print(f"❌ Error: {e}")
