"""Guard the workflow exports before they are committed.

Two failure modes, both of which have burned people publishing n8n workflows:

1. **Leaked secrets.** An n8n export normally references credentials by name, not by
   value — but a webhook URL typed straight into an HTTP node, an API key pasted into
   a header, or a `credentials` block carrying real data all travel with the JSON.
   Slack webhook URLs are the usual one, because they look like a setting rather than
   a password, and anyone holding one can post into the channel.

2. **A broken graph.** A workflow that references a node that is not in the file
   imports without complaint and then fails at run time, in front of whoever you sent
   it to.

    python scripts/check_workflows.py

Exit code is non-zero if anything is found, so this works as a pre-commit hook:

    echo 'python scripts/check_workflows.py' > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / "workflows"

# Each pattern is a shape that should never appear as a literal in a committed
# export. Anything genuinely needed at run time belongs in $env or a credential.
SECRET_PATTERNS = [
    ("Slack webhook URL", re.compile(r"hooks\.slack\.com/services/T[A-Za-z0-9/+_-]{8,}")),
    ("Discord webhook URL", re.compile(r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    # Negative lookahead on `ant-` so an Anthropic key is not also reported as an
    # OpenAI one. Both still get caught; only the label would have been wrong.
    ("OpenAI key", re.compile(r"sk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Bearer token literal", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("Password assignment", re.compile(r'"password"\s*:\s*"(?!\s*$)[^"{]{4,}"', re.I)),
]


def check(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    raw = path.read_text(encoding="utf-8")

    for label, pattern in SECRET_PATTERNS:
        for hit in pattern.findall(raw):
            snippet = hit if isinstance(hit, str) else str(hit)
            problems.append(f"possible {label}: {snippet[:24]}...")

    try:
        wf = json.loads(raw)
    except json.JSONDecodeError as exc:
        return problems + [f"invalid JSON: {exc}"]

    nodes = wf.get("nodes", [])
    if not nodes:
        problems.append("no nodes")

    names = {n.get("name") for n in nodes}
    ids = [n.get("id") for n in nodes]
    if len(set(ids)) != len(ids):
        problems.append("duplicate node ids")

    for src, outputs in (wf.get("connections") or {}).items():
        if src not in names:
            problems.append(f"connection from a node that does not exist: {src}")
        for group in outputs.get("main", []):
            for conn in group or []:
                if conn.get("node") not in names:
                    problems.append(f"connection to a node that does not exist: {conn.get('node')}")

    for node in nodes:
        # A credentials block naming a credential is correct and expected. One
        # carrying a value is the bug.
        for cred in (node.get("credentials") or {}).values():
            if isinstance(cred, dict) and set(cred) - {"id", "name"}:
                problems.append(f"credential data inline on node {node.get('name')!r}")

    triggers = [n for n in nodes if "trigger" in (n.get("type") or "").lower()]
    if not triggers:
        problems.append("no trigger node — this workflow can never start")

    return problems


def main() -> int:
    files = sorted(WORKFLOWS.glob("*.json"))
    if not files:
        print(f"no workflows found in {WORKFLOWS}", file=sys.stderr)
        return 1

    failed = 0
    for path in files:
        problems = check(path)
        if problems:
            failed += 1
            print(f"FAIL  {path.name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {path.name}")

    print()
    print(f"{len(files) - failed}/{len(files)} clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
