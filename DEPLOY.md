# Fix My Name Online — DEPLOYMENT GUIDE

## 1. DEPLOY LANDING PAGE TO NETLIFY (30 seconds)

The landing page is a standalone HTML file. Deploy it immediately:

```bash
# Option A: Netlify CLI
cd ~/fix_my_name_online
netlify deploy --prod --dir=.

# Option B: Drag & drop
# Go to https://app.netlify.com/drop
# Drag the entire ~/fix_my_name_online folder
# It will auto-detect landing_page_v2.html as the entry point

# Option C: GitHub + Netlify
# Already pushed to: https://github.com/elli35111-png/fix-my-name-online
# Connect this repo in Netlify dashboard → auto-deploy
```

**Custom domain**: Point `fixmynameonline.com` → Netlify, then add in Netlify dashboard.

---

## 2. CREATE STRIPE PRODUCTS

1. Log into **Stripe Dashboard**: https://dashboard.stripe.com
2. Go to **Products** → **Add Product**
3. Create these 5 products (monthly + annual for each):

| Product | Monthly | Annual | Features |
|---------|---------|--------|----------|
| Sentinel | $97/mo | $970/yr | Monitoring, alerts, AI Lawyer agents, monthly email pack |
| Starter | $297/mo | $2,970/yr | 20 content pieces, auto-publish, quarterly PDF |
| Pro | $997/mo | $9,970/yr | 50 pieces + FPS owned-media (firstpagestrategy.org) |
| Premium | $1,997/mo | $19,970/yr | 150 pieces, dedicated researcher, monthly PDF |
| Concierge | $4,997/mo | $49,970/yr | Unlimited, Sarah Chen video reports, white-glove |

4. For each product, create **Monthly** and **Annual** recurring prices
5. Copy the **Price IDs** (format: `price_xxx...`)

---

## 3. UPDATE server.py WITH STRIPE PRICE IDs

Edit `~/fix_my_name_online/server.py`, replace the placeholder price IDs:

```python
TIER_PRICE_IDS = {
    'sentinel': 'price_ACTUAL_ID_FROM_STRIPE',
    'starter': 'price_ACTUAL_ID_FROM_STRIPE',
    'pro': 'price_ACTUAL_ID_FROM_STRIPE',
    'premium': 'price_ACTUAL_ID_FROM_STRIPE',
    'concierge': 'price_ACTUAL_ID_FROM_STRIPE',
}
```

---

## 4. DEPLOY FULL APP TO RENDER

1. Log into **Render**: https://dashboard.render.com
2. Click **New** → **Blueprint**
3. Use `render.yaml` from this repo (auto-fills all settings)
4. Add environment variables:
   - `STRIPE_SECRET_KEY` → your Stripe secret key
   - `STRIPE_PUBLISHABLE_KEY` → your Stripe publishable key
   - `STRIPE_WEBHOOK_SECRET` → from Stripe → Webhooks
   - All `STRIPE_PRICE_*` IDs from Step 2
   - `DOMAIN` → `https://fixmynameonline.com`
   - `BREVO_API_KEY` → your Brevo/SendinBlue API key
   - `FPS_WP_USER` → WordPress username for firstpagestrategy.org
   - `FPS_WP_APP_PASSWORD` → WordPress app password

5. Click **Apply Blueprint**
6. Wait 2-3 minutes for deployment
7. Test at: `https://fix-my-name-online.onrender.com`

---

## 5. UPDATE STRIPE WEBHOOK

After Render deploys:

1. Go to **Stripe Dashboard** → **Webhooks**
2. Add endpoint: `https://YOUR-RENDER-URL.onrender.com/webhook`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy webhook signing secret to Render env: `STRIPE_WEBHOOK_SECRET`

---

## 6. SET UP FPS WORDPRESS PUBLISHING

For Pro+ tiers to publish to firstpagestrategy.org:

1. Log into WordPress: https://firstpagestrategy.org/wp-admin
2. Go to **Users** → **Profile**
3. Scroll to **Application Passwords**
4. Create new password named "FMNOL Publisher"
5. Copy the password (format: `xxxx xxxx xxxx xxxx`)
6. Add to Render env:
   - `FPS_WP_USER` = your WordPress username
   - `FPS_WP_APP_PASSWORD` = the app password you just created
7. Repeat for firstpageacademy.org

---

## 7. SET UP CUSTOM DOMAIN

1. **Render**: Dashboard → Your Service → Settings → Custom Domains
   - Add `fixmynameonline.com`
   - Add DNS records Render provides

2. **Namecheap**: Add DNS records:
   ```
   Type: CNAME
   Name: www
   Value: YOUR-RENDER-URL.onrender.com
   
   Type: A (for naked domain)
   Name: @
   Value: 76.76.21.21
   ```

3. **Netlify** (if using for landing page):
   - Dashboard → Domains → Add `fixmynameonline.com`
   - Netlify will give you DNS records for Namecheap

---

## 8. STREAMLINE DEPLOYMENT (for future updates)

```bash
cd ~/fix_my_name_online

# Make changes to code...

# Push to GitHub → auto-deploys to Render
git add .
git commit -m "your changes"
git push

# Or deploy landing page to Netlify
netlify deploy --prod --dir=.
```

---

## QUICK START CHECKLIST

- [ ] Deploy landing page to Netlify (landing_page_v2.html)
- [ ] Create 5 Stripe products with monthly + annual prices
- [ ] Update server.py with Stripe Price IDs
- [ ] Deploy full app to Render via render.yaml
- [ ] Add all environment variables to Render
- [ ] Set up Stripe webhook
- [ ] Set up FPS WordPress credentials
- [ ] Configure custom domain
- [ ] Test full checkout flow

---

## FILES SUMMARY

| File | Purpose |
|------|---------|
| `landing_page_v2.html` | Marketing landing page (Netlify) |
| `server.py` | Flask server with Stripe checkout (Render) |
| `app_full.py` | Full Streamlit app (run separately) |
| `browser_publisher.py` | Multi-platform publishing automation |
| `ai_lawyer.py` | AI lawyer personas (4 jurisdictions) |
| `evidence_pack.py` | PDF evidence pack generator |
| `fps_publisher.py` | FPS WordPress publishing |
| `bombardment_scheduler.py` | Content queue + scheduling |
| `content_generator.py` | AI content generation |
| `render.yaml` | Render deployment blueprint |
| `setup_stripe_products.py` | One-run Stripe product creation |

---

## SUPPORT

- **Email**: support@fixmynameonline.com
- **Telegram**: @FixMyNameOnline
- **Docs**: See README.md in this repo

© 2026 MadisonJade Pty Ltd. All Rights Reserved. FixMyNameOnline™ and First Page Strategy™ are trademarks of MadisonJade Pty Ltd.
