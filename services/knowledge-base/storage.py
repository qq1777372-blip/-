import json
import hashlib
import re
import sqlite3
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "knowledge.db"
LEGACY_FILE = ROOT / "alidocs_import.json"


def connect():
    connection = sqlite3.connect(DATABASE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    return connection


def init_db():
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                updated TEXT NOT NULL DEFAULT '',
                path TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                data_json TEXT NOT NULL,
                import_version INTEGER NOT NULL DEFAULT 0,
                content_length INTEGER NOT NULL DEFAULT 0,
                image_count INTEGER NOT NULL DEFAULT 0,
                block_count INTEGER NOT NULL DEFAULT 0,
                integrity_status TEXT NOT NULL DEFAULT 'ok',
                integrity_issues TEXT NOT NULL DEFAULT '[]',
                synced_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
            CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
            CREATE TABLE IF NOT EXISTS import_jobs (
                name TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL DEFAULT 0,
                pending INTEGER NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                started_at REAL,
                updated_at REAL NOT NULL,
                message TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS import_failures (
                job_name TEXT NOT NULL,
                document_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY(job_name, document_id)
            );
            CREATE TABLE IF NOT EXISTS document_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                change_summary TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                UNIQUE(document_id, version_number)
            );
            CREATE TABLE IF NOT EXISTS image_text (
                document_id TEXT NOT NULL,
                image_path TEXT NOT NULL,
                file_hash TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT NOT NULL DEFAULT '',
                updated_at REAL NOT NULL,
                PRIMARY KEY(document_id, image_path)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
                document_id UNINDEXED, title, path, content, image_text,
                tokenize='unicode61'
            );
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
        if "content_hash" not in columns:
            connection.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
        job_columns = {row[1] for row in connection.execute("PRAGMA table_info(import_jobs)")}
        if "process_id" not in job_columns:
            connection.execute("ALTER TABLE import_jobs ADD COLUMN process_id INTEGER")
        count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        fts_count = connection.execute("SELECT COUNT(*) FROM document_fts").fetchone()[0]
        if count and fts_count != count:
            connection.execute("DELETE FROM document_fts")
            connection.execute(
                "INSERT INTO document_fts(document_id,title,path,content,image_text) SELECT id,title,path,content,'' FROM documents"
            )
    if count == 0 and LEGACY_FILE.exists():
        try:
            payload = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
            for document in payload.get("documents", []):
                upsert_document(document)
        except (OSError, ValueError, json.JSONDecodeError):
            pass


def integrity(document):
    content = str(document.get("content", ""))
    images = document.get("images", []) if isinstance(document.get("images"), list) else []
    blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
    issues = []
    if len(content) < 100:
        issues.append("content_too_short")
    if images and not blocks:
        issues.append("missing_ordered_blocks")
    headings = re.findall(r"(?m)^(?:[一二三四五六七八九十]+、|\d+[）.)、])[^\n]{2,50}", content)
    duplicate_headings = [{"heading": heading, "count": headings.count(heading)} for heading in dict.fromkeys(headings) if headings.count(heading) > 1]
    if duplicate_headings:
        issues.append("duplicate_sections")
    return {
        "content_length": len(content),
        "image_count": len(images),
        "block_count": len(blocks),
        "integrity_status": "warning" if issues else "ok",
        "integrity_issues": issues,
        "integrity_details": {"duplicate_sections": duplicate_headings},
    }


def upsert_document(document):
    metrics = integrity(document)
    payload = {**document, **metrics}
    now = time.time()
    content_hash = hashlib.sha256(json.dumps({
        "title": payload.get("title", ""), "content": payload.get("content", ""),
        "images": payload.get("images", []), "blocks": payload.get("blocks", []),
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    with connect() as connection:
        old = connection.execute("SELECT data_json,content_hash FROM documents WHERE id=?", (payload["id"],)).fetchone()
        if old and old["content_hash"] != content_hash:
            version = connection.execute(
                "SELECT COALESCE(MAX(version_number),0)+1 FROM document_versions WHERE document_id=?",
                (payload["id"],),
            ).fetchone()[0]
            old_data = json.loads(old["data_json"])
            summary = {
                "content_before": len(old_data.get("content", "")), "content_after": len(payload.get("content", "")),
                "images_before": len(old_data.get("images", [])), "images_after": len(payload.get("images", [])),
            }
            connection.execute(
                "INSERT INTO document_versions(document_id,version_number,data_json,change_summary,created_at) VALUES(?,?,?,?,?)",
                (payload["id"], version, old["data_json"], json.dumps(summary, ensure_ascii=False), now),
            )
        connection.execute(
            """
            INSERT INTO documents (
                id, title, category, source, updated, path, content, data_json,
                import_version, content_length, image_count, block_count,
                integrity_status, integrity_issues, synced_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, category=excluded.category, source=excluded.source,
                updated=excluded.updated, path=excluded.path, content=excluded.content,
                data_json=excluded.data_json, import_version=excluded.import_version,
                content_length=excluded.content_length, image_count=excluded.image_count,
                block_count=excluded.block_count, integrity_status=excluded.integrity_status,
                integrity_issues=excluded.integrity_issues, synced_at=excluded.synced_at,
                content_hash=excluded.content_hash
            """,
            (
                payload["id"], payload.get("title", ""), payload.get("category", ""),
                payload.get("source", ""), payload.get("updated", ""), payload.get("path", ""),
                payload.get("content", ""), json.dumps(payload, ensure_ascii=False),
                int(payload.get("image_scan_version", 0)), metrics["content_length"],
                metrics["image_count"], metrics["block_count"], metrics["integrity_status"],
                json.dumps(metrics["integrity_issues"], ensure_ascii=False), now, content_hash,
            ),
        )
        image_text = "\n".join(row[0] for row in connection.execute(
            "SELECT text FROM image_text WHERE document_id=? AND status='completed'", (payload["id"],)
        ))
        connection.execute("DELETE FROM document_fts WHERE document_id=?", (payload["id"],))
        connection.execute(
            "INSERT INTO document_fts(document_id,title,path,content,image_text) VALUES(?,?,?,?,?)",
            (payload["id"], payload.get("title", ""), payload.get("path", ""), payload.get("content", ""), image_text),
        )
    return payload


def list_documents():
    with connect() as connection:
        rows = connection.execute("SELECT data_json FROM documents ORDER BY synced_at DESC").fetchall()
    return [json.loads(row["data_json"]) for row in rows]


def documents_revision():
    with connect() as connection:
        return connection.execute("SELECT MAX(value) FROM (SELECT COALESCE(MAX(synced_at),0) AS value FROM documents UNION ALL SELECT COALESCE(MAX(updated_at),0) FROM image_text)").fetchone()[0]


def integrity_documents(limit=500):
    with connect() as connection:
        rows = connection.execute(
            """SELECT id,title,path,source,content_length,image_count,block_count,
                      integrity_status,integrity_issues,synced_at
               FROM documents WHERE integrity_status != 'ok'
               ORDER BY synced_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["integrity_issues"] = json.loads(item["integrity_issues"])
        document = get_document(item["id"])
        item["integrity_details"] = (document or {}).get("integrity_details", {})
        result.append(item)
    return result


def get_document(document_id):
    with connect() as connection:
        row = connection.execute("SELECT data_json FROM documents WHERE id=?", (document_id,)).fetchone()
    return json.loads(row["data_json"]) if row else None


def document_history(document_id):
    with connect() as connection:
        rows = connection.execute(
            "SELECT version_number,change_summary,created_at FROM document_versions WHERE document_id=? ORDER BY version_number DESC",
            (document_id,),
        ).fetchall()
    return [{**dict(row), "change_summary": json.loads(row["change_summary"])} for row in rows]


def pending_images(limit=100):
    with connect() as connection:
        documents = connection.execute("SELECT id,data_json FROM documents ORDER BY synced_at DESC").fetchall()
        known = {(row[0], row[1]) for row in connection.execute("SELECT document_id,image_path FROM image_text WHERE status='completed'")}
    result = []
    for row in documents:
        document = json.loads(row["data_json"])
        for image in document.get("images", []):
            path = image.get("path", "") if isinstance(image, dict) else str(image)
            if path and (row["id"], path) not in known:
                result.append({"document_id": row["id"], "title": document.get("title", ""), "path": path})
                if len(result) >= limit:
                    return result
    return result


def save_image_text(document_id, image_path, file_hash, text, status="completed", error=""):
    now = time.time()
    with connect() as connection:
        connection.execute(
            """INSERT INTO image_text(document_id,image_path,file_hash,text,status,error,updated_at)
               VALUES(?,?,?,?,?,?,?) ON CONFLICT(document_id,image_path) DO UPDATE SET
               file_hash=excluded.file_hash,text=excluded.text,status=excluded.status,
               error=excluded.error,updated_at=excluded.updated_at""",
            (document_id, image_path, file_hash, text, status, error, now),
        )
        combined = "\n".join(row[0] for row in connection.execute(
            "SELECT text FROM image_text WHERE document_id=? AND status='completed'", (document_id,)
        ))
        connection.execute("UPDATE document_fts SET image_text=? WHERE document_id=?", (combined, document_id))


def image_text_map():
    with connect() as connection:
        rows = connection.execute(
            "SELECT document_id,group_concat(text,'\n') AS text FROM image_text WHERE status='completed' GROUP BY document_id"
        ).fetchall()
    return {row["document_id"]: row["text"] or "" for row in rows}


def fts_search(query, limit=20):
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return []
    expression = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
    try:
        with connect() as connection:
            rows = connection.execute(
                "SELECT document_id,bm25(document_fts) AS rank FROM document_fts WHERE document_fts MATCH ? ORDER BY rank LIMIT ?",
                (expression, limit),
            ).fetchall()
        return {row["document_id"]: -float(row["rank"]) for row in rows}
    except sqlite3.OperationalError:
        return {}


def set_job_process(name, process_id):
    with connect() as connection:
        connection.execute("UPDATE import_jobs SET process_id=?,updated_at=? WHERE name=?", (process_id, time.time(), name))


def document_versions():
    with connect() as connection:
        rows = connection.execute("SELECT id, import_version FROM documents").fetchall()
    return {row["id"]: row["import_version"] for row in rows}


def start_job(name, version, total, pending):
    now = time.time()
    with connect() as connection:
        connection.execute("DELETE FROM import_failures WHERE job_name = ?", (name,))
        connection.execute(
            """INSERT INTO import_jobs(name,status,version,total,pending,completed,failed,started_at,updated_at,message)
               VALUES(?,?,?,?,?,0,0,?,?,?)
               ON CONFLICT(name) DO UPDATE SET status=excluded.status,version=excluded.version,
               total=excluded.total,pending=excluded.pending,completed=0,failed=0,
               started_at=excluded.started_at,updated_at=excluded.updated_at,message=excluded.message""",
            (name, "running", version, total, pending, now, now, ""),
        )


def update_job(name, completed=0, failed=0, status=None, message=""):
    assignments = ["completed=completed+?", "failed=failed+?", "updated_at=?"]
    values = [completed, failed, time.time()]
    if status:
        assignments.append("status=?")
        values.append(status)
    if message:
        assignments.append("message=?")
        values.append(message)
    values.append(name)
    with connect() as connection:
        connection.execute(f"UPDATE import_jobs SET {', '.join(assignments)} WHERE name=?", values)


def pause_running_jobs():
    with connect() as connection:
        connection.execute(
            "UPDATE import_jobs SET status='paused', message='服务重启后等待继续', updated_at=? WHERE status='running'",
            (time.time(),),
        )


def job_status(name):
    with connect() as connection:
        row = connection.execute("SELECT * FROM import_jobs WHERE name=?", (name,)).fetchone()
        documents = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        warnings = connection.execute("SELECT COUNT(*) FROM documents WHERE integrity_status!='ok'").fetchone()[0]
    result = dict(row) if row else {"name": name, "status": "idle", "total": 0, "pending": 0, "completed": 0, "failed": 0}
    result.update({"documents": documents, "warnings": warnings, "running": result.get("status") == "running"})
    return result


def record_failure(job_name, document_id, title, source, error):
    with connect() as connection:
        connection.execute(
            """INSERT INTO import_failures(job_name,document_id,title,source,error,updated_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(job_name,document_id) DO UPDATE SET
               title=excluded.title,source=excluded.source,error=excluded.error,updated_at=excluded.updated_at""",
            (job_name, document_id, title, source, error, time.time()),
        )


def list_failures(name):
    with connect() as connection:
        rows = connection.execute(
            "SELECT document_id AS uuid,title,source,error FROM import_failures WHERE job_name=? ORDER BY updated_at DESC",
            (name,),
        ).fetchall()
    return [dict(row) for row in rows]


init_db()
