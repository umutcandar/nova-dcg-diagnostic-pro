"""NOVA DCG authenticated PCB web workbench.

Temporary image data is removed at the end of each request. Detection is an
unverified visual suggestion; never infer electrical health from a photo.
"""
import base64
import binascii
import json
import logging
import math
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

LOG = logging.getLogger("nova_web")
logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("NOVA_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
AUTH_USER = os.environ.get("NOVA_AUTH_USER", "")
AUTH_PASSWORD = os.environ.get("NOVA_AUTH_PASSWORD", "")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_BODY_BYTES = 17 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000
INFERENCE_SLOT = BoundedSemaphore(value=1)
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

SECURITY_CSP = (
    "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'none'; img-src 'self' data: blob:; "
    "style-src 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'"
)


class ClientInputError(Exception):
    """A request validation error suitable for a brief user-facing message."""


def normalize_detections(detections, width, height):
    """Emit JSON-compatible, pixel-based boxes matching the displayed image.

    Model results use bbox_xyxy_pixels (NOT bbox/box/xyxy). Do not replace an
    unknown class with an invented name or treat confidence as accuracy.
    """
    if not isinstance(detections, (list, tuple)):
        raise ValueError("Detector must return a list")
    output = []
    for item in detections[:250]:
        if not isinstance(item, dict):
            if not hasattr(item, "__dict__"):
                continue
            item = vars(item)
        box = item.get("bbox_xyxy_pixels")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        try:
            x1, y1, x2, y2 = [float(v) for v in box]
        except (ValueError, TypeError):
            continue
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
            continue
        x1, y1 = max(0.0, x1), max(0.0, y1)
        x2, y2 = min(float(width), x2), min(float(height), y2)
        if x1 >= x2 or y1 >= y2:
            continue
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)) and math.isfinite(confidence):
            confidence = min(1.0, max(0.0, float(confidence)))
        else:
            confidence = None
        alternatives = []
        for alternative in item.get("alternatives", [])[:3]:
            if not isinstance(alternative, dict):
                continue
            value = alternative.get("confidence")
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            if not 0 <= value <= 1:
                continue
            alternatives.append({
                "label": str(alternative.get("label", "Bilinmiyor"))[:80],
                "source_label": str(alternative.get("source_label", ""))[:80],
                "confidence": float(value),
            })
        output.append({
            "label": str(item.get("label", "Bilinmiyor"))[:80],
            "source_label": str(item.get("source_label", ""))[:80],
            "bbox_xyxy_pixels": [x1, y1, x2, y2],
            "confidence": confidence,
            "alternatives": alternatives,
            "source": "model",
            "verified": False,
        })
    return output


