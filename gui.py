"""NOVA DCG Diagnostic Pro - offline macOS desktop prototype.

Manual Fluke measurements only. No automatic component identification.
"""
import csv
import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from guide import GUIDES, steps_for
from report import create_pdf
from diagnosis import prioritize
from annotator import mark_photo
from component_labeler import launch_labeler
from dataset import export_yolo

def assess(mode, value):
    if value < 0:
        return "Negatif değer geçersiz."
    if mode == "Direnç (Ω)":
        if value < 2:
            return "Çok düşük direnç. Kısa devre olabilir; devre içi paralel yolları kontrol edin."
        return "Direnç kaydedildi. Nominal değer/şema olmadan sağlamlık belirlenemez."
    if mode == "Diyot (V)":
        if value == 0:
            return "0 V okuması: kısa devre olasılığı veya ölçüm koşullarını kontrol edin."
        return "İleri yön gerilimi kaydedildi. Ters yön ve devre dışı ölçüm gerekebilir."
    return "Ölçüm kaydedildi."

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("NOVA DCG Diagnostic Pro V0.2")
        self.root.geometry("850x620")
        self.photo = ""
        self.annotated_photo = ""
        self.entries = []
        main = ttk.Frame(root, padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="NOVA DCG | Diagnostic Pro V0.2", font=("Helvetica", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="Yalnızca enerjisiz, artık gerilimi doğrulanmış düşük gerilimli kartlarda kullanın.", foreground="#a33").pack(anchor="w", pady=(4, 15))
        form = ttk.Frame(main)
        form.pack(fill="x")
        ttk.Label(form, text="Kart / iş no:").grid(row=0, column=0, sticky="w")
        self.job = ttk.Entry(form, width=35)
        self.job.grid(row=0, column=1, padx=8, pady=5, sticky="w")
        ttk.Button(form, text="Kart fotoğrafı seç", command=self.pick_photo).grid(row=0, column=2, padx=8)
        self.photo_label = ttk.Label(form, text="Fotoğraf seçilmedi")
        self.photo_label.grid(row=0, column=3, sticky="w")
        ttk.Label(form, text="Test noktası:").grid(row=1, column=0, sticky="w")
        self.point = ttk.Entry(form, width=35)
        self.point.grid(row=1, column=1, padx=8, pady=5, sticky="w")
        self.mode = ttk.Combobox(form, values=["Direnç (Ω)", "Diyot (V)"], state="readonly", width=18)
        self.mode.current(0)
        self.mode.grid(row=1, column=2, padx=8)
        self.value = ttk.Entry(form, width=15)
        self.value.grid(row=1, column=3, padx=8)
        ttk.Label(form, text="Değer →").grid(row=1, column=4)
        ttk.Button(main, text="Ölçümü kaydet ve değerlendir", command=self.add).pack(anchor="w", pady=10)
        guide_row = ttk.Frame(main)
        guide_row.pack(fill="x", pady=(0, 8))
        ttk.Label(guide_row, text="Kontrol rehberi:").pack(side="left")
        self.component = ttk.Combobox(guide_row, values=list(GUIDES), state="readonly", width=22)
        self.component.current(0)
        self.component.pack(side="left", padx=8)
        ttk.Button(guide_row, text="Ölçüm adımlarını göster", command=self.show_guide).pack(side="left")
        self.table = ttk.Treeview(main, columns=("point","mode","value","note"), show="headings", height=11)
        for key, label, width in [("point","Test noktası",115),("mode","Mod",100),("value","Değer",85),("note","Ön değerlendirme",470)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width)
        self.table.pack(fill="both", expand=True)
        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=12)
        ttk.Button(buttons, text="Etiketleri YOLO aktar", command=self.export_labels).pack(side="left", padx=4)
        ttk.Button(buttons, text="Komponent etiketle", command=self.label_components).pack(side="left", padx=4)
        ttk.Button(buttons, text="Fotoğrafı işaretle", command=self.annotate).pack(side="left", padx=4)
        ttk.Button(buttons, text="Olası kontrolleri sırala", command=self.show_findings).pack(side="left", padx=4)
        ttk.Button(buttons, text="PDF servis raporu", command=self.pdf_report).pack(side="left", padx=4)
        ttk.Button(buttons, text="JSON kaydet", command=lambda:self.export("json")).pack(side="left", padx=4)
        ttk.Button(buttons, text="CSV rapor", command=lambda:self.export("csv")).pack(side="left", padx=4)
        ttk.Button(buttons, text="Ölçümleri temizle", command=self.clear).pack(side="left", padx=4)
        ttk.Label(main, text="Bu sürüm arıza teşhisi yapmaz; yalnızca ölçüm kaydı ve ihtiyatlı uyarılar sunar.", foreground="#555").pack(anchor="w")

    def show_guide(self):
        component = self.component.get()
        steps = steps_for(component)
        messagebox.showinfo("Kontrol rehberi: " + component,
                            "\\n\\n".join(str(i) + ". " + step for i, step in enumerate(steps, 1)))

    def show_findings(self):
        if not self.entries:
            messagebox.showinfo("Ölçüm yok", "Önce en az bir ölçüm girin.")
            return
        findings = prioritize(self.entries)
        content = "\\n\\n".join(
            f"{i}. {f.title} [{f.priority}]\\n{f.reason}\\nSonraki adım: {f.next_step}"
            for i, f in enumerate(findings, 1))
        win = tk.Toplevel(self.root)
        win.title("Ölçüme dayalı kontrol öncelikleri")
        win.geometry("740x430")
        box = tk.Text(win, wrap="word", padx=12, pady=12)
        box.pack(fill="both", expand=True)
        box.insert("1.0", content)
        box.configure(state="disabled")

    def export_labels(self):
        source = filedialog.askopenfilename(
            title="Komponent etiket JSON dosyasını seç", filetypes=[("JSON", "*.json")])
        if not source:
            return
        target = filedialog.asksaveasfilename(
            title="YOLO etiket dosyasını kaydet", defaultextension=".txt",
            filetypes=[("Text", "*.txt")])
        if not target:
            return
        try:
            count = export_yolo(source, target)
            messagebox.showinfo("Etiketler aktarıldı", f"{count} komponent kutusu aktarıldı.")
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Etiket aktarım hatası", str(exc))

    def label_components(self):
        if not self.photo:
            messagebox.showinfo("Fotoğraf gerekli", "Önce kart fotoğrafı seçin.")
            return
        try:
            launch_labeler(self.root, self.photo)
        except Exception as exc:
            messagebox.showerror("Etiketleme hatası", str(exc))

    def annotate(self):
        if not self.photo:
            messagebox.showinfo("Fotoğraf gerekli", "Önce kart fotoğrafı seçin.")
            return
        try:
            mark_photo(self.root, self.photo)
        except Exception as exc:
            messagebox.showerror("Fotoğraf hatası", str(exc))

    def pdf_report(self):
        if not self.entries:
            messagebox.showinfo("Boş rapor", "Önce en az bir ölçüm ekleyin.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            create_pdf(path, self.job.get().strip(), self.entries,
                       self.annotated_photo or self.photo)
            messagebox.showinfo("PDF hazır", path)
        except Exception as exc:
            messagebox.showerror("PDF oluşturulamadı", str(exc))

    def pick_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Fotoğraflar","*.png *.jpg *.jpeg *.heic"),("Tüm dosyalar","*.*")])
        if path:
            self.photo = path
            self.annotated_photo = ""
            self.photo_label.config(text=Path(path).name[:28])

    def add(self):
        try:
            value = float(self.value.get().strip().replace(",","."))
            if not (float("-inf") < value < float("inf")):
                raise ValueError
        except ValueError:
            messagebox.showerror("Hatalı değer", "Geçerli, sonlu bir sayı girin.")
            return
        point = self.point.get().strip()
        if not point:
            messagebox.showerror("Eksik bilgi", "Test noktasını girin.")
            return
        mode = self.mode.get()
        note = assess(mode, value)
        item = {"point":point,"mode":mode,"value":value,"assessment":note}
        self.entries.append(item)
        self.table.insert("", "end", values=(point,mode,value,note))
        self.point.delete(0,"end")
        self.value.delete(0,"end")

    def export(self, kind):
        if not self.entries:
            messagebox.showinfo("Boş rapor", "Önce ölçüm ekleyin.")
            return
        ext = ".json" if kind=="json" else ".csv"
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(kind.upper(), "*"+ext)])
        if not path:
            return
        if kind=="json":
            data = {"job":self.job.get().strip(),"photo_path":self.photo,"created":datetime.now().isoformat(),"measurements":self.entries}
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                writer=csv.DictWriter(f,fieldnames=["point","mode","value","assessment"])
                writer.writeheader()
                writer.writerows(self.entries)
        messagebox.showinfo("Kaydedildi", path)

    def clear(self):
        if messagebox.askyesno("Onay", "Tüm ölçüm kayıtları temizlensin mi?"):
            self.entries.clear()
            for row in self.table.get_children():
                self.table.delete(row)

if __name__=="__main__":
    root=tk.Tk()
    App(root)
    root.mainloop()
