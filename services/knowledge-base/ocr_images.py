import argparse
import hashlib
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

import storage


ROOT = Path(__file__).resolve().parent


def recognize(limit):
    engine = RapidOCR()
    completed = failed = 0
    for item in storage.pending_images(limit):
        path = (ROOT / item["path"]).resolve()
        try:
            if not path.is_file() or ROOT.resolve() not in path.parents:
                raise FileNotFoundError(item["path"])
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            result, _ = engine(str(path))
            lines = []
            for row in result or []:
                if len(row) >= 3 and float(row[2]) >= 0.45:
                    lines.append(str(row[1]).strip())
            storage.save_image_text(item["document_id"], item["path"], file_hash, "\n".join(lines))
            completed += 1
            print(f"OCR {completed}/{limit}: {item['title']} - {len(lines)} lines", flush=True)
        except Exception as exc:
            storage.save_image_text(item["document_id"], item["path"], "", "", "failed", str(exc))
            failed += 1
            print(f"OCR FAIL: {item['title']} - {exc}", flush=True)
    return completed, failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    done, errors = recognize(max(1, args.limit))
    print(f"complete: {done} recognized, {errors} failed")
