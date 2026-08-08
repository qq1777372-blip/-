import json
import base64
import io
import hashlib
import mimetypes
import os
import re
import sys
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
import signal
from pypdf import PdfReader
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
import storage

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "ai_config.json"
HOST, PORT = "127.0.0.1", int(os.environ.get("ZHICE_PORT", "8765"))
ALIDOCS_PROCESS = None
OCR_PROCESS = None
SEARCH_CACHE = {"mtime": 0, "chunks": []}
BROWSER_CAPTURES = {}


class PageTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.parts = []
        self.skip = 0
        self.in_title = False
        self.image_sources = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag in ("p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "br"):
            self.parts.append("\n")
        if tag in ("img", "source") and not self.skip:
            source = attributes.get("data-src") or attributes.get("data-original") or attributes.get("src")
            srcset = attributes.get("data-srcset") or attributes.get("srcset")
            if srcset:
                source = srcset.split(",")[-1].strip().split()[0]
            if source:
                self.image_sources.append(source)
                self.parts.append(f"\n[[ZHICE_WEB_IMAGE_{len(self.image_sources) - 1}]]\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.skip:
            return
        text = data.strip()
        if self.in_title and text:
            self.title += text
        elif text:
            self.parts.append(text)


def download_web_images(page_url, sources, limit=24):
    directory_name = hashlib.sha256(page_url.encode("utf-8")).hexdigest()[:20]
    directory = ROOT / "web_import_images" / directory_name
    images, seen = [], set()
    for source in sources:
        image_url = urllib.parse.urljoin(page_url, source)
        parsed = urllib.parse.urlparse(image_url)
        if parsed.scheme not in ("http", "https") or image_url in seen:
            continue
        seen.add(image_url)
        try:
            request = urllib.request.Request(image_url, headers={
                "User-Agent": "Mozilla/5.0 Zhice-Knowledge/1.0",
                "Referer": page_url,
            })
            with urllib.request.urlopen(request, timeout=20) as response:
                mime = response.headers.get_content_type().lower()
                if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                    continue
                raw = response.read(5_000_001)
            if len(raw) < 5_000 or len(raw) > 5_000_000:
                continue
            extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}[mime]
            directory.mkdir(parents=True, exist_ok=True)
            filename = f"{len(images) + 1:03d}{extension}"
            (directory / filename).write_bytes(raw)
            images.append({"path": f"web_import_images/{directory_name}/{filename}", "source": image_url, "source_index": sources.index(source)})
            if len(images) >= limit:
                break
        except (OSError, ValueError, urllib.error.URLError):
            continue
    return images


def web_content_blocks(marked_content, images):
    by_index = {image.pop("source_index"): image for image in images}
    pattern = re.compile(r"\[\[ZHICE_WEB_IMAGE_(\d+)\]\]")
    blocks, position = [], 0
    for match in pattern.finditer(marked_content):
        text = marked_content[position:match.start()].strip()
        if text:
            blocks.append({"type": "text", "text": text})
        image = by_index.get(int(match.group(1)))
        if image:
            blocks.append({"type": "image", **image})
        position = match.end()
    text = marked_content[position:].strip()
    if text:
        blocks.append({"type": "text", "text": text})
    return blocks


def read_webpage(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Zhice-Knowledge/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get_content_type().lower()
        raw = response.read(50_000_001 if content_type == "application/pdf" or url.lower().split("?", 1)[0].endswith(".pdf") else 5_000_001)
        if content_type == "application/pdf" or url.lower().split("?", 1)[0].endswith(".pdf"):
            return read_pdf(url, raw)
        if len(raw) > 5_000_000:
            raise ValueError("网页内容超过 5MB")
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
    parser = PageTextParser()
    parser.feed(html)
    marked_content = "\n".join(line.strip() for line in " ".join(parser.parts).splitlines() if line.strip())
    images = download_web_images(url, parser.image_sources)
    blocks = web_content_blocks(marked_content, images)
    content = "\n\n".join(block["text"] for block in blocks if block["type"] == "text")
    if len(content) < 20:
        raise ValueError("没有读取到有效网页正文，该页可能依赖登录或 JavaScript")
    ordered_images = [{key: value for key, value in block.items() if key != "type"} for block in blocks if block["type"] == "image"]
    return {"title": parser.title.strip() or url, "content": content[:500_000], "source": url, "images": ordered_images, "blocks": blocks}


def read_pdf(url, raw):
    if len(raw) > 50_000_000:
        raise ValueError("PDF 文件超过 50MB")
    reader = PdfReader(io.BytesIO(raw))
    directory_name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    directory = ROOT / "web_import_images" / directory_name
    blocks, images, paragraphs = [], [], []
    for page_number, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            blocks.append({"type": "text", "text": text})
            paragraphs.append(text)
        for image in getattr(page, "images", []):
            try:
                extension = "." + (image.image.format or "png").lower()
                if extension not in (".png", ".jpg", ".jpeg", ".webp"):
                    extension = ".png"
                directory.mkdir(parents=True, exist_ok=True)
                filename = f"page-{page_number:03d}-{len(images) + 1:02d}{extension}"
                (directory / filename).write_bytes(image.data)
                item = {"path": f"web_import_images/{directory_name}/{filename}", "page": page_number}
                images.append(item)
                blocks.append({"type": "image", **item})
            except Exception:
                continue
    content = "\n\n".join(paragraphs).strip()
    if len(content) < 20 and not images:
        raise ValueError("PDF 没有提取到正文或图片")
    return {
        "title": Path(urllib.parse.urlparse(url).path).stem or url,
        "content": content[:500_000], "source": url, "images": images, "blocks": blocks,
    }


def alidocs_status():
    status = storage.job_status("alidocs")
    process_running = bool(ALIDOCS_PROCESS and ALIDOCS_PROCESS.poll() is None)
    if process_running and not status.get("running"):
        status.update({"status": "starting", "running": True, "message": "正在读取钉钉目录"})
    if status.get("status") == "running" and ALIDOCS_PROCESS and ALIDOCS_PROCESS.poll() is not None:
        storage.update_job("alidocs", status="paused", message="导入进程已停止，可继续执行")
        status = storage.job_status("alidocs")
    return status


def search_terms(text):
    clean = re.sub(r"[\s\W_]+", "", str(text).lower(), flags=re.UNICODE)
    terms = set()
    for index, char in enumerate(clean):
        terms.add(char)
        if index + 1 < len(clean):
            terms.add(clean[index:index + 2])
    terms.update(part for part in re.split(r"[\s,.;:!?，。！？；：、]+", str(text).lower()) if len(part) > 1)
    return terms


def split_document(content, limit=1200):
    paragraphs = [part.strip() for part in re.split(r"\n+", content) if part.strip()]
    chunks, current = [], ""
    for paragraph in paragraphs:
        pieces = [paragraph[i:i + limit] for i in range(0, len(paragraph), limit)] or [paragraph]
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > limit:
                chunks.append(current)
                current = ""
            current = f"{current}\n{piece}".strip()
    if current:
        chunks.append(current)
    return chunks or [content[:limit]]


def load_search_chunks():
    revision = storage.documents_revision()
    if SEARCH_CACHE["mtime"] == revision:
        return SEARCH_CACHE["chunks"]
    chunks = []
    image_text = storage.image_text_map()
    for document in storage.list_documents():
        document = {**document, "image_text": image_text.get(document.get("id", ""), "")}
        for index, content in enumerate(split_document(str(document.get("content", "")))):
            chunks.append({**document, "content": content, "chunk_index": index})
    SEARCH_CACHE.update({"mtime": revision, "chunks": chunks})
    return chunks


def search_documents(query, limit=5):
    terms = search_terms(query)
    exact = query.strip().lower()
    ranked = []
    for chunk in load_search_chunks():
        title = str(chunk.get("title", "")).lower()
        path = str(chunk.get("path", "")).lower()
        content = str(chunk.get("content", "")).lower()
        image_content = str(chunk.get("image_text", "")).lower()
        score = sum(8 for term in terms if term in title)
        score += sum(4 for term in terms if term in path)
        score += sum(1 for term in terms if term in content)
        score += sum(2 for term in terms if term in image_content)
        if exact and exact in title:
            score += 30
        elif exact and exact in content:
            score += 15
        if score:
            ranked.append((score, chunk))
    fts_scores = storage.fts_search(query, limit * 3)
    ranked = [(score + fts_scores.get(chunk.get("id", ""), 0) * 0.1, chunk) for score, chunk in ranked]
    ranked.sort(key=lambda item: item[0], reverse=True)
    selected, per_document = [], {}
    for score, chunk in ranked:
        doc_id = chunk.get("id", "")
        if per_document.get(doc_id, 0) >= 1:
            continue
        selected.append({**chunk, "score": score})
        per_document[doc_id] = per_document.get(doc_id, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def load_config():
    default = {"base_url": "https://api.openai.com/v1", "model": "gpt-4.1-mini", "api_key": ""}
    if not CONFIG_FILE.exists():
        return default
    try:
        return {**default, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
    except Exception:
        return default


def public_config(config):
    return {"base_url": config.get("base_url", ""), "model": config.get("model", ""), "has_key": bool(config.get("api_key"))}


def document_image_data(documents, limit=20):
    images = []
    image_roots = [(ROOT / name).resolve() for name in ("alidocs_images", "web_import_images")]
    for document_index, document in enumerate(documents[:5], 1):
        for image_index, item in enumerate(document.get("images", []), 1):
            relative = item.get("path", "") if isinstance(item, dict) else str(item)
            try:
                path = (ROOT / relative).resolve()
                if not any(path == root or root in path.parents for root in image_roots):
                    continue
                if not path.is_file() or path.stat().st_size > 5_000_000:
                    continue
                mime = mimetypes.guess_type(path.name)[0] or "image/png"
                if mime not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
                    continue
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                images.append((f"资料{document_index}的图片{image_index}", f"data:{mime};base64,{encoded}"))
                if len(images) >= limit:
                    return images
            except (OSError, ValueError):
                continue
    return images


class ModelHTTPError(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(f"模型接口返回 HTTP {code}：{detail}")
        self.code, self.detail = code, detail


# 纯文本模型（deepseek-chat 等）收到 image_url 会直接 400，且各家措辞不同：
# DeepSeek 报 "unknown variant `image_url`"，OpenAI 兼容网关多为 "does not
# support image"。命中这些就退回纯文本重试一次，而不是让整次问答失败。
IMAGE_UNSUPPORTED_PATTERN = re.compile(
    r"image_url|image input|not support\w*\s+image|does not support image|vision|multimodal",
    re.I,
)


def call_model(config, question, documents, image=""):
    if not config.get("api_key"):
        raise ValueError("请先在 AI 设置中填写 API Key")
    cached_image_text = storage.image_text_map()
    context = "\n\n".join(
        f"[资料{i + 1}] 标题：{d.get('title', '')}\n来源：{d.get('source', '')}\n更新时间：{d.get('updated', '')}\n内容：{d.get('content', '')}\n图片OCR文字：{cached_image_text.get(d.get('id', ''), '')}\n图文块数量：{len(d.get('blocks', []))}"
        for i, d in enumerate(documents[:5])
    )
    user_text = f"知识资料：\n{context}\n\n用户问题：{question}"
    knowledge_images = document_image_data(documents)
    user_content = user_text
    if image or knowledge_images:
        user_content = [{"type": "text", "text": user_text}]
    if image:
        if not re.match(r"^data:image/(jpeg|png|webp|gif);base64,", image):
            raise ValueError("图片格式不受支持")
        user_content.append({"type": "text", "text": "下面是用户本次提问上传的图片："})
        user_content.append({"type": "image_url", "image_url": {"url": image, "detail": "auto"}})
    for label, data_url in knowledge_images:
        user_content.append({"type": "text", "text": f"下面是{label}，请识别其中的文字和操作信息："})
        user_content.append({"type": "image_url", "image_url": {"url": data_url, "detail": "auto"}})
    system_prompt = (
        "你是淘宝店铺推广运营分析助手。用户上传推广数据截图时，先准确提取可见字段和数值，"
        "再给出面向店铺经营的可执行建议，而不是只复述图片。重点分析展现、点击率、点击、花费、"
        "转化、成交、投入产出比、平均点击成本和关键词/计划状态；指出异常、可能原因、优先级，"
        "并明确写出今天可以执行的操作（加价、降价、暂停、调整预算、优化创意或详情页）。"
        "无法确认的字段标注‘截图无法确认’，不要臆测。只输出整理后的中文最终答案，禁止输出思考过程、"
        "英文草稿、计算过程草稿、提示词或Continue、Need recalc等内部内容。使用以下固定结构输出："
        "一、数据概览；二、核心问题（按优先级）；三、原因判断；四、今天可执行的操作；"
        "五、观察指标与复盘时间。每条操作必须包含对象、动作和幅度；没有足够数据时给出补充数据清单。"
        "标题使用‘一、二、三’格式，每段不超过三句话，避免大段连续文字，不要使用英文标题或Markdown表格。"
    )
    base_url = config["base_url"].rstrip("/")
    urls = [base_url + "/chat/completions"]
    if not base_url.endswith("/v1"):
        urls.append(base_url + "/v1/chat/completions")

    def send(content):
        payload = json.dumps({
            "model": config["model"],
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
        }, ensure_ascii=False).encode("utf-8")
        for index, url in enumerate(urls):
            request = urllib.request.Request(
                url, data=payload, method="POST",
                headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Zhice-Knowledge/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                    content_type = response.headers.get("Content-Type", "")
                    if "json" not in content_type.lower() or raw.lstrip().startswith("<"):
                        if index + 1 < len(urls):
                            continue
                        raise RuntimeError("接口返回了网页而不是 AI 数据，请确认接口地址是否包含 /v1")
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:600]
                try:
                    parsed = json.loads(detail)
                    detail = parsed.get("error", {}).get("message", detail)
                except json.JSONDecodeError:
                    pass
                raise ModelHTTPError(exc.code, detail) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"无法连接模型接口：{exc.reason}") from exc
            except json.JSONDecodeError as exc:
                raise RuntimeError("模型接口返回的不是有效 JSON，请检查接口地址") from exc
        raise RuntimeError("模型接口没有返回有效数据")

    try:
        data = send(user_content)
    except ModelHTTPError as exc:
        # 配的是纯文本模型：去掉知识库配图重试一次。文档的图片 OCR 文字已经拼进
        # 上下文，所以退回纯文本仍能作答。但用户本次上传的截图丢了就答不成，
        # 那种情况如实报错，让用户去换支持视觉的模型。
        if not (isinstance(user_content, list) and IMAGE_UNSUPPORTED_PATTERN.search(exc.detail or "")):
            raise
        if image:
            raise RuntimeError(
                f"当前模型 {config['model']} 不支持图片，无法分析你上传的截图。"
                "请在 AI 设置里换成支持视觉的模型。"
            ) from exc
        data = send(user_text)
    if data is None:
        raise RuntimeError("模型接口没有返回有效数据")
    try:
        message = data["choices"][0]["message"]
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise RuntimeError("模型没有返回最终答案")
        content = re.sub(r"<think>.*?</think>", "", str(content), flags=re.I | re.S)
        content = re.sub(r"(?im)^\s*(need recalc|let's recalc|continue\.?|need mention references|let's formulate).*?$", "", content)
        content = re.sub(r"(?is)\b(?:analysis|reasoning|scratchpad)\s*:\s*.*?(?=\n\s*(?:final|answer)\s*:|$)", "", content)
        return content.strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("模型接口返回格式不兼容") from exc


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        # The server may run through pythonw without stdout/stderr streams.
        return

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 5_000_000:
            raise ValueError("请求内容过大")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == "/api/browser-capture":
            capture_id = urllib.parse.parse_qs(parsed_path.query).get("id", [""])[0]
            capture = BROWSER_CAPTURES.pop(capture_id, None)
            if not capture:
                self.send_json(404, {"ok": False, "error": "采集内容不存在或已被读取"})
            else:
                self.send_json(200, {"ok": True, **capture})
        elif self.path == "/api/config":
            self.send_json(200, public_config(load_config()))
        elif self.path == "/api/status":
            config = load_config()
            self.send_json(200, {"online": True, "configured": bool(config.get("api_key")), "model": config.get("model", ""), "version": "1.1-browser-capture"})
        elif self.path == "/api/alidocs/status":
            self.send_json(200, alidocs_status())
        elif self.path == "/api/alidocs/failures":
            self.send_json(200, {"failures": storage.list_failures("alidocs")})
        elif self.path == "/api/documents":
            self.send_json(200, {"documents": storage.list_documents()})
        elif self.path == "/api/integrity":
            documents = storage.integrity_documents()
            self.send_json(200, {"documents": documents, "count": len(documents)})
        elif self.path.startswith("/api/documents/") and self.path.endswith("/history"):
            document_id = urllib.parse.unquote(self.path[len("/api/documents/"):-len("/history")])
            self.send_json(200, {"history": storage.document_history(document_id)})
        elif self.path == "/api/ocr/status":
            pending = len(storage.pending_images(100000))
            self.send_json(200, {"pending": pending, "running": bool(OCR_PROCESS and OCR_PROCESS.poll() is None)})
        elif self.path == "/api/backup":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                if storage.DATABASE.exists(): archive.write(storage.DATABASE, "knowledge.db")
                for folder in (ROOT / "alidocs_images", ROOT / "web_import_images"):
                    if folder.exists():
                        for file in folder.rglob("*"):
                            if file.is_file(): archive.write(file, str(file.relative_to(ROOT)))
                if CONFIG_FILE.exists(): archive.write(CONFIG_FILE, "ai_config.json")
            body = buffer.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=zhice-backup.zip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        try:
            data = self.read_json()
            if self.path == "/api/config":
                old = load_config()
                base_url, model = str(data.get("base_url", "")).strip(), str(data.get("model", "")).strip()
                if not re.match(r"^https?://", base_url) or not model:
                    raise ValueError("接口地址或模型名称不正确")
                config = {"base_url": base_url, "model": model, "api_key": str(data.get("api_key", "")).strip() or old.get("api_key", "")}
                CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
                self.send_json(200, {"ok": True, **public_config(config)})
            elif self.path == "/api/browser-capture":
                title = str(data.get("title", "")).strip()[:300]
                url = str(data.get("url", "")).strip()[:2000]
                text_content = str(data.get("text", "")).strip()[:100000]
                image = str(data.get("image", ""))
                if not title and not text_content and not image:
                    raise ValueError("没有采集到可分析的页面内容")
                if image and not re.match(r"^data:image/(jpeg|png|webp);base64,", image):
                    raise ValueError("页面截图格式不受支持")
                capture_id = hashlib.sha256(f"{time.time_ns()}:{url}".encode()).hexdigest()[:24]
                BROWSER_CAPTURES[capture_id] = {"title": title, "url": url, "text": text_content, "image": image}
                cutoff = time.time() - 600
                for key, value in list(BROWSER_CAPTURES.items()):
                    if value.get("created", time.time()) < cutoff:
                        BROWSER_CAPTURES.pop(key, None)
                BROWSER_CAPTURES[capture_id]["created"] = time.time()
                self.send_json(200, {"ok": True, "capture_id": capture_id})
            elif self.path == "/api/import-url":
                url = str(data.get("url", "")).strip()
                if not re.match(r"^https?://", url):
                    raise ValueError("请输入有效的 HTTP 或 HTTPS 链接")
                self.send_json(200, {"ok": True, **read_webpage(url)})
            elif self.path == "/api/import-alidocs":
                global ALIDOCS_PROCESS
                status = alidocs_status()
                if not status.get("running") and (not ALIDOCS_PROCESS or ALIDOCS_PROCESS.poll() is not None):
                    python = ROOT.parent / "PycharmProjects" / "PythonProject3" / ".venv" / "Scripts" / "python.exe"
                    executable = str(python if python.exists() else Path(sys.executable))
                    ALIDOCS_PROCESS = subprocess.Popen(
                        [executable, str(ROOT / "import_alidocs.py")], cwd=str(ROOT),
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                self.send_json(202, {"ok": True, **storage.job_status("alidocs"), "running": True})
            elif self.path == "/api/reimport-document":
                document_id = str(data.get("id", ""))
                document = storage.get_document(document_id)
                if not document or not document_id.startswith("alidocs-"):
                    raise ValueError("文档不存在或不支持重新采集")
                if storage.job_status("alidocs").get("running") or (ALIDOCS_PROCESS and ALIDOCS_PROCESS.poll() is None):
                    raise ValueError("全库任务正在运行，请结束后再单篇重新采集")
                python = ROOT.parent / "PycharmProjects" / "PythonProject3" / ".venv" / "Scripts" / "python.exe"
                executable = str(python if python.exists() else Path(sys.executable))
                ALIDOCS_PROCESS = subprocess.Popen(
                    [executable, str(ROOT / "import_alidocs.py"), "--document-id", document_id.removeprefix("alidocs-")],
                    cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                self.send_json(202, {"ok": True, "running": True})
            elif self.path == "/api/ocr/run":
                global OCR_PROCESS
                if OCR_PROCESS and OCR_PROCESS.poll() is None:
                    self.send_json(202, {"ok": True, "running": True})
                else:
                    python = ROOT.parent / "PycharmProjects" / "PythonProject3" / ".venv" / "Scripts" / "python.exe"
                    executable = str(python if python.exists() else Path(sys.executable))
                    OCR_PROCESS = subprocess.Popen(
                        [executable, str(ROOT / "ocr_images.py"), "--limit", str(max(1, min(int(data.get("limit", 50)), 500)))],
                        cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    self.send_json(202, {"ok": True, "running": True})
            elif self.path == "/api/alidocs/control":
                action = str(data.get("action", ""))
                status = storage.job_status("alidocs")
                process_id = status.get("process_id")
                if action in ("pause", "stop") and process_id:
                    try:
                        os.kill(int(process_id), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    storage.update_job("alidocs", status="paused" if action == "pause" else "stopped", message="任务已暂停" if action == "pause" else "任务已停止")
                    self.send_json(200, {"ok": True, "status": action})
                elif action == "resume":
                    if status.get("running"):
                        raise ValueError("任务已经在运行")
                    python = ROOT.parent / "PycharmProjects" / "PythonProject3" / ".venv" / "Scripts" / "python.exe"
                    executable = str(python if python.exists() else Path(sys.executable))
                    ALIDOCS_PROCESS = subprocess.Popen([executable, str(ROOT / "import_alidocs.py")], cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    self.send_json(202, {"ok": True, "running": True})
                else:
                    raise ValueError("当前没有可控制的导入任务")
            elif self.path == "/api/search":
                query = str(data.get("query", "")).strip()
                if not query:
                    raise ValueError("搜索内容不能为空")
                limit = max(1, min(int(data.get("limit", 5)), 10))
                self.send_json(200, {"ok": True, "documents": search_documents(query, limit)})
            elif self.path in ("/api/chat", "/api/test"):
                config = load_config()
                is_test = self.path == "/api/test"
                question = "请只回复：连接成功" if is_test else str(data.get("question", "")).strip()
                documents = [{"title": "连接测试", "source": "系统", "updated": "", "content": "这是一次连接测试。"}] if is_test else data.get("documents", [])
                if not question:
                    raise ValueError("问题不能为空")
                if not documents:
                    raise ValueError("知识库中没有检索到相关资料")
                image = "" if is_test else str(data.get("image", ""))
                self.send_json(200, {"ok": True, "answer": call_model(config, question, documents, image)})
            else:
                self.send_json(404, {"ok": False, "error": "接口不存在"})
        except ValueError as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            self.send_json(502, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    os.chdir(ROOT)
    if not os.environ.get("ZHICE_SKIP_JOB_RECOVERY"):
        storage.pause_running_jobs()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Zhice is running at http://{HOST}:{PORT}")
    if "--no-browser" not in sys.argv:
        webbrowser.open(f"http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
