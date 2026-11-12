"""Opt-in trusted local model registry for NOVA DCG.

The file is written only after a successful local V2 training + test run.
On every application startup the checkpoint SHA256 is checked before loading.
Model files are PyTorch checkpoints: use only locally trained/trusted weights.
"""
import hashlib
import json
from pathlib import Path

DEFAULT_REGISTRY = Path.home() / ".nova_dcg" / "trained_model.json"


class ModelRegistryError(RuntimeError):
    pass


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def register_trained_model(weights, classes, registry=DEFAULT_REGISTRY):
    weights = Path(weights).expanduser().resolve()
    if not weights.is_file():
        raise FileNotFoundError(weights)
    if not classes or not isinstance(classes, list):
        raise ValueError("Model sınıfları boş olamaz")
    registry = Path(registry).expanduser()
    registry.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "nova-dcg-v2-trained-model",
        "weights": str(weights),
        "sha256": file_sha256(weights),
        "classes": classes,
        "origin": "User-controlled local training",
    }
    temporary = registry.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(registry)
    return payload


def registered_model(registry=DEFAULT_REGISTRY):
    registry = Path(registry).expanduser()
    if not registry.is_file():
        return None
    try:
        data=json.loads(registry.read_text(encoding="utf-8"))
        if data.get("schema") != "nova-dcg-v2-trained-model":
            raise ValueError("Kayıt biçimi tanınmıyor")
        weights=Path(data["weights"]).expanduser().resolve()
        if not weights.is_file():
            raise FileNotFoundError(weights)
        if file_sha256(weights) != data["sha256"]:
            raise ValueError("Model SHA256 uyuşmazlığı")
        return weights
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ModelRegistryError(
            "Kayıtlı V2 model doğrulanamadı. Güvenlik için yüklenmedi: " + str(exc)
        ) from exc
