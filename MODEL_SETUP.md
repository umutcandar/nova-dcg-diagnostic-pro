# Optional trained YOLO model integration (V0.8)

**No model weights are bundled.** NOVA DCG cannot automatically recognize components until you supply a compatible trained and independently validated `.pt` weights file.

1. Collect and review permitted PCB photos and accurate labels.
2. Split train/validation/test by board identity to avoid leakage.
3. Train an object detector with the exact classes and order from `dataset.CLASSES`.
4. Evaluate precision, recall, mAP, false positives and performance on unseen boards.
5. Install optional inference dependency: `python3 -m pip install ultralytics`.
6. In the app choose a PCB photo and a trained `.pt` weights file, then select **Model ile tara**.

Results are **unverified suggestions** and are not fault diagnoses. Review every box before using it. Inference runs locally, but installing third-party dependencies may involve external downloads. Never use model output as justification for energized measurements.
