import importlib.util
import pathlib

SCRIPT = pathlib.Path(__file__).parent / 'ops' / 'fmno_namewatch.py'
spec = importlib.util.spec_from_file_location('fmno_namewatch', SCRIPT)
assert spec is not None and spec.loader is not None
namewatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(namewatch)


def test_parse_queries_deduplicates_and_caps():
    queries = namewatch.parse_queries('Jane Smith\n jane smith ; ACME Plumbing | Old Name,Another Name')
    assert queries == ['Jane Smith', 'ACME Plumbing', 'Old Name', 'Another Name']


def test_result_record_normalises_tracking_and_flags_watch_terms():
    result = namewatch.result_record(
        'Jane Smith',
        'Court investigation involving Jane Smith',
        'https://Example.com/story/?utm_source=x&id=7#top',
        'test',
    )
    assert result['url'] == 'https://example.com/story?id=7'
    assert result['status'] == 'watch'
    assert 'court' in result['risk_terms']
    assert 'investigation' in result['risk_terms']


def test_match_paid_customers_requires_active_email_and_matching_session():
    active = {
        'paid@example.com': {'email': 'paid@example.com', 'session_id': 'cs_paid'},
        'other@example.com': {'email': 'other@example.com', 'session_id': 'cs_other'},
    }
    onboardings = [
        {'plan': 'sentinel', 'email': 'paid@example.com', 'session_id': 'cs_wrong', 'names': 'Paid Person'},
        {'plan': 'sentinel', 'email': 'other@example.com', 'session_id': 'cs_other', 'names': 'Other Person'},
        {'plan': 'sentinel', 'email': 'unpaid@example.com', 'session_id': 'cs_unpaid', 'names': 'Unpaid Person'},
    ]
    matched = namewatch.match_paid_customers(active, onboardings)
    assert len(matched) == 1
    assert matched[0]['payment']['email'] == 'other@example.com'


def test_process_customer_creates_baseline_then_alerts_only_on_new_results(tmp_path, monkeypatch):
    monkeypatch.setattr(namewatch, 'STATE_DIR', tmp_path)
    sent = []
    monkeypatch.setattr(namewatch, 'send_mail', lambda recipient, subject, body, sender=namewatch.SENDER: sent.append((recipient, subject, body, sender)))
    first = namewatch.result_record('Test Person', 'Test Person profile', 'https://example.com/profile', 'test')
    second = namewatch.result_record('Test Person', 'Court result for Test Person', 'https://example.com/court', 'test')
    batches = [([first], []), ([first, second], [])]
    monkeypatch.setattr(namewatch, 'search_queries', lambda queries: batches.pop(0))
    customer = {
        'payment': {
            'email': 'paid@example.com', 'session_id': 'cs_paid',
            'subscription_id': 'sub_paid', 'subscription_status': 'active',
        },
        'onboarding': {'name': 'Paid Person', 'email': 'paid@example.com', 'names': 'Test Person'},
    }

    baseline = namewatch.process_customer(customer, force=True)
    assert baseline['status'] == 'baseline_created'
    assert len(sent) == 1
    assert 'first baseline' in sent[0][1]

    alert = namewatch.process_customer(customer, force=True)
    assert alert['status'] == 'new_results_alerted'
    assert alert['new_results'] == 1
    assert len(sent) == 3  # customer baseline + customer alert + internal alert
    assert 'newly observed result' in sent[1][1]
    assert 'Court result' in sent[1][2]
    assert 'not necessarily newly published' in sent[1][2]


def test_dry_run_never_writes_state_or_sends_email(tmp_path, monkeypatch):
    monkeypatch.setattr(namewatch, 'STATE_DIR', tmp_path)
    monkeypatch.setattr(namewatch, 'search_queries', lambda queries: ([], []))
    monkeypatch.setattr(namewatch, 'send_mail', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('email sent')))
    customer = {
        'payment': {'email': 'paid@example.com', 'session_id': 'cs_paid', 'subscription_id': 'sub_paid', 'subscription_status': 'active'},
        'onboarding': {'name': 'Paid Person', 'email': 'paid@example.com', 'names': 'Test Person'},
    }
    result = namewatch.process_customer(customer, dry_run=True, force=True)
    assert result['status'] == 'baseline_created'
    assert not list(tmp_path.glob('*.json'))
