import sys
from pathlib import Path

# ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sys
from pathlib import Path

# ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sys as _sys
from actions.send_message import send_message

if __name__ == '__main__':
    # enable debug snapshots
    _sys._send_debug = True
    _sys._send_debug_dir = str(Path("tools") / "send_debug")
    # enable automatic confirmation during tests so no interactive prompt appears
    _sys._send_auto_confirm = True

    result = send_message({'receiver':'chinni','message_text':'hiii','platform':'whatsapp', 'debug': True, 'auto_confirm': True})
    print('RESULT:', result)
