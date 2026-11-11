"""Read-only preflight checks that do not require a model or a Mac."""
import ast
import json
from pathlib import Path

FILES = [
    "diagnostic.py", "gui.py", "guide.py", "diagnosis.py",
    "annotator.py", "component_labeler.py", "dataset.py",
    "model_inference.py", "source_model.py", "prepare_dataset.py",
    "train_model.py", "report.py", "download_and_test_model.py",
]

def check_syntax(base="."):
    base=Path(base)
    results=[]
    for name in FILES:
        path=base/name
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=name)
            results.append({"file":name,"status":"ok"})
        except (SyntaxError,OSError,UnicodeError) as exc:
            results.append({"file":name,"status":"error","message":str(exc)})
    return results

def main():
    results=check_syntax()
    print(json.dumps(results,ensure_ascii=False,indent=2))
    if any(item["status"]!="ok" for item in results):
        raise SystemExit(1)

if __name__=="__main__":
    main()
