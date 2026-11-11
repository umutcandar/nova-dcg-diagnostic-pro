# PCB dataset collection protocol

**Status:** Pipeline only. No PCB photo dataset or trained weights are included.

1. Capture sharp top-down photos of **unpowered, discharged** boards, in varied lighting.
2. Obtain permission to use the images. Remove customer labels, serials, personal data and confidential design markings.
3. For each photo, manually label all visible components using **Komponent etiketle**.
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
