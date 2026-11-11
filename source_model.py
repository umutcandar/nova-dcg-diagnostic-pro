"""Verified source-class adapter for the public PCB YOLOv8s checkpoint.

The source model predicts 10 classes. Preserve those names; never relabel the
weights as if trained on NOVA's 8 classes. Unmapped classes remain explicit.
"""
SOURCE_CLASSES = ["Resistor","Capacitor","Diode","LED","IC","Connector",
                  "Switch/Button","Header","Crystal","Debug/TP"]
SOURCE_TO_NOVA = {
    "Resistor":"Direnç",
    "Capacitor":"Kondansatör",
    "Diode":"Diyot",
    "IC":"Entegre",
    "Connector":"Konnektör",
    "LED":"LED",
    "Switch/Button":"Anahtar",
    "Header":"Header",
    "Crystal":"Kristal",
    "Debug/TP":"Test noktası",
}
def adapt_source_classes(names):
    actual=[names[i] for i in range(len(names))] if isinstance(names,dict) else list(names)
    if actual != SOURCE_CLASSES:
        raise ValueError("Model does not match verified source PCB class order")
    return True

def mapped_label(source_name):
    return SOURCE_TO_NOVA.get(source_name, f"Diğer: {source_name}")
