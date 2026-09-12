"""A stand-in for the real extraction service, so this repo runs on its own.

The workflows in `workflows/` POST a PDF to an extraction service and branch on
whether the result is safe to write through unattended. That service lives in a
separate repo (pdf-to-json-demo), and requiring it — plus an API key, plus a model
call — just to see the workflows run would make this repo untestable for anyone
evaluating it in five minutes.

So this speaks the same contract and returns canned results. Its only job is to let
you exercise both branches on demand, including the failure branch, which is the one
that is otherwise hardest to demonstrate and the one most worth demonstrating.

    python services/mock_extract.py

Route by filename:
    anything containing "review"  -> route=review, a flagged ambiguous date
    anything containing "boom"    -> HTTP 502, to fire the error workflow
    anything else                 -> route=auto, a clean invoice
"""

from __future__ import annotations

import json
import pathlib
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8000
SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"

CLEAN = {
    "route": "auto",
    "reason": None,
    "min_confidence": 0.98,
    "threshold": 0.85,
    "review": {
        "needs_human_review": [],
        "not_present_in_document": ["remit_to", "discount_total"],
        "validation_problems": [],
    },
    "invoice": {
        "vendor_name": {"value": "Ashgrove Print & Design Ltd", "confidence": 0.99, "note": None},
        "invoice_number": {"value": "AP-2026-0771", "confidence": 0.99, "note": None},
        "invoice_date": {"value": "2026-02-14", "confidence": 0.98, "note": None},
        "currency": {"value": "GBP", "confidence": 0.99, "note": None},
        "total": {"value": "2913.60", "confidence": 0.99, "note": None},
    },
}

NEEDS_REVIEW = {
    "route": "review",
    "reason": (
        "invoice_date = '03/05/2026' (0.85) — Date format is numeric (03/05/2026); "
        "could be 3 May or March 5."
    ),
    "min_confidence": 0.85,
    "threshold": 0.85,
    "review": {
        "needs_human_review": [
            "invoice_date = '03/05/2026' (0.85) — Date format is numeric "
            "(03/05/2026); could be 3 May or March 5."
        ],
        "not_present_in_document": ["remit_to", "due_date", "amount_paid"],
        "validation_problems": [],
    },
    "invoice": {
        "vendor_name": {"value": "Hartley Medical Supplies Inc.", "confidence": 0.96, "note": None},
        "invoice_number": {"value": "HMS-114-2026", "confidence": 0.97, "note": None},
        "invoice_date": {
            "value": "03/05/2026",
            "confidence": 0.85,
            "note": "Date format is numeric (03/05/2026); could be 3 May or March 5.",
        },
        "currency": {"value": "USD", "confidence": 0.95, "note": None},
        "total": {"value": "901.39", "confidence": 0.98, "note": None},
    },
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            return self._send(200, {"status": "ok", "provider": "mock", "model": "mock"})

        # Serves the sample PDFs over HTTP rather than letting the workflow read them
        # off disk. n8n sandboxes filesystem access by default and n8n cloud has no
        # disk at all, so a "read the sample file" node fails for most people who
        # import this — which is the worst possible first impression for a demo.
        if self.path.startswith("/sample/"):
            name = pathlib.PurePosixPath(self.path).name
            if not re.fullmatch(r"[\w.-]+\.pdf", name):
                return self._send(400, {"detail": "Bad sample name."})
            path = SAMPLES / name
            if not path.is_file():
                available = sorted(p.name for p in SAMPLES.glob("*.pdf"))
                return self._send(404, {"detail": f"No such sample. Have: {available}"})
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)

        self._send(404, {"detail": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/extract":
            return self._send(404, {"detail": "Not found"})

        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        # Good enough to read the filename out of a multipart body without pulling in
        # a parser. This file is a test fixture; it is not on the delivery path.
        match = re.search(rb'filename="([^"]*)"', raw)
        name = (match.group(1).decode(errors="replace") if match else "").lower()

        if "boom" in name:
            # Deliberately the same shape the real service returns when the model
            # call fails, so the error workflow is exercised against a true signal.
            return self._send(502, {"detail": "RateLimitError: upstream returned 429"})
        self._send(200, NEEDS_REVIEW if "review" in name else CLEAN)

    def log_message(self, fmt: str, *args) -> None:
        # flush: the interesting thing to watch here is the retry burst when a call
        # fails, and a buffered log shows it minutes late or not at all.
        print(f"  mock  {fmt % args}", flush=True)


if __name__ == "__main__":
    print(__doc__)
    print(f"listening on http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
