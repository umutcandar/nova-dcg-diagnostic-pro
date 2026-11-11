"""PDF service report. Requires reportlab."""
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

def create_pdf(path, job, measurements, photo_path="", markers=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    font = "Helvetica"
    for candidate in fonts:
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("NovaUnicode", candidate))
                font = "NovaUnicode"
                break
            except Exception:
                pass
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("NovaBody", parent=styles["BodyText"], fontName=font, fontSize=9, leading=13)
    heading = ParagraphStyle("NovaHeading", parent=normal, fontSize=17, leading=22, spaceAfter=10)
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    story = [Paragraph("NOVA DCG | Diagnostic Pro", heading),
             Paragraph("Servis ölçüm raporu - ön değerlendirme", normal),
             Spacer(1, 12),
             Paragraph("İş / kart: " + escape(job or "Belirtilmedi"), normal),
             Paragraph("Tarih: " + datetime.now().strftime("%Y-%m-%d %H:%M"), normal),
             Spacer(1, 12)]
    rows = [[Paragraph(x, normal) for x in ["Nokta", "Mod", "Değer", "Ön değerlendirme"]]]
    for m in measurements:
        rows.append([Paragraph(escape(str(m.get(k,""))), normal) for k in ("point","mode","value","assessment")])
    table = Table(rows, colWidths=[85,85,55,285], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9EDF3")),
                               ("GRID",(0,0),(-1,-1),0.3,colors.grey),
                               ("VALIGN",(0,0),(-1,-1),"TOP"),
                               ("TOPPADDING",(0,0),(-1,-1),6),
                               ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(table)
    if photo_path and Path(photo_path).exists():
        try:
            from PIL import Image as PILImage
            with PILImage.open(photo_path) as pic:
                w,h=pic.size
            factor=min(490/w,260/h,1)
            story.extend([Spacer(1,14), Paragraph("Kart fotoğrafı / işaretli ölçüm noktaları",normal),
                          Spacer(1,6),Image(photo_path,width=w*factor,height=h*factor)])
        except Exception:
            story.extend([Spacer(1,8),Paragraph("Fotoğraf rapora eklenemedi.",normal)])
    story.extend([Spacer(1,14),Paragraph(
        "UYARI: Bu rapor otomatik arıza teşhisi değildir. Devre içi ölçümler paralel yollar nedeniyle yanıltıcı olabilir. "
        "Yalnızca enerjisiz, güvenli kartlar için hazırlanmıştır.",normal)])
    doc.build(story)
