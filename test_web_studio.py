"""Integration tests for the NOVA DCG private web workbench (no model download)."""
import base64
from http.client import HTTPConnection
from io import BytesIO
import json
from threading import Thread
import unittest
from unittest.mock import patch

from PIL import Image
import web_studio


class WebStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_user, cls.original_password = web_studio.AUTH_USER, web_studio.AUTH_PASSWORD
        web_studio.AUTH_USER = "web-test"
        web_studio.AUTH_PASSWORD = "temporary-unittest-credential"
        cls.server = web_studio.ThreadingHTTPServer(("127.0.0.1", 0), web_studio.Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        web_studio.AUTH_USER, web_studio.AUTH_PASSWORD = cls.original_user, cls.original_password

    def request(self, method, path, body=None, headers=None, authorized=True):
        headers = dict(headers or {})
        if authorized:
            credentials = base64.b64encode(b"web-test:temporary-unittest-credential").decode()
            headers["Authorization"] = "Basic " + credentials
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        connection.request(method, path, body=body, headers=headers)
        reply = connection.getresponse()
        data = reply.read()
        status, all_headers = reply.status, dict(reply.getheaders())
        connection.close()
        return status, data, all_headers

    @staticmethod
    def photo():
        with BytesIO() as output:
            Image.new("RGB", (64, 40), (115, 85, 70)).save(output, format="PNG")
            return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()

    def test_health_requires_no_password(self):
        code, body, _ = self.request("GET", "/healthz", authorized=False)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_private_page_rejects_anonymous_get_and_head(self):
        for method in ("GET", "HEAD"):
            with self.subTest(method=method):
                code, _, headers = self.request(method, "/", authorized=False)
                self.assertEqual(code, 401)
                self.assertIn("WWW-Authenticate", headers)

    def test_page_and_query_parameters_work_after_auth(self):
        code, body, headers = self.request("GET", "/?utm_source=check")
        self.assertEqual(code, 200)
        self.assertIn(b"PCB STUDIO", body)
        self.assertIn(b"bbox_xyxy_pixels", body)
        self.assertIn("no-store", headers["Cache-Control"])
        code, body, _ = self.request("HEAD", "/?utm_source=check")
        self.assertEqual(code, 200)
        self.assertEqual(body, b"")

    def test_review_script_is_private_and_available(self):
        code, _, _ = self.request("GET", "/web_review.js", authorized=False)
        self.assertEqual(code, 401)
        code, body, headers = self.request("GET", "/web_review.js")
        self.assertEqual(code, 200)
        self.assertIn(b"trainingAnnotation", body)
        self.assertIn("application/javascript", headers["Content-Type"])
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])

    def test_invalid_data_url_does_not_call_model(self):
        code, body, _ = self.request("POST", "/analyze",
                                     body=json.dumps({"image": "not-an-image"}),
                                     headers={"Content-Type": "application/json"})
        self.assertEqual(code, 400)
        self.assertIn("error", json.loads(body))

    def test_cross_origin_post_is_denied(self):
        code, _, _ = self.request("POST", "/analyze",
                                  body="{}",
                                  headers={"Content-Type": "application/json",
                                           "Origin": "https://other.example"})
        self.assertEqual(code, 403)

    def test_real_png_and_mock_model_return_pixel_boxes(self):
        example = {"label": "Direnç", "source_label": "Resistor",
                   "bbox_xyxy_pixels": [3, 5, 21, 25], "confidence": 0.87}
        from auto_detector import automatic_detect
        with patch("auto_detector.automatic_detect", return_value=[example]) as fake:
            code, body, _ = self.request(
                "POST", "/analyze",
                body=json.dumps({"image": self.photo()}),
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertEqual(payload["image_width"], 64)
        self.assertEqual(payload["image_height"], 40)
        self.assertEqual(payload["detections"][0]["bbox_xyxy_pixels"], [3., 5., 21., 25.])
        self.assertEqual(payload["detections"][0]["label"], "Direnç")
        self.assertFalse(payload["detections"][0]["verified"])
        fake.assert_called_once()

    def test_box_normalization_rejects_invalid_coordinates(self):
        cases = [
            {"label": "Bad", "bbox_xyxy_pixels": [0, 0, float("nan"), 8]},
            {"label": "Bad", "bbox_xyxy_pixels": [5, 6, 2, 3]},
            {"label": "Bad", "bbox": [1, 1, 2, 2]},
        ]
        self.assertEqual(web_studio.normalize_detections(cases, 100, 100), [])

    def test_busy_server_returns_429_not_false_result(self):
        self.assertTrue(web_studio.INFERENCE_SLOT.acquire(blocking=False))
        try:
            code, data, _ = self.request("POST", "/analyze",
                                         body="{}", headers={"Content-Type": "application/json"})
            self.assertEqual(code, 429)
            self.assertIn("error", json.loads(data))
        finally:
            web_studio.INFERENCE_SLOT.release()


if __name__ == "__main__":
    unittest.main()
