#!/usr/bin/env python3
"""Serve a folder, downloading .html/.htm files instead of displaying them.

Usage: python3 serve_html.py --directory ./html --port 8000
"""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit


class DownloadHandler(SimpleHTTPRequestHandler):
    def send_response(self, code, message=None):
        self.response_status = code
        super().send_response(code, message)

    def end_headers(self):
        path = Path(self.translate_path(self.path))
        if self.response_status == 200 and path.suffix.lower() in {".html", ".htm"} and path.is_file():
            self.send_header(
                "Content-Disposition",
                "attachment; filename=\"download.html\"; filename*=UTF-8''"
                + quote(path.name, safe=""),
            )
        super().end_headers()

    def send_head(self):
        # Reject links pointing outside the served folder.
        root = Path(self.directory).resolve()
        path = Path(self.translate_path(self.path)).resolve()
        if not path.is_relative_to(root):
            self.send_error(403, "Outside the served folder")
            return None
        # Always show the folder listing, even when index.html exists.
        if path.is_dir() and urlsplit(self.path).path.endswith("/"):
            return self.list_directory(str(path))
        return super().send_head()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="html", help="Folder to serve (default: html)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    handler = partial(DownloadHandler, directory=str(directory))
    with ThreadingHTTPServer((args.bind, args.port), handler) as server:
        print(f"Serving {directory} at http://{args.bind}:{server.server_port}/", flush=True)
        print("HTML files download when clicked. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
