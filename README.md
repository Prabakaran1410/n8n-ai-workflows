# n8n AI workflows — automations that tell you when they break

Two working n8n automations, plus the part most of them are missing: a shared
error handler, retries on every network call, and a heartbeat so that a workflow
which stops running altogether is still noticed.

<!-- assets/01-invoice-intake.png — canvas screenshot, see assets/WHAT-TO-CAPTURE.md -->

---

## Why this repo leads with error handling

Almost every broken automation I get asked to rescue was working on the day it
was delivered. It stopped weeks later — an expired token, a renamed field, an API
that started rate limiting — and nobody noticed until the data was already wrong.

A workflow without an error branch does not fail loudly. It fails quietly, which
is worse, because the dashboard still looks fine.

There is a second, subtler gap. An **error trigger only fires when something runs
and fails.** A workflow that stops firing at all — a disabled trigger, an expired
OAuth token, a paused instance — throws nothing, and so alerts nothing. That is
what the heartbeat is for: the workflow pings a dead-man's-switch on every run,
and the absence of that ping is itself the alert.

---

## Workflow 1 — Invoice intake, unattended

`workflows/01-invoice-intake.json`

An invoice arrives by email. It ends up in a spreadsheet — unless the reading is
doubtful, in which case a person is asked first and nothing is written.

```
Email arrives ─▶ Has a PDF? ──no──▶ ignore (not a failure)
                     │yes
                     ▼
              Extract document            ← retries 3× with backoff
                     │
            Safe to post automatically?
              │                   │
         safe │                   │ needs a human
              ▼                   ▼
      Append to the ledger   Write the review message
                                  ▼
                         Post to the review channel
```

**The decision this workflow exists to make** is at `Safe to post automatically?`.
The extraction service returns a `route` of `auto` or `review`, and the workflow
branches on that word. It deliberately does **not** compare confidence scores
itself — a workflow should not have to know what `0.85` means, and if the
threshold ever changes it should change in one place.

A wrong number that lands silently in the books is worse than a blank one someone
has to fill in. So anything the model was unsure about stops here, and the Slack
message says which field, what it guessed, and why it was unsure:

> **Invoice needs a look before it goes in the books**
> Hartley Medical Supplies Inc. — HMS-114-2026
> Amount: USD 901.39
>
> **Read with low confidence:**
> • invoice_date = '03/05/2026' (0.85) — Date format is numeric; could be 3 May or March 5.
>
> Nothing has been written to the sheet. Confirm and it goes in.

That is a message someone can act on in four seconds. A JSON dump is not, and an
alert nobody reads gets muted — at which point it is worse than no alert, because
it looks like coverage.

### The extraction service

`Extract document` POSTs the PDF to an HTTP service and expects back:

```json
{
  "route": "auto | review",
  "reason": "the first thing that was wrong, or null",
  "min_confidence": 0.85,
  "review": {
    "needs_human_review": [],
    "not_present_in_document": [],
    "validation_problems": []
  },
  "invoice": { "...": "field: { value, confidence, note }" }
}
```

Anything that speaks that contract works. Two do:

- **[pdf-to-json-demo](https://github.com/Prabakaran1410/pdf-to-json-demo)** — the
  real one. Per-field confidence from an LLM, plus deterministic arithmetic checks
  that recompute the totals rather than trusting them. Run `uvicorn serve:app`.
- **`services/mock_extract.py`** — a stand-in, so this repo runs on its own with no
  API key and no model call. Route by filename: a file named `...review...` comes
  back needing review, `...boom...` returns a 502 to fire the error workflow, and
  anything else comes back clean.

## Workflow 2 — Morning digest

`workflows/02-morning-digest.json`

Runs at 08:00, reads the week out of the ledger, and posts a short summary.
It replaces a person opening a spreadsheet every morning.

One design note that matters more than it looks: **the model never adds anything
up.** A Code node computes the totals, the per-vendor breakdown and the count of
items still in review, and hands those over as fixed facts. The model is asked
only to turn them into sentences, at temperature 0.2, with an explicit instruction
never to infer a figure. Asking an LLM to sum a column is the most common way a
digest like this ends up confidently wrong, and nobody checks a summary.

## Workflow 99 — The shared error handler

`workflows/99-error-handler.json`

Set as the **Error Workflow** on every other workflow, so one graph catches all of
them. It posts which workflow failed, which node it stopped at, the error, and a
link to the failed run — then emails as well, because if Slack is the thing that
broke, a Slack alert about it is not much use.

It also **redacts anything key-shaped** out of the error text before forwarding.
Error messages quote request headers surprisingly often, and an alert channel is
almost always wider than the list of people who should see a credential.

---

## Running it

You need Node 18+ for n8n, and Python 3.10+ only for the mock service.

```bash
python services/mock_extract.py            # the stand-in service, 127.0.0.1:8000
npx n8n                                    # http://localhost:5678
npx n8n import:workflow --separate --input=workflows
```

Then in the n8n UI:

1. Open **01 Invoice intake** and hit **Test workflow**. It runs from the
   `Test with a sample PDF` trigger, so you do not need a mailbox or an API key.
2. Open each workflow's **Settings → Error Workflow** and choose
   `99 Error handler`. It is the highest-value setting in n8n and it is off by
   default, which is why so many workflows fail silently.
3. Open the **Settings** node to point alerts at a real Slack webhook.

To watch the error path, change the `Load sample PDF` URL to `.../sample/boom.pdf`:
the mock returns 502, `Extract document` retries three times over ~10 seconds,
gives up, and the error workflow fires.

### Two configuration choices worth knowing about

Both were found by running this, not by reading the docs:

- **No environment variables.** n8n blocks `$env` inside nodes by default and n8n
  cloud will not let you unblock it, so an `$env` expression fails on import for
  most people. Config lives in a **Settings** node instead — which is better for a
  handover anyway, since it is editable in the UI by someone who is not a developer.
- **`127.0.0.1`, not `localhost`.** n8n resolves `localhost` to IPv6 `::1`. A local
  service bound only to IPv4 then refuses the connection, with an error that reads
  as though the service is down.

## Before you commit

```bash
python scripts/check_workflows.py
```

It rejects exports containing a Slack webhook URL, an API key, a private key block
or inline credential data, and it rejects a graph whose connections point at nodes
that are not in the file — which imports without complaint and then fails at run
time, in front of whoever you sent it to.

Wire it in as a hook:

```bash
echo 'python scripts/check_workflows.py' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## What is not here

- **Credentials.** n8n exports reference them by name; you supply your own.
- **A Google Sheet.** The Sheets nodes carry a placeholder document ID; swap in
  yours, or replace the node — nothing downstream depends on Sheets specifically.
- **Anything trained.** No model is fine-tuned here. The LLM steps do
  classification, extraction and summarising through an API, and every one of them
  is bounded by code that checks the result.

## Licence

MIT — see `LICENSE`.