def decode_photo(body):
    """Decode a single JPG, PNG or WebP data URL and normalize its orientation."""
    if not isinstance(body, dict):
        raise ClientInputError("Geçersiz JSON verisi.")
    image = body.get("image")
    if not isinstance(image, str) or len(image) > MAX_BODY_BYTES:
        raise ClientInputError("Fotoğraf verisi geçersiz veya çok büyük.")
    if not image.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
        raise ClientInputError("Yalnızca JPG, PNG ve WebP fotoğrafları kabul edilir.")
    try:
        raw = base64.b64decode(image.split(",", 1)[1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ClientInputError("Fotoğraf Base64 kodlaması geçersiz.") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ClientInputError("Fotoğraf boş veya 12 MB sınırını aşıyor.")
    try:
        with Image.open(BytesIO(raw)) as opened:
            if opened.format not in {"JPEG", "PNG", "WEBP"}:
                raise ClientInputError("Desteklenmeyen fotoğraf biçimi.")
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                raise ClientInputError("Fotoğraf çözünürlüğü çok yüksek.")
            image = ImageOps.exif_transpose(opened).convert("RGB")
            return image
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ClientInputError("Fotoğraf okunamadı veya güvenli boyut sınırını aştı.") from exc


class Handler(BaseHTTPRequestHandler):
    server_version = "NovaDCG/2"
    sys_version = ""

    def log_message(self, fmt, *args):
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def base_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", SECURITY_CSP)

    def send_payload(self, code, payload, content_type="application/json", head=False):
        if isinstance(payload, str):
            encoded = payload.encode("utf-8")
        else:
            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.base_headers()
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        if not head:
            self.wfile.write(encoded)

    def require_auth(self):
        header = self.headers.get("Authorization", "")
        valid = False
        if len(header) <= 2048 and header.startswith("Basic ") and AUTH_USER and AUTH_PASSWORD:
            try:
                decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
                user, password = decoded.split(":", 1)
                valid = (
                    secrets.compare_digest(user, AUTH_USER)
                    and secrets.compare_digest(password, AUTH_PASSWORD)
                )
            except (UnicodeError, ValueError, binascii.Error):
                pass
        if valid:
            return False
        self.send_response(401)
        self.base_headers()
        self.send_header("WWW-Authenticate", 'Basic realm="NOVA DCG Private"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def handle_get(self, head=False):
        path = urlsplit(self.path).path
        # Safe, credential-free service readiness for Render health checks.
        if path == "/healthz":
            return self.send_payload(200, {"status": "ok", "app": "nova-dcg-web"}, head=head)
        if self.require_auth():
            return
        if path == "/web_review.js":
            content = (ROOT / "web_review.js").read_text(encoding="utf-8")
            return self.send_payload(200, content, "application/javascript", head=head)
        if path == "/web_component_knowledge.js":
            content = (ROOT / "web_component_knowledge.js").read_text(encoding="utf-8")
            return self.send_payload(200, content, "application/javascript", head=head)
        if path == "/model-status":
            from web_onnx_detector import model_state
            return self.send_payload(200, model_state(), head=head)
        if path == "/":
            content = (ROOT / "web_studio.html").read_text(encoding="utf-8")
            return self.send_payload(200, content, "text/html", head=head)
        return self.send_payload(404, {"error": "Sayfa bulunamadı."}, head=head)

    def do_GET(self):
        self.handle_get()

    def do_HEAD(self):
        self.handle_get(head=True)

    def do_POST(self):
        if self.require_auth():
            return
        if urlsplit(self.path).path != "/analyze":
            return self.send_payload(404, {"error": "Sayfa bulunamadı."})
        # Browser same-origin requests; do not authorize cross-origin POSTs.
        origin = self.headers.get("Origin")
        if origin:
            parts = urlsplit(origin)
            if parts.netloc.lower() != self.headers.get("Host", "").lower() or parts.scheme not in {"https", "http"}:
                return self.send_payload(403, {"error": "İstek kaynağı doğrulanamadı."})
        if self.headers.get("Content-Type", "").split(";", 1)[0].lower().strip() != "application/json":
            return self.send_payload(415, {"error": "JSON gerekli."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_payload(400, {"error": "İstek boyutu geçersiz."})
        if length <= 0 or length > MAX_BODY_BYTES:
            return self.send_payload(413, {"error": "İstek boyutu sınırı aşıldı."})
        if not INFERENCE_SLOT.acquire(blocking=False):
            return self.send_payload(429, {"error": "Başka bir kart taranıyor. Biraz sonra tekrar dene."})
        try:
            try:
                body = json.loads(self.rfile.read(length))
                image = decode_photo(body)
            except (json.JSONDecodeError, UnicodeError, ClientInputError) as exc:
                return self.send_payload(400, {"error": str(exc)})
            with TemporaryDirectory(prefix="nova_pcb_") as directory:
                path = Path(directory) / "board.png"
                width, height = image.size
                image.save(path, format="PNG")
                image.close()
                try:
                    from web_onnx_detector import automatic_detect, OnnxDetectorError
                    detections = automatic_detect(path)
                except OnnxDetectorError as exc:
                    LOG.warning("PCB detector unavailable: %s", type(exc).__name__)
                    return self.send_payload(503, {
                        "error": str(exc)[:350],
                        "manual_mode_available": True,
                    })
                results = normalize_detections(detections, width, height)
                return self.send_payload(200, {
                    "detections": results,
                    "image_width": width,
                    "image_height": height,
                    "model_predictions_unverified": True,
                    "model_name": "pinned_21_class_onnx",
                    "model_class_count": 21,
                })
        except (OSError, ValueError):
            LOG.exception("PCB image processing failed")
            return self.send_payload(422, {"error": "Fotoğraf işlenemedi. Farklı bir görüntü dene."})
        except Exception:
            LOG.exception("PCB inference failed")
            return self.send_payload(500, {"error": "Analiz işlemi başarısız. Logları kontrol et."})
        finally:
            INFERENCE_SLOT.release()


if __name__ == "__main__":
    if not AUTH_USER or len(AUTH_PASSWORD) < 16:
        raise SystemExit("NOVA_AUTH_USER ve en az 16 karakterli NOVA_AUTH_PASSWORD gerekli.")
    if HOST not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("NOVA_BEHIND_HTTPS_PROXY") != "1":
        raise SystemExit("Genel ağa yalnızca HTTPS reverse proxy arkasında bağlan.")
    from threading import Thread
    from web_onnx_detector import warm_up
    Thread(target=warm_up, daemon=True, name="nova_onnx_prewarm").start()
    LOG.info("NOVA DCG private web starting at %s:%s (21-class ONNX CPU)", HOST, PORT)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
