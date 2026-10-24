"""Transcript Grabber as a desktop app: runs the site inside its own window.

Run from source:  python desktop.py
Packaged builds come from .github/workflows/desktop.yml.
Set TG_HEADLESS=1 to run only the server (used to test packaged builds).
"""

import os
import socket
import threading
import time

from werkzeug.serving import make_server

from app import app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server() -> str:
    port = int(os.getenv("TG_PORT") or free_port())
    server = make_server("127.0.0.1", port, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    return f"http://127.0.0.1:{port}"


def main():
    url = start_server()

    if os.getenv("TG_HEADLESS"):
        print(f"Serving at {url}", flush=True)
        threading.Event().wait()
        return

    import webview

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    webview.create_window("Transcript Grabber", url, width=1280, height=840, min_size=(420, 600))
    webview.start()


if __name__ == "__main__":
    main()
