# Public PCB component datasets researched (2026-11-11)

This file records **candidate sources**, not downloaded or validated training data.

## First candidate: wangshnegqi/pcb-component-detection-dataset-yolo
https://github.com/wangshnegqi/pcb-component-detection-dataset-yolo

Repository describes real PCB images with YOLO labels, ten component categories, and YOLOv8s trained weights. Dataset/labels marked CC BY 4.0, model weights marked Apache 2.0. Review LICENSE files and image provenance before commercial use. Its ten class names/order **do not match** NOVA's eight-class mapping; build and test a deliberate mapping before inference or training. Never simply rename a pretrained model's class list.

## Second candidate: Roboflow pcb-board-component
https://universe.roboflow.com/pcbboard/pcb-board-component

Lists resistor, capacitor, diode, transistor, connector, IC, LED, potentiometer. Page indicates CC BY 4.0. Download permissions, version, attribution, and data quality need confirmation. Reported metrics are source claims, not NOVA validation.

## Third candidate: Roboflow PCB-Component-Detection
https://universe.roboflow.com/research-pbbdl/pcb-component-detection-dre7a

Small public-domain-labeled set with resistors, capacitors, diodes, ICs, inductors and others. Verify origin and rights; too small for reliable generalization alone.

## Higher-resolution alternative
https://huggingface.co/datasets/ParsaVictor/pcb-component-detection

YOLO component labels and high-resolution images; author requests contact before commercial redistribution. Review LICENSE.md and suitability before inclusion.

## Do not confuse tasks
DeepPCB and PCB-Defect target PCB *manufacturing defects*, not recognition of mounted electronic components. Do not use them as component labels.

## Next validation steps
1. Check actual file downloadability and licenses.
2. Inspect sample images and bounding boxes for errors.
3. Map source classes to NOVA classes explicitly and discard unsupported classes.
4. Hold out boards not present in training.
5. Evaluate per-class precision, recall and mAP on new boards.
6. Only then train a baseline or connect compatible weights to the app.

No external images or weights have been imported into this repository by this research step.
