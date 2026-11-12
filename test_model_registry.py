import json
import tempfile
import unittest
from pathlib import Path

from model_registry import (
    ModelRegistryError, register_trained_model, registered_model, file_sha256
)


class ModelRegistryTests(unittest.TestCase):
    def test_trained_model_verified_before_loading(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            weights = base / "best.pt"
            weights.write_bytes(b"locally-trained-checkpoint-sample")
            config = base / "registry.json"
            entry = register_trained_model(weights, ["Direnç","Kondansatör"],config)
            self.assertEqual(entry["sha256"], file_sha256(weights))
            self.assertEqual(registered_model(config),weights)

    def test_tampered_weights_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            weights = base / "best.pt"
            weights.write_bytes(b"checkpoint A")
            config = base / "registry.json"
            register_trained_model(weights,["Direnç"],config)
            weights.write_bytes(b"checkpoint B")
            with self.assertRaisesRegex(ModelRegistryError,"SHA256"):
                registered_model(config)

    def test_missing_registration_falls_back(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(registered_model(Path(d)/"missing.json"))

    def test_invalid_registration_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as d:
            config=Path(d)/"registry.json"
            config.write_text(json.dumps({"schema":"unknown"}),encoding="utf-8")
            with self.assertRaises(ModelRegistryError):
                registered_model(config)

if __name__=="__main__":
    unittest.main()
