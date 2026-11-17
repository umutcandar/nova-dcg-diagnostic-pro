# PCB dataset collection protocol

**Status:** Pipeline only. No PCB photo dataset or trained weights are included.

1. Capture sharp top-down photos of **unpowered, discharged** boards, in varied lighting.
2. Obtain permission to use the images. Remove customer labels, serials, personal data and confidential design markings.
3. For each photo, manually label **all** visible components using **Komponent etiketle**. Check both technician verification and the exhaustive-label checkbox (`annotation_complete: true`). V2 training audit now rejects incomplete images; otherwise unmarked real parts could be learned as background.
4. Add a stable `board_id` to the annotation JSON. Different photos of the same physical PCB **must use the same board_id**.
5. Review boxes and component types manually. The app's `verified: false` field means no second-person verification occurred.
6. Place annotation JSON files and their referenced images in an input directory. Run:
   ```bash
   python3 prepare_dataset.py annotations pcb_dataset
   ```
   At least three distinct board IDs are required. The script makes board-grouped train/val/test splits and creates `data.yaml`, label files and `summary.json`.
7. Inspect split statistics and sample labels before training. For meaningful evaluation, collect many diverse boards per class; three boards only satisfies the script's minimum, not model quality.
8. Optional local training with reviewed data and a user-provided compatible local base model:
   ```bash
   python3 -m pip install ultralytics
   python3 train_model.py pcb_dataset/data.yaml /path/to/local_base_model.pt
   ```
9. Evaluate on unseen boards and independently check errors before using model output in service work.

**No dataset is automatically scraped or generated.** Model licensing, image rights and class mapping must be checked. A trained model can suggest component regions, not diagnose electrical faults.


## Detection benchmark: false positives and capacitor/diode confusion

The labeler now exports `annotation_complete`. This must be `true` (along
with `technician_verified: true`) before an image may contribute to a
false-positive measurement. Mark it only if every visible component is boxed.
An image with only a few annotated parts may be used for training, **not** for
measuring missing or spurious detections.

Keep a separate list of physical board IDs never used for training or model
selection. Do not mix different photos of the same physical PCB between
training and holdout datasets. The evaluator requires a `--holdout-boards`
text file and refuses incomplete, unknown-labeled or unverified images.

```bash
python benchmark_detection.py --annotations annotations \
  --holdout-boards heldout_boards.txt \
  --weights /path/to/compatible.pt --output pcb_holdout_report.json
```

Examine the confusion rows for `Kondansatör -> Diyot` and
`Diyot -> Kondansatör`, plus false positives and missing parts at each
confidence threshold. Do not increase the live detector's threshold based on
one PCB or on confidence numbers alone; compare held-out boards and review
lost components. No actual-board benchmark results are included in the repo.
