"""Local preview only: no payment, model, email or external submissions."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['FMNO_DATA_DIR'] = tempfile.mkdtemp(prefix='fmno-preview-')
import server
server.stripe.api_key = ''
server.send_snapshot_emails = lambda *args, **kwargs: {}
server.tracking_head = lambda: ''
server.safe_create_fulfilment_case = lambda *args, **kwargs: None
server.run_free_snapshot_pipeline = lambda *args, **kwargs: None
server.send_telegram_alert = lambda *args, **kwargs: None
server.call_concierge_model = lambda *args, **kwargs: None

@server.app.before_request
def preview_only():
    if server.request.path.startswith(('/checkout/', '/admin/', '/onboarding', '/submit-onboarding', '/webhook', '/api/concierge/', '/diy-action/generate')):
        return server.Response('This action is disabled in the local preview.', status=403)

if __name__ == '__main__':
    server.app.run(host='127.0.0.1', port=5093, debug=False)
