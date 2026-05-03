"""Test-time compatibility helpers.

The codebase uses `google.genai`, while some tests patch
`google.generativeai.GenerativeModel`. This file creates a minimal alias so
those tests can patch the expected target without affecting runtime imports.
"""

from __future__ import annotations

import sys
import types


if 'google.generativeai' not in sys.modules:
    compat = types.ModuleType('google.generativeai')

    class _DummyResponse:
        def __init__(self, text: str = ''):
            self.text = text

    class GenerativeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            return _DummyResponse('')

    def configure(*args, **kwargs):
        return None

    compat.GenerativeModel = GenerativeModel
    compat.configure = configure
    sys.modules['google.generativeai'] = compat

    try:
        import google
        setattr(google, 'generativeai', compat)
    except Exception:
        pass
