"""Extract candidate datasheet facts from a local PDF for technician review.

Never infer pass/fail measurement limits from absolute maximum ratings.
"""
import re
from pathlib import Path

KEYWORDS=("pin configuration","pin assignment","electrical characteristics",
          "test conditions","absolute maximum ratings","package","threshold voltage",
          "forward voltage","on resistance","drain source")
def extract_pdf_candidates(path,part_number=None,max_pages=30):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install optional dependency: pip install pypdf") from exc
    file=Path(path)
    if not file.is_file() or file.suffix.lower()!=".pdf":
        raise ValueError("A local PDF file is required")
    if not 1<=max_pages<=200:
        raise ValueError("Invalid page limit")
    reader=PdfReader(str(file))
    matches=[]
    for page_number,page in enumerate(reader.pages[:max_pages],1):
        content=page.extract_text() or ""
        lines=[re.sub(r"\\s+"," ",line).strip() for line in content.splitlines()]
        for idx,line in enumerate(lines):
            if not line:
                continue
            found=[word for word in KEYWORDS if word in line.lower()]
            if found:
                context=" ".join(lines[max(0,idx-1):min(len(lines),idx+3)])[:600]
                matches.append({"page":page_number,"topic":found[0],
                                "excerpt":context,"verified":False})
                if len(matches)>=150:
                    break
        if len(matches)>=150:
            break
    return {"file":str(file),"part_number_claimed":part_number,
            "pages_scanned":min(len(reader.pages),max_pages),
            "candidates":matches,"measurement_reference":None,
            "warning":"Otomatik PDF metin çıkarımıdır; tablo sütunları ve test koşulları karışabilir. Teknisyen onayı olmadan eşik üretilmez."}
