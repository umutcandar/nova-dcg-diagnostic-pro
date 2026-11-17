"""Local technician review decisions for unverified PCB detector candidates.

A rejected box is NOT a negative electrical diagnosis or training label;
it only means a technician reports no component at that location.
"""
def set_candidate_rejected(task, rejected=True):
    if not isinstance(task, dict):
        raise ValueError("Geçersiz komponent adayı")
    if type(rejected) is not bool:
        raise ValueError("Red kararı doğru/yanlış olmalı")
    task["technician_rejected_candidate"] = rejected
    return task


def review_summary(tasks):
    rejected = sum(t.get("technician_rejected_candidate") is True for t in tasks)
    corrected = sum(t.get("technician_verified_type") is True
                    and not t.get("technician_rejected_candidate") for t in tasks)
    pending = sum(t.get("component") == "Bilinmiyor"
                  and not t.get("technician_rejected_candidate")
                  and not t.get("technician_verified_type") for t in tasks)
    return {
        "source_candidates": len(tasks),
        "visible_candidates": len(tasks) - rejected,
        "manually_rejected": rejected,
        "technician_verified_types": corrected,
        "unresolved_unknowns": pending,
        "warning": "Bu teknik servis düzeltmeleri gerçek model precision/recall metriği değildir.",
    }
