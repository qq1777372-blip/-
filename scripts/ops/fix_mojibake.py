"""Repair GBK-misdecoded Chinese literals in the Python sources.

Some strings were written UTF-8, read back as GBK, then re-saved as UTF-8. The
files stay valid UTF-8, so neither the compiler nor the tests notice, but users
see mojibake in API error messages and in the Excel export column headers.

Recovery is the inverse of the corruption: encode the mangled text as GBK to get
the original UTF-8 bytes back, then decode those as UTF-8. A replacement is only
applied when that round trip succeeds AND yields CJK, so anything that is not
actually mojibake is left untouched.

Usage:
    python scripts/ops/fix_mojibake.py --check    # report only, exit 1 if found
    python scripts/ops/fix_mojibake.py --write    # apply repairs in place
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TARGETS = (
    "main.py",
    "app/api/routes/device_license_records.py",
    "app/api/routes/peer_shops.py",
)

# Quoted string bodies, single or double quoted, no escapes or newlines inside.
STRING_PATTERN = re.compile(r"""(['"])([^'"\n]{2,}?)\1""")
CJK_PATTERN = re.compile(r"[一-鿿]")


def recover(text: str) -> str | None:
    """Return the repaired text, or None when `text` is not mojibake."""
    if not CJK_PATTERN.search(text):
        return None
    try:
        candidate = text.encode("gbk").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    if not CJK_PATTERN.search(candidate):
        return None
    return candidate


def process(path: Path) -> list[tuple[int, str, str]]:
    original = io.open(path, encoding="utf-8").read()
    findings: list[tuple[int, str, str]] = []

    def substitute(match: re.Match[str]) -> str:
        quote, body = match.group(1), match.group(2)
        fixed = recover(body)
        if fixed is None:
            return match.group(0)
        line = original.count("\n", 0, match.start()) + 1
        findings.append((line, body, fixed))
        return f"{quote}{fixed}{quote}"

    repaired = STRING_PATTERN.sub(substitute, original)
    if findings and repaired != original:
        process.pending[path] = repaired  # type: ignore[attr-defined]
    return findings


process.pending = {}  # type: ignore[attr-defined]


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()

    total = 0
    for name in TARGETS:
        path = REPO_ROOT / name
        if not path.is_file():
            print(f"skip (missing): {name}")
            continue
        findings = process(path)
        total += len(findings)
        for line, before, after in findings:
            print(f"{name}:{line}\n    {before}\n    -> {after}")

    if not total:
        print("no mojibake found")
        return 0

    if args.write:
        for path, repaired in process.pending.items():  # type: ignore[attr-defined]
            io.open(path, "w", encoding="utf-8", newline="").write(repaired)
        print(f"\nrepaired {total} strings in {len(process.pending)} files")  # type: ignore[attr-defined]
        return 0

    print(f"\n{total} mojibake strings found (run with --write to repair)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
