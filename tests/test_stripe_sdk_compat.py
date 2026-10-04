"""Regression coverage using actual SDK resources, not dict-only mocks."""
import json
import time
import hashlib
import hmac
import stripe
import server
import paid_actions
from test_paid_actions import shop, start


def resource(data):
    return stripe.StripeObject.construct_from(data, None)


def test_sdk_checkout_price_and_session_resources(shop, monkeypatch):
    client, _ = shop
    monkeypatch.setattr(stripe.Price, 'retrieve', lambda pid: resource({'id':pid,'active':True,'unit_amount':1900,'currency':'usd','type':'one_time'}))
    monkeypatch.setattr(stripe.checkout.Session, 'create', lambda **kw: resource({'url':'https://checkout.stripe.test/ok'}))
    assert client.get('/checkout/diy-single').status_code == 302


def test_sdk_nested_paid_and_refund_resources(shop, monkeypatch):
    client, session_for = shop
    row=session_for('cs_test_sdk_resources',created=int(time.time()))
    monkeypatch.setattr(stripe.checkout.Session,'retrieve',lambda *a,**kw:resource(row))
    monkeypatch.setattr(stripe.Refund,'list',lambda **kw:resource({'data':[],'has_more':False}))
    csrf=start(client,row['id'])
    monkeypatch.setattr(stripe.Refund,'create',lambda **kw:resource({'id':'re_synthetic'}))
    monkeypatch.setattr(stripe.Refund,'retrieve',lambda rid:resource({'id':rid,'status':'succeeded'}))
    assert client.post('/diy-action/refund',data={'csrf':csrf,'confirm':'refund'}).status_code==200


def test_real_sdk_signed_webhook_resources(shop, monkeypatch):
    client, session_for=shop
    row=session_for('cs_test_sdk_webhook')
    secret='whsec_synthetic'
    monkeypatch.setattr(server,'STRIPE_WEBHOOK_SECRET',secret)
    payload=json.dumps({'id':'evt_synthetic','object':'event','type':'checkout.session.completed','data':{'object':row}})
    timestamp=str(int(time.time()))
    signature=hmac.new(secret.encode(),(timestamp+'.'+payload).encode(),hashlib.sha256).hexdigest()
    header='t='+timestamp+',v1='+signature
    assert client.post('/webhook',data=payload,headers={'Stripe-Signature':header},content_type='application/json').status_code==200
    assert len(paid_actions.backup(server)['workspaces'])==1
    assert client.post('/webhook',data=payload,headers={'Stripe-Signature':'t='+timestamp+',v1=invalid'}).status_code==400


def test_legacy_verification_handles_sdk_metadata(shop,monkeypatch):
    _,session_for=shop
    row=session_for('cs_test_sdk_legacy',metadata={'tier':'sentinel'})
    monkeypatch.setattr(stripe.checkout.Session,'retrieve',lambda *a,**kw:resource(row))
    assert server.verify_paid_checkout(row['id'],expected_tier='sentinel') is not None
