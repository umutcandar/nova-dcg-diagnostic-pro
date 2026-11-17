"""Real Chromium UI + authenticated HTTP smoke tests for NOVA DCG web.

Uses disposable Basic Auth credentials on a localhost server, NEVER a live
password. Browser model replies are deliberately deterministic so UI tests
can pinpoint component #7 and human review behavior independently of
machine-learning variability.

A separate official source-image test performs REAL pinned ONNX inference
against the same localhost HTTP API. No PCB images are retained on server.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from http.client import HTTPConnection
from io import BytesIO
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from PIL import Image
from playwright.sync_api import sync_playwright
import web_studio

PASSWORD = "ci-test-credential-not-production-only"
USERNAME = "ci-tester"
TIMEOUT = 200


class BrowserAndRealInferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = (web_studio.AUTH_USER, web_studio.AUTH_PASSWORD)
        web_studio.AUTH_USER = USERNAME
        web_studio.AUTH_PASSWORD = PASSWORD
        cls.server = web_studio.ThreadingHTTPServer(("127.0.0.1", 0), web_studio.Handler)
        cls.host = "127.0.0.1"
        cls.port = cls.server.server_port
        cls.root = f"http://{cls.host}:{cls.port}"
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.temp = tempfile.TemporaryDirectory()
        cls.file = Path(cls.temp.name)/"pcb_test_4k.png"
        Image.new("RGB", (4096, 3072), (25,80,60)).save(cls.file)
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        cls.context = cls.browser.new_context(
            http_credentials={"username": USERNAME, "password": PASSWORD},
            accept_downloads=True, viewport={"width":1300,"height":850})
        cls.errors = []
        cls.page = cls.context.new_page()
        cls.page.on("pageerror", lambda error: cls.errors.append(str(error)))

    @classmethod
    def tearDownClass(cls):
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()
        web_studio.AUTH_USER, web_studio.AUTH_PASSWORD = cls.old

    def test_public_health_and_locked_down_private_endpoints(self):
        with urlopen(self.root+"/healthz",timeout=12) as reply:
            self.assertEqual(reply.status,200)
            self.assertEqual(json.load(reply)["status"],"ok")
        for endpoint in ("/","/model-status","/web_component_knowledge.js"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(HTTPError) as error:
                    urlopen(self.root+endpoint,timeout=12)
                self.assertEqual(error.exception.code,401)
        with self.assertRaises(HTTPError) as error:
            request = Request(self.root+"/analyze", data=b"{}",
                              headers={"Content-Type":"application/json"},method="POST")
            urlopen(request,timeout=12)
        self.assertEqual(error.exception.code,401)

    @staticmethod
    def model_detections():
        candidates=[]
        for index in range(6):
            candidates.append({
                "label":"Direnç", "source_label":"resistor", "confidence":.70,
                "bbox_xyxy_pixels":[15+index*220,35,115+index*220,115],
                "alternatives":[], "review_required":False,"review_note":"",
            })
        candidates.append({
            "label":"Diyot", "source_label":"diode", "confidence":.47,
            "bbox_xyxy_pixels":[260,230,330,410],
            "alternatives":[
                {"label":"Diyot","confidence":.47,"source_label":"diode"},
                {"label":"Kondansatör","confidence":.38,"source_label":"capacitor"},
            ],
            "review_required":True,
            "review_note":"Diyot ve kondansatör model skorları yakın; parçanın türünü doğrula.",
        })
        return candidates

    def install_fake_detector(self, record):
        def handle(route):
            payload=json.loads(route.request.post_data)
            source=payload["image"]
            self.assertTrue(source.startswith("data:image/jpeg;base64,"))
            with Image.open(BytesIO(base64.b64decode(source.split(",",1)[1]))) as photo:
                record.append(photo.size)
                w,h=photo.size
            result={
                "detections":self.model_detections(),
                "image_width":w,"image_height":h,
                "model_predictions_unverified":True,
                "model_name":"pinned_21_class_onnx",
                "model_class_count":21,
                "inference_mode":"tiled_detail",
            }
            route.fulfill(status=200, content_type="application/json",body=json.dumps(result))
        self.page.route("**/analyze",handle)

    def test_real_chromium_photo_review_fluke_and_saved_correction(self):
        dimensions=[]
        self.install_fake_detector(dimensions)
        self.page.goto(self.root+"/",wait_until="domcontentloaded")
        self.assertIn("NOVA DCG",self.page.title())
        self.page.locator("#file").set_input_files(self.file)
        self.page.wait_for_function(
            "() => document.querySelector('#count').textContent.includes('7 aday')",
            timeout=30000,
        )
        self.assertEqual(dimensions[-1],(4096,3072))  # No lossy 1600 px thumbnail.
        self.assertIn("7. Diyot",self.page.locator("#results").inner_text())
        self.assertTrue(self.page.locator("#modelAlternatives").is_visible())
        self.assertIn("Parça türü kontrol edilmeli",
                      self.page.locator("#modelAlternatives").inner_text())
        self.assertIn("Kondansatör",self.page.locator("#modelAlternatives").inner_text())
        self.page.get_by_role("button",name=re.compile(r"Kondansatör seç ve doğrula")).click()
        self.assertIn("7. Kondansatör",self.page.locator("#results").inner_text())
        self.assertIn("Teknisyen onayı",self.page.locator("#results").inner_text())
        self.assertIn("Kapasitans",self.page.locator("#guide").inner_text())
        artifact=Path("artifacts")
        artifact.mkdir(exist_ok=True)
        self.page.screenshot(path=str(artifact/"browser_7_capacitor_verified.png"),full_page=True)
        self.page.locator("#value").fill("10,3")
        self.page.locator("#saveReading").click()
        self.assertIn("Ölçüm kaydedildi",self.page.locator("#assessment").inner_text())
        self.assertIn("Kondansatör",self.page.locator("#history").inner_text())
        # This is a browser-local correction tied to the exact same picture.
        self.page.reload(wait_until="domcontentloaded")
        self.page.locator("#file").set_input_files(self.file)
        self.page.wait_for_function(
            "() => document.querySelector('#results').innerText.includes('7. Kondansatör')",
            timeout=30000,
        )
        self.assertIn("Teknisyen onayı",self.page.locator("#results").inner_text())
        # The application selects the first unreviewed candidate by design.
        # Select saved component 7 explicitly before asserting its Fluke guide.
        self.page.locator("#results .item").nth(6).click()
        self.assertEqual(self.page.locator("#partType").input_value(),"Kondansatör")
        self.assertIn("Kapasitans",self.page.locator("#guide").inner_text())
        self.assertTrue(self.page.locator("#confirmed").is_checked())
        self.assertFalse(self.errors, "JavaScript errors: "+repr(self.errors))
        self.page.unroute("**/analyze")

    def test_real_onnx_prediction_on_public_annotated_photo(self):
        source = os.environ.get("NOVA_PUBLIC_PCB_TEST_IMAGE")
        if not source or not Path(source).is_file():
            self.skipTest("Public annotated validation photo not supplied")
        path=Path(source)
        with Image.open(path) as img:
            rgb=img.convert("RGB")
            expected=rgb.size
            output=BytesIO()
            rgb.save(output,format="JPEG",quality=87)
            encoded="data:image/jpeg;base64,"+base64.b64encode(output.getvalue()).decode()
        data=json.dumps({"image":encoded}).encode()
        authorization=base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()
        connection=HTTPConnection("127.0.0.1",self.port,timeout=TIMEOUT)
        started=time.monotonic()
        try:
            connection.request("POST","/analyze",body=data,headers={
                "Content-Type":"application/json",
                "Authorization":"Basic "+authorization,
            })
            response=connection.getresponse()
            status=response.status
            content=response.read()
        finally:
            connection.close()
        self.assertEqual(status,200,content.decode(errors="replace")[:300])
        payload=json.loads(content)
        self.assertEqual((payload["image_width"],payload["image_height"]),expected)
        self.assertEqual(payload["model_class_count"],21)
        self.assertEqual(payload["model_name"],"pinned_21_class_onnx")
        self.assertEqual(payload["inference_mode"],"standard")
        self.assertTrue(payload["model_predictions_unverified"])
        self.assertIsInstance(payload["detections"],list)
        # Real public PCB examples must produce actual candidates; failure may
        # indicate a broken weights download or output adapter.
        self.assertGreater(len(payload["detections"]),0)
        for x in payload["detections"]:
            self.assertEqual(len(x["bbox_xyxy_pixels"]),4)
            self.assertFalse(x["verified"])
            self.assertIn("review_required",x)
            self.assertIn("review_note",x)
            self.assertGreaterEqual(x["confidence"],0.28)
        print("REAL PHOTO",str(path.name),"resolution",expected,
              "detections",len(payload["detections"]),
              "elapsed_seconds",round(time.monotonic()-started,2),flush=True)


if __name__=="__main__":
    unittest.main(verbosity=2)
