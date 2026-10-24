import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def client():
    import fake_youtube
    import app as app_module

    fake_youtube.install()
    app_module.app.testing = True
    return app_module.app.test_client()
