"""Automatic, local PCB component detection with a verified public checkpoint.

Image selection is the only routine input. Never infer electronic health, pin
numbers, probe contacts, nominal values or power safety from image recognition.
"""
from pathlib import Path
import hashlib
import importlib.util

from download_and_test_model import download, EXPECTED_SHA256, EXPECTED_SIZE
from model_registry import registered_model, ModelRegistryError

WEIGHTS = Path(__file__).resolve().parent / "models" / "yolov8s_pcb_best.pt"


class DetectorSetupError(RuntimeError):
    pass


def verify_weights(path):
    """Verify the complete checkpoint instead of trusting a filename or size."""
    path = Path(path)
    if not path.is_file() or path.stat().st_size != EXPECTED_SIZE:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == EXPECTED_SHA256


def ensure_weights(path=WEIGHTS, progress=None):
    path = Path(path)
    if verify_weights(path):
        return path
    if path.exists():
        raise DetectorSetupError(
            "Kayıtlı model doğrulanamadı. Dosyayı kendiliğinden kullanmadım: "
            + str(path) + ". Silip uygulamayı yeniden açarak güvenilir kopyayı indirebilirsiniz."
        )
    if progress:
        progress("Eğitilmiş PCB modeli ilk kez indiriliyor (yaklaşık 90 MB).")
    try:
        download(path)
    except (OSError, ValueError, RuntimeError) as exc:
        raise DetectorSetupError(
            "Doğrulanmış PCB modeli indirilemedi: " + str(exc)
            + ". İnternet erişimini kontrol edin; model olmadan tanıma yapılamaz."
        ) from exc
    if not verify_weights(path):
        raise DetectorSetupError("İndirilen modelin SHA256 doğrulaması başarısız.")
    return path


def automatic_detect(image_path, progress=None):
    if not Path(image_path).is_file():
        raise DetectorSetupError("Kart fotoğrafı bulunamadı: " + str(image_path))
    if importlib.util.find_spec("ultralytics") is None:
        raise DetectorSetupError(
            "Otomatik komponent tespiti için Ultralytics kurulu değil. "
            "Proje klasöründeki sanal ortamda: python -m pip install -r requirements.txt"
        )
    try:
        weights = registered_model()
    except ModelRegistryError as exc:
        raise DetectorSetupError(str(exc)) from exc
    if weights is None:
        weights = ensure_weights(progress=progress)
        if progress:
            progress("Doğrulanmış genel PCB modeli kullanılıyor.")
    elif progress:
        progress("Yerel eğitimle oluşturulan V2 modeli doğrulandı; tarama başlıyor.")
    if progress:
        progress("Fotoğraf yapay zekâ modeliyle taranıyor...")
    try:
        from model_inference import detect_components
        detections = detect_components(image_path, weights)
    except Exception as exc:
        raise DetectorSetupError("Fotoğraf taraması başarısız: " + str(exc)) from exc
    if progress:
        progress(f"Tarama tamamlandı: {len(detections)} doğrulanmamış komponent adayı.")
    return detections
