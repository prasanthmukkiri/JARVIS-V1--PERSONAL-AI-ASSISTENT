from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui.app import app

with app.test_client() as client:
    for path in ['/api/analytics', '/api/insights', '/api/chart/success_rates', '/api/emotion/stats']:
        resp = client.get(path)
        print(path, resp.status_code)
        print(resp.get_data(as_text=True)[:2000])
        print('---')
