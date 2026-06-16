"""Web 管理后台入口

用法:
    python web_main.py              # 默认 0.0.0.0:5000
    python web_main.py --port 8080  # 指定端口
    python web_main.py --debug      # 开发模式
"""

import argparse
import sys
import os
import shutil
import subprocess
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import create_app
from utils.console import configure_utf8_console
import config

configure_utf8_console()


def open_client(url: str) -> None:
    """Open the local client in Chrome when it is available."""
    chrome_candidates = [
        shutil.which("chrome"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    chrome = next((path for path in chrome_candidates if path and os.path.exists(path)), None)
    if chrome:
        subprocess.Popen([chrome, "--app=" + url])
    else:
        webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="A股量化 Web管理后台")
    parser.add_argument("--host", default=config.WEB.get("host", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=config.WEB.get("port", 5000))
    parser.add_argument("--debug", action="store_true",
                        default=config.WEB.get("debug", False))
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    app = create_app()
    url = f"http://127.0.0.1:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: open_client(url)).start()
    print(f"\n  A股量化 Web管理后台")
    print(f"  {url}")
    print(f"  按 Ctrl+C 停止\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
