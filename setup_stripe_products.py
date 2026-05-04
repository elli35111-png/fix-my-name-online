"""
FixMyNameOnline™ — Stripe Products & Prices Setup
Creates launch-safe products/prices for the FMNO funnel.

Usage:
  STRIPE_SECRET_KEY=sk_live_... python setup_stripe_products.py

Copyright (c) 2026 MadisonJade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of MadisonJade Pty Ltd.
"""
import os
import json
import stripe

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
if not stripe.api_key:
    print('Set STRIPE_SECRET_KEY first')
    raise SystemExit(1)

PRODUCTS = [
    {
        'id': 'sentinel',
        'env': 'STRIPE_PRICE_SENTINEL',
        'name': 'Sentinel Alert™ — FixMyNameOnline™',
        'description': 'Automated name, business, associated-name, review, and risk-term monitoring. Alerts only; no human review or repair work included.',
        'amount': 29,
        'mode': 'subscription',
        'recurring': {'interval': 'month'},
    },
    {
        'id': 'removal-review',
        'env': 'STRIPE_PRICE_REMOVAL_REVIEW',
        'name': 'Removal Review™ — FixMyNameOnline™',
        'description': 'One-time review of up to 3 bad links/results to assess whether a removal, correction, de-indexing, privacy, outdated-content, or reporting pathway looks realistic. No outcome guarantee.',
        'amount': 297,
        'mode': 'payment',
    },
    {
        'id': 'review-defence',
        'env': 'STRIPE_PRICE_REVIEW_DEFENCE',
        'name': 'Review Defence™ — FixMyNameOnline™',
        'description': 'One-time Google review defence pack: audit up to 25 bad reviews, identify possible policy issues, draft reporting notes, draft calm owner responses, and prepare a recovery plan. Google decides outcomes.',
        'amount': 497,
        'mode': 'payment',
    },
    {
        'id': 'starter',
        'env': 'STRIPE_PRICE_STARTER',
        'name': 'Starter™ — FixMyNameOnline™',
        'description': 'Monthly starter repair plan for a name or business: name map, approved positive pages/articles, profile/social support items, and monthly evidence report.',
        'amount': 499,
        'mode': 'subscription',
        'recurring': {'interval': 'month'},
    },
    {
        'id': 'pro',
        'env': 'STRIPE_PRICE_PRO',
        'name': 'Pro™ — FixMyNameOnline™',
        'description': 'Monthly ongoing reputation repair for larger cases: more approved positive assets, monitoring, old-name/misspelling coverage, and next-step advice.',
        'amount': 997,
        'mode': 'subscription',
        'recurring': {'interval': 'month'},
    },
    {
        'id': 'premium',
        'env': 'STRIPE_PRICE_PREMIUM',
        'name': 'Premium™ — FixMyNameOnline™',
        'description': 'Monthly deep repair for serious cases: full search/business/review risk map, 12+ approved positive pages/articles, 30 support items, and priority monthly review.',
        'amount': 2497,
        'mode': 'subscription',
        'recurring': {'interval': 'month'},
    },
]

def main():
    created=[]
    for item in PRODUCTS:
        product = stripe.Product.create(
            name=item['name'],
            description=item['description'],
            metadata={'fmno_plan': item['id'], 'service': 'fixmynameonline'}
        )
        price_args = {
            'product': product.id,
            'unit_amount': item['amount'] * 100,
            'currency': 'usd',
            'metadata': {'fmno_plan': item['id'], 'env': item['env'], 'mode': item['mode']},
        }
        if item.get('recurring'):
            price_args['recurring'] = item['recurring']
        price = stripe.Price.create(**price_args)
        created.append({'plan': item['id'], 'env': item['env'], 'mode': item['mode'], 'amount_usd': item['amount'], 'product_id': product.id, 'price_id': price.id})
        print(f"{item['env']}={price.id}  # {item['name']} ${item['amount']} {item['mode']}")
    with open('stripe_products_launch_v1.json', 'w') as f:
        json.dump(created, f, indent=2)
    print('Saved stripe_products_launch_v1.json')

if __name__ == '__main__':
    main()
