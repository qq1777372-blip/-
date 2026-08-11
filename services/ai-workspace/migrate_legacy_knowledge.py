import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path

import server


def migrate(source_root: Path):
    source_db = source_root / "knowledge.db"
    if not source_db.is_file():
        raise SystemExit(f"旧知识库不存在: {source_db}")

    backup = server.DB.with_name(f"ai_workspace.before-legacy-knowledge-{time.strftime('%Y%m%d-%H%M%S')}.db")
    shutil.copy2(server.DB, backup)
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    target = server.db()
    categories = {}
    imported = image_refs = missing = 0

    for row in source.execute("SELECT * FROM documents ORDER BY synced_at"):
        payload = json.loads(row["data_json"] or "{}")
        category = (row["category"] or "未分类").strip() or "未分类"
        knowledge_id = "legacy-kb-" + hashlib.sha256(category.encode()).hexdigest()[:16]
        categories[category] = knowledge_id
        target.execute("INSERT OR IGNORE INTO knowledge(id,name,description,created_at) VALUES(?,?,?,?)", (knowledge_id, category, "从旧知识库迁移", int(row["synced_at"] or time.time())))

        images = []
        for image in payload.get("images", []):
            info = image if isinstance(image, dict) else {"path": str(image)}
            relative = str(info.get("path", "")).replace("\\", "/").lstrip("/")
            if not relative: continue
            image_refs += 1
            if not (source_root / relative).is_file(): missing += 1
            images.append({"path": relative, "width": info.get("width"), "height": info.get("height")})

        file_id = "legacy-file-" + hashlib.sha256(row["id"].encode()).hexdigest()[:20]
        ocr = "\n".join(item[0] for item in source.execute("SELECT text FROM image_text WHERE document_id=? AND status='completed'", (row["id"],)))
        content = (row["content"] or "").strip()
        if ocr: content += "\n\n[图片文字]\n" + ocr
        blocks = []
        for block in payload.get("blocks", []):
            if not isinstance(block, dict) or block.get("type") not in ("text", "image"): continue
            if block.get("type") == "text": blocks.append({"type": "text", "text": str(block.get("text", ""))})
            else: blocks.append({"type": "image", "path": str(block.get("path", "")).replace("\\", "/").lstrip("/"), "width": block.get("width"), "height": block.get("height")})
        metadata = json.dumps({"legacy_id": row["id"], "path": row["path"], "updated": row["updated"], "images": images, "blocks": blocks}, ensure_ascii=False)
        target.execute("INSERT INTO files(id,knowledge_id,name,content,path,status,created_at,source,metadata) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET knowledge_id=excluded.knowledge_id,name=excluded.name,content=excluded.content,status=excluded.status,source=excluded.source,metadata=excluded.metadata", (file_id, knowledge_id, row["title"], content, "", "ready", int(row["synced_at"] or time.time()), row["source"], metadata))
        server.index_file(target, file_id, row["title"], content)
        imported += 1
        if imported % 50 == 0: target.commit(); print(f"已迁移 {imported} 篇")

    assets = source_root / "alidocs_images"
    destination = server.LEGACY_ASSETS / "alidocs_images"
    if assets.is_dir(): shutil.copytree(assets, destination, dirs_exist_ok=True)
    target.commit(); target.close(); source.close()
    print(json.dumps({"backup": str(backup), "documents": imported, "categories": len(categories), "image_refs": image_refs, "missing_images": missing, "assets": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path.home() / "ai-knowledge-web")
    migrate(parser.parse_args().source_root.resolve())
