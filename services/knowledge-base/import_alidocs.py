import json
import os
import argparse
import re
import sys
import time
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from playwright.sync_api import sync_playwright
import storage


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "alidocs_import.json"
IMAGE_ROOT = ROOT / "alidocs_images"
IMAGE_SCAN_VERSION = 4
SOURCE_URL = "https://alidocs.dingtalk.com/i/nodes/mExel2BLV59rgdDPi5zm3LdEVgk9rpMq"
ROOT_UUID = "qnYMoO1rWxrkmoj2IMxzDEpmJ47Z3je9"


def clean_text(title, text):
    text = text.replace("\ufeff", "").replace("\u200b", "")
    lines = [line.strip() for line in text.splitlines()]
    start = 0
    occurrences = [i for i, line in enumerate(lines) if line == title]
    if occurrences:
        start = occurrences[-1] + 1
    lines = lines[start:]
    for i, line in enumerate(lines):
        if line.startswith("原语雀文档链接:"):
            start = i + 1
            if start < len(lines) and lines[start].startswith(("http://", "https://")):
                start += 1
            lines = lines[start:]
            break
    stop_markers = ("人赞过", "所有评论", "全文评论", "发表你的评论", "字数统计")
    for i, line in enumerate(lines):
        if any(marker in line for marker in stop_markers):
            lines = lines[:i]
            break
    ignored = ("分享", "登录钉钉文档")
    lines = [line for line in lines if line and line not in ignored and not line.startswith("上次编辑:")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ordered_blocks(text, images):
    for image in images:
        anchor = image.pop("anchor_before", "")
        anchor_index = text.find(anchor) if anchor else -1
        image["text_offset"] = anchor_index + len(anchor) if anchor_index >= 0 else len(text)
    blocks, position = [], 0
    for image in sorted(images, key=lambda item: item["text_offset"]):
        offset = max(position, min(image.pop("text_offset"), len(text)))
        part = text[position:offset].strip()
        if part:
            blocks.append({"type": "text", "text": part})
        blocks.append({"type": "image", **image})
        position = offset
    tail = text[position:].strip()
    if tail:
        blocks.append({"type": "text", "text": tail})
    return blocks


def merge_snapshots(snapshots):
    snapshots = [snapshot.strip() for snapshot in snapshots if snapshot.strip()]
    if not snapshots:
        return ""
    prefix = os.path.commonprefix(snapshots)
    merged = prefix.rstrip()
    for snapshot in snapshots:
        part = snapshot[len(prefix):].strip()
        if not part or part in merged:
            continue
        if merged in part:
            merged = part
            continue
        match = max(SequenceMatcher(None, merged, part, autojunk=False).get_matching_blocks(), key=lambda item: item.size)
        if match.size >= 30:
            addition = part[match.b + match.size:].strip()
            if addition and addition not in merged:
                merged = f"{merged}\n{addition}".strip()
        else:
            merged = f"{merged}\n{part}".strip()
    return merged


def get_catalog(page):
    captured = {}

    def capture(request):
        if "/box/api/v2/dentry/list?" in request.url and not captured:
            captured.update(request.headers)

    page.on("request", capture)
    page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(10000)
    headers = {key: value for key, value in captured.items() if key.lower() in {
        "a-token", "x-xsrf-token", "utm-source", "utm-medium", "accept"
    }}
    if "a-token" not in headers:
        raise RuntimeError("Failed to obtain the temporary DingTalk document token")

    documents = []
    queue = [(ROOT_UUID, [])]
    visited = set()
    while queue:
        parent_uuid, path = queue.pop(0)
        if parent_uuid in visited:
            continue
        visited.add(parent_uuid)
        result = page.evaluate(
            """async ({uuid, headers}) => {
              const response = await fetch('/box/api/v2/dentry/list?dentryUuid=' + uuid, {headers});
              return {status: response.status, data: await response.json()};
            }""",
            {"uuid": parent_uuid, "headers": headers},
        )
        if result["status"] != 200:
            print(f"catalog warning: HTTP {result['status']} for {parent_uuid}")
            continue
        children = result["data"].get("data", {}).get("children", [])
        for item in children:
            name = str(item.get("name", "")).removesuffix(".adoc").strip()
            uuid = item.get("dentryUuid")
            if not uuid or not name:
                continue
            child_path = path + [name]
            if item.get("hasChildren"):
                queue.append((uuid, child_path))
            if item.get("dentryType") != "folder":
                documents.append({"uuid": uuid, "title": name, "path": path})
        print(f"catalog: {len(visited)} folders, {len(documents)} documents", flush=True)
    return documents


def scrape_document(item):
    url = f"https://alidocs.dingtalk.com/i/nodes/{item['uuid']}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6500)
            frames = [frame for frame in page.frames if "/note/" in frame.url]
            if not frames:
                raise RuntimeError("document frame was not loaded")
            frame = frames[-1]
            image_dir = IMAGE_ROOT / item["uuid"]
            image_dir.mkdir(parents=True, exist_ok=True)
            images, snapshots, captured_sources = [], [], set()
            for step in range(21):
                frame.evaluate(
                    """ratio => {
                      const element = [...document.querySelectorAll('*')]
                        .filter(node => node.scrollHeight > node.clientHeight + 300)
                        .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight))[0];
                      if (element) element.scrollTop = (element.scrollHeight - element.clientHeight) * ratio;
                    }""",
                    step / 20,
                )
                page.wait_for_timeout(250)
                snapshots.append(clean_text(item["title"], frame.locator("body").inner_text(timeout=15000)))
                candidates = frame.locator("img")
                visible_indexes = candidates.evaluate_all(
                    """nodes => nodes.map((node, index) => {
                      const rect = node.getBoundingClientRect();
                      return {index, visible: rect.bottom > 0 && rect.top < innerHeight,
                        width: node.naturalWidth, height: node.naturalHeight, source: node.src || ''};
                    }).filter(item => item.visible && item.width >= 160 && item.height >= 100)"""
                )
                for candidate in visible_indexes:
                    index = candidate["index"]
                    image = candidates.nth(index)
                    try:
                        size = {"width": candidate["width"], "height": candidate["height"]}
                        source = candidate["source"]
                        if source in captured_sources:
                            continue
                        filename = f"{len(images) + 1:03d}.png"
                        image.screenshot(path=str(image_dir / filename), timeout=10000)
                        marker = f"[[ZHICE_IMAGE_{len(images)}]]"
                        image.evaluate(
                            """(element, marker) => {
                              const node = document.createElement('div');
                              node.dataset.zhiceImageMarker = '1';
                              node.textContent = marker;
                              element.before(node);
                            }""",
                            marker,
                        )
                        marked_content = clean_text(item["title"], frame.locator("body").inner_text(timeout=15000))
                        text_offset = marked_content.find(marker)
                        image.evaluate("element => element.previousElementSibling?.remove()")
                        if text_offset < 0:
                            continue
                        captured_sources.add(source)
                        images.append({
                            "anchor_before": marked_content[:text_offset][-100:],
                            "path": f"alidocs_images/{item['uuid']}/{filename}",
                            "width": size["width"],
                            "height": size["height"],
                        })
                    except Exception:
                        continue
            content_text = merge_snapshots(snapshots)
            blocks = ordered_blocks(content_text, images)
            content = "\n\n".join(block["text"] for block in blocks if block["type"] == "text")
            if len(content) < 20:
                raise RuntimeError("document body is empty")
            ordered_images = [block for block in blocks if block["type"] == "image"]
            return {
                "id": f"alidocs-{item['uuid']}",
                "title": item["title"],
                "category": "\u5e97\u94fa\u8fd0\u8425",
                "source": url,
                "updated": time.strftime("%Y-%m-%d"),
                "type": "rule",
                "path": " / ".join(item["path"]),
                "content": content,
                "images": [{key: value for key, value in image.items() if key != "type"} for image in ordered_images],
                "blocks": blocks,
                "image_scan_version": IMAGE_SCAN_VERSION,
            }, None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
        finally:
            browser.close()


def save(documents, failures):
    payload = {"source": SOURCE_URL, "documents": documents, "failures": failures}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(document_uuid=None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="msedge")
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        catalog = get_catalog(page)
        browser.close()

    if document_uuid:
        catalog = [item for item in catalog if item["uuid"] == document_uuid]
        if not catalog:
            raise RuntimeError("Document was not found in the DingTalk catalog")
    versions = storage.document_versions()
    pending = [item for item in catalog if versions.get(f"alidocs-{item['uuid']}", 0) != IMAGE_SCAN_VERSION]
    if document_uuid:
        pending = catalog
    failures = []
    job_name = f"alidocs:{document_uuid}" if document_uuid else "alidocs"
    storage.start_job(job_name, IMAGE_SCAN_VERSION, len(catalog), len(pending))
    storage.set_job_process(job_name, os.getpid())
    print(f"starting: {len(catalog)} total, {len(versions)} cached, {len(pending)} pending", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(scrape_document, item): item for item in pending}
        for index, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            document, error = future.result()
            if document:
                storage.upsert_document(document)
                storage.update_job(job_name, completed=1)
                print(f"[{index}/{len(pending)}] OK {item['title']}", flush=True)
            else:
                failures.append({**item, "error": error})
                storage.record_failure(job_name, item["uuid"], item["title"], f"https://alidocs.dingtalk.com/i/nodes/{item['uuid']}", error)
                storage.update_job(job_name, completed=1, failed=1)
                print(f"[{index}/{len(pending)}] FAIL {item['title']}: {error}", flush=True)
    documents = storage.list_documents()
    save(documents, failures)
    storage.update_job(job_name, status="completed", message="导入完成")
    print(f"complete: {len(documents)} imported, {len(failures)} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--document-id", default="")
    args = parser.parse_args()
    sys.exit(main(args.document_id or None))
