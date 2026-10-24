"""Run the app against the fake YouTube (for the benchmark). Usage: python tests/stub_server.py PORT"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_youtube  # noqa: E402
import summary  # noqa: E402
from app import app  # noqa: E402

fake_youtube.install()
summary.available = lambda: True
summary.summarize = lambda text, title: "This video covers the X-Men.\n\nKey points:\n- [0:00] Welcome."

app.run(port=int(sys.argv[1]) if len(sys.argv) > 1 else 5055)
