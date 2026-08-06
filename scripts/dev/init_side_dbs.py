"""Create the four side sqlite databases in a local directory.

main.py defaults these four paths to `/srv/fastapiproject/...`, the production
layout, so on a dev box every endpoint that touches one fails: two of them raise
`unable to open database file`, and the rule catalog answers 503 because it
checks `db_path.exists()` and gives up.

Two of the four bootstrap their own schema (`ensure_product_parse_cache_db`,
`ensure_publish_failure_report_db`) and only need a writable path. The rule
catalog does not -- it only ever reads and updates, so the tables have to exist
before the first request. Its schema is mirrored from the INSERT statements in
main.py (see `category_rules` around main.py:4456 and
`category_name_dictionary` around main.py:4545).
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Same layout as production, just rooted at a local directory, so the env vars
# the launcher exports differ from the deployed ones only by prefix.
#
# SYCM_DATA_DB_PATH is deliberately NOT here: seed_dev_data.py already writes
# dev_sycm.db at the repo root, and creating a second empty one under this root
# would leave the 生意参谋 workbench showing no shops at all.
LAYOUT = {
    "RULE_CATALOG_DB_PATH": Path("rule_catalog/data/category_rules.db"),
    "PRODUCT_PARSE_CACHE_DB_PATH": Path("product_parse_cache/product_parse_cache.db"),
    "PUBLISH_FAILURE_REPORT_DB_PATH": Path("publish_failure_reports/publish_failure_reports.db"),
}

# Where seed_dev_data.py puts the 生意参谋 database (its --sycm-db default).
SEEDED_SYCM_DB = PROJECT_ROOT / "dev_sycm.db"

RULE_CATALOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS category_rules (
    platform TEXT NOT NULL,
    category_id TEXT NOT NULL,
    category_name TEXT NOT NULL DEFAULT '',
    has_explicit_package INTEGER NOT NULL DEFAULT 0,
    is_customized INTEGER NOT NULL DEFAULT 0,
    default_rule_json TEXT NOT NULL DEFAULT '',
    current_rule_json TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    fetch_status TEXT NOT NULL DEFAULT 'unfetched',
    last_fetch_error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (platform, category_id)
);
CREATE TABLE IF NOT EXISTS category_name_dictionary (
    platform TEXT NOT NULL,
    category_id TEXT NOT NULL,
    category_name TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    is_verified INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (platform, category_id)
);
"""

# A couple of rows so the 规则目录 pages render something instead of 404.
SAMPLE_RULES = [
    ("taobao", "50010850", "女装/女士精品"),
    ("taobao", "50006842", "居家日用"),
    ("pdd", "1", "开发用假类目"),
]


def resolve_root(root: str | None) -> Path:
    return Path(root).resolve() if root else PROJECT_ROOT / "_dev_side_dbs"


def init(root: Path, *, with_samples: bool = True) -> dict[str, Path]:
    created: dict[str, Path] = {}
    for env_name, relative in LAYOUT.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        created[env_name] = target

    # page_imports is a directory the rule catalog writes into, not a table.
    (root / "rule_catalog" / "data" / "page_imports").mkdir(parents=True, exist_ok=True)

    rule_db = created["RULE_CATALOG_DB_PATH"]
    with sqlite3.connect(rule_db) as connection:
        connection.executescript(RULE_CATALOG_SCHEMA)
        if with_samples:
            placeholder = '{"note": "dev placeholder rule"}'
            for platform, category_id, category_name in SAMPLE_RULES:
                connection.execute(
                    "INSERT OR IGNORE INTO category_rules ("
                    "platform, category_id, category_name, has_explicit_package, is_customized,"
                    "default_rule_json, current_rule_json, updated_at, fetch_status, last_fetch_error"
                    ") VALUES (?, ?, ?, 0, 0, ?, ?, '2026-01-01T00:00:00', 'success', '')",
                    (platform, category_id, category_name, placeholder, placeholder),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO category_name_dictionary ("
                    "platform, category_id, category_name, source, is_verified,"
                    "first_seen_at, last_seen_at"
                    ") VALUES (?, ?, ?, 'dev-seed', 1, '2026-01-01T00:00:00', '2026-01-01T00:00:00')",
                    (platform, category_id, category_name),
                )
        connection.commit()

    # These two bootstrap their own schema on first use (ensure_*_db in main.py);
    # creating the file here just means the launcher can print a path that
    # already exists instead of one that appears only after the first request.
    for env_name in ("PRODUCT_PARSE_CACHE_DB_PATH", "PUBLISH_FAILURE_REPORT_DB_PATH"):
        with sqlite3.connect(created[env_name]):
            pass

    return created


def env_for(root: Path) -> dict[str, str]:
    """Every side-DB env var the backend needs, including the seeded sycm one."""
    created = {name: str(root / relative) for name, relative in LAYOUT.items()}
    created["SYCM_DATA_DB_PATH"] = str(SEEDED_SYCM_DB)
    return created


def env_for(root: Path) -> dict[str, str]:
    """The env vars a locally-run backend needs, as strings.

    The launcher imports this instead of rebuilding the paths, so the four
    values can never drift between "what was created" and "what was exported".
    """
    mapping = {env_name: str(root / relative) for env_name, relative in LAYOUT.items()}
    mapping["SYCM_DATA_DB_PATH"] = str(SEEDED_SYCM_DB)
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="directory to hold the side DBs")
    parser.add_argument("--no-samples", action="store_true", help="skip the sample rule rows")
    args = parser.parse_args()

    root = resolve_root(args.root)
    init(root, with_samples=not args.no_samples)
    print(f"side DB root: {root}")
    for env_name, path in env_for(root).items():
        suffix = "  (seeded by seed_dev_data.py)" if env_name == "SYCM_DATA_DB_PATH" else ""
        print(f"  {env_name}={path}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
