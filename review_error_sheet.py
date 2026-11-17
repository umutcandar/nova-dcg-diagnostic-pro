"""Create a local visual review sheet for real labeled PCB benchmark errors.

No images are downloaded or uploaded. A contact sheet only facilitates human
inspection; it does not turn model errors into verified new training labels.
"""
import argparse
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

KINDS = {"false_candidate", "class_confusion", "missed_component"}


def _selected_result(report, threshold):
    if report.get("ground_truth_available") is not True:
        raise ValueError("Gerçek etiketli test sonucu gerekli")
    results = report.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("Test raporunda eşik sonuçları yok")
    matching = [row for row in results
                if isinstance(row, dict)
                and isinstance(row.get("threshold"), (int, float))
                and math.isclose(float(row["threshold"]), threshold, abs_tol=1e-9)]
    if len(matching) != 1:
        raise ValueError("İstenen güven eşiği raporda benzersiz değil veya mevcut değil")
    return matching[0]


def _crop_error(entry, tile_size):
    path = Path(entry.get("image", ""))
    if not path.is_file():
        raise FileNotFoundError(f"Kart görüntüsü bulunamadı: {path}")
    box = entry.get("bbox_xyxy_pixels")
    if not isinstance(box, (tuple, list)) or len(box) != 4:
        raise ValueError("Eksik hata konumu")
    values = [float(v) for v in box]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Geçersiz hata konumu")
    x1, y1, x2, y2 = values
    with Image.open(path) as image:
        board = ImageOps.exif_transpose(image).convert("RGB")
    if not (0 <= x1 < x2 <= board.width and 0 <= y1 < y2 <= board.height):
        raise ValueError("Fotoğraf sınırları dışında hata kutusu")
    w, h = x2 - x1, y2 - y1
    padding = max(w, h) * .65
    region = (max(0, int(x1-padding)), max(0, int(y1-padding)),
              min(board.width, int(math.ceil(x2+padding))),
              min(board.height, int(math.ceil(y2+padding))))
    view = board.crop(region)
    draw = ImageDraw.Draw(view)
    draw.rectangle((x1-region[0], y1-region[1], x2-region[0], y2-region[1]),
                   outline="red", width=max(2, min(view.size)//120))
    view.thumbnail(tile_size, Image.Resampling.LANCZOS)
    return view


def create_review_sheet(report_file, output_png, threshold, *,
                        kinds=KINDS, max_cases=80, columns=4):
    if not isinstance(threshold, (float, int)) or not math.isfinite(threshold):
        raise ValueError("Güven eşiği sayısal olmalı")
    if not isinstance(columns, int) or columns < 1 or columns > 10:
        raise ValueError("Sütun sayısı 1-10 olmalı")
    if not isinstance(max_cases, int) or not 1 <= max_cases <= 1000:
        raise ValueError("Gösterim sınırı 1-1000 olmalı")
    if not kinds or not set(kinds).issubset(KINDS):
        raise ValueError("Geçersiz hata türü")
    report = json.loads(Path(report_file).read_text(encoding="utf-8"))
    result = _selected_result(report, float(threshold))
    cases = [e for e in result.get("error_cases", [])
             if isinstance(e, dict) and e.get("kind") in kinds]
    if not cases:
        raise ValueError("Bu eşikte görüntülenebilir hata örneği yok")
    cases = cases[:max_cases]
    tile_w, tile_h = 260, 220
    rows = math.ceil(len(cases) / columns)
    sheet = Image.new("RGB", (columns * tile_w, rows * tile_h), "#f5f5f5")
    draw = ImageDraw.Draw(sheet)
    for i, entry in enumerate(cases):
        view = _crop_error(entry, (tile_w-18, tile_h-64))
        x = (i % columns) * tile_w
        y = (i // columns) * tile_h
        sheet.paste(view, (x + (tile_w-view.width)//2, y+6))
        kind = entry["kind"]
        # ASCII ID is guaranteed to render with Pillow's bundled font.
        draw.text((x+7, y+tile_h-52), f"#{i+1:03d}  {kind}", fill="#111111")
        draw.text((x+7, y+tile_h-34),
                  f"Board: {str(entry.get('board_id', ''))[:30].encode('ascii','replace').decode()}",
                  fill="#222222")
        draw.text((x+7, y+tile_h-17), "Review actual/predicted labels in JSON", fill="#444444")
    target = Path(output_png)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return {"image": str(target), "shown_errors": len(cases),
            "total_matching_errors": len(result.get("error_cases", [])),
            "threshold": float(threshold),
            "warning": "İnsan incelemesi gereklidir. Görseller yerel diske kaydedilir."}


def main():
    parser = argparse.ArgumentParser(description="Local PCB benchmark error contact sheet")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", default="pcb_error_review.png")
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--max-cases", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(create_review_sheet(args.report,args.output,args.threshold,
                                         max_cases=args.max_cases), ensure_ascii=False))


if __name__ == "__main__":
    main()
