# How this works — for whoever inherits it

No code in this page. If you can edit a spreadsheet, you can run this.

---

## What it does

An invoice arrives by email. Instead of someone opening it and typing the numbers
into a spreadsheet, the automation reads it and adds the row itself.

With one exception, which is the important part: **if it is not sure about
something, it does not write anything.** It posts a message asking a person to
check, and waits. A blank you have to fill in costs five minutes. A wrong number
that quietly lands in the books costs a great deal more, and by the time anyone
notices, it has been reconciled, reported, and possibly paid.

## The five things on the screen

Open n8n and you will see boxes joined by lines. Read left to right.

| Box | What it does |
|---|---|
| **Email arrives with an invoice** | Watches the mailbox. Only looks at mail with a PDF attached. |
| **Has a PDF attached?** | A reply with no attachment just stops here. That is not an error. |
| **Settings** | The one box you may need to edit. See below. |
| **Extract document** | Sends the PDF off to be read. Tries three times if the internet hiccups. |
| **Safe to post automatically?** | The fork. Confident → spreadsheet. Not confident → ask a person. |

## The only box you might need to change

**Settings.** Double-click it. You will see a short list of web addresses — where
to send alerts, mainly. Change the value, click back, then **Save** at the top
right. Nothing else needs touching.

If someone tells you to "set an environment variable", you do not need to. This
was built without them on purpose, precisely so that changing a setting does not
require a developer or a server restart.

## When something goes wrong

You will get a Slack message that looks like this:

> :rotating_light: **01 Invoice intake** failed
> Stopped at: **Extract document**
> Error: connect ETIMEDOUT
> *Open the failed run*

Three things worth knowing about it:

1. **It names the box that failed.** Find that box on the screen; that is where
   the problem is.
2. **"Open the failed run" shows you exactly what happened**, including the data
   that was going through at the time. Nothing is lost — the email is still in the
   mailbox and can be run again.
3. **It emails as well as posting to Slack.** If Slack itself is the thing that
   broke, a Slack alert about it would not reach you.

## The alert you will not get, and why it matters anyway

There is a second kind of failure that no error message can catch: the automation
does not break, it simply **stops running**. Someone switches it off. A password
expires. The server reboots and never comes back up. Nothing fails, because
nothing ran — so nothing is reported, and everything looks fine.

So the digest workflow sends a short "I ran today" ping to an outside monitoring
service on every run. If that service stops hearing from it, **it** alerts you.
Silence becomes a signal instead of an absence.

This is the single most common gap in automations built by someone else. It is
worth checking for by name if you are ever handed one.

## Reasonable things to do yourself

- **Turn a workflow off** — the Active toggle, top right.
- **Change which Slack channel gets alerts** — the Settings box.
- **Re-run a failed invoice** — Executions in the sidebar, find it, *Retry*.
- **See what ran last night** — Executions. Everything is kept, successes included.

## Things to ask a developer about

- Adding a new tool to the chain.
- Changing what counts as "not confident enough" — that threshold lives in the
  extraction service, deliberately, so it is set in one place rather than in every
  workflow that happens to use it.
- Anything involving credentials or access.

## A note on the AI part

An AI model reads the PDF, and a second one writes the morning summary. Neither
is trusted on its own:

- Every field it reads comes back with a **confidence score and, where relevant, a
  note explaining the doubt** — and either one being present is enough to send the
  document to a human.
- The **arithmetic is done by ordinary code**, not by the model. The totals are
  recomputed and checked against what the invoice claims. If they disagree, that
  is flagged.
- The summary model is **handed the numbers and forbidden from calculating any**.
  Asking an AI to add up a column is the most reliable way to get a summary that
  is confidently, invisibly wrong — and nobody proofreads a summary.

The model is used for the thing it is good at, reading messy documents, and
fenced off from the thing it is bad at, arithmetic.
