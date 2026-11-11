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
from model_inference import detect_components
from service_records import save_job, load_job, list_jobs
from component_library import component_info
from check_planner import next_checks

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
        self.root.title("NOVA DCG Diagnostic Pro V1.3")
        self.root.geometry("1100x760")
        self.root.minsize(880, 640)
        self.photo = ""
        self.annotated_photo = ""
        self.entries = []
        main = ttk.Frame(root, padding=18)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="NOVA DCG | Diagnostic Pro V1.3", font=("Helvetica", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="Yalnızca enerjisiz, artık gerilimi doğrulanmış düşük gerilimli kartlarda kullanın.", foreground="#a33").pack(anchor="w", pady=(4, 15))
        form = ttk.Frame(main)
        form.pack(fill="x")
        ttk.Label(form, text="Kart / iş no:").grid(row=0, column=0, sticky="w")
        self.job = ttk.Entry(form, width=35)
        self.job.grid(row=0, column=1, padx=8, pady=5, sticky="w")
        ttk.Button(form, text="Kart fotoğrafı seç", command=self.pick_photo).grid(row=0, column=2, padx=8)
        self.photo_label = ttk.Label(form, text="Fotoğraf seçilmedi")
        self.photo_label.grid(row=0, column=3, sticky="w")
        ttk.Label(form, text="Cihaz modeli:").grid(row=1, column=0, sticky="w")
        self.device_model = ttk.Entry(form, width=35)
        self.device_model.grid(row=1, column=1, padx=8, pady=5, sticky="w")
        ttk.Label(form, text="Arıza açıklaması:").grid(row=2, column=0, sticky="w")
        self.fault_description = ttk.Entry(form, width=65)
        self.fault_description.grid(row=2, column=1, columnspan=3, padx=8, pady=5, sticky="ew")
        ttk.Label(form, text="Test noktası:").grid(row=3, column=0, sticky="w")
        self.point = ttk.Entry(form, width=35)
        self.point.grid(row=3, column=1, padx=8, pady=5, sticky="w")
        self.mode = ttk.Combobox(form, values=["Direnç (Ω)", "Diyot (V)"], state="readonly", width=18)
        self.mode.current(0)
        self.mode.grid(row=3, column=2, padx=8)
        self.value = ttk.Entry(form, width=15)
        self.value.grid(row=3, column=3, padx=8)
        ttk.Label(form, text="Değer →").grid(row=3, column=4)
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
        tabs = ttk.Notebook(main)
        tabs.pack(fill="x", pady=10)
        for title, actions in [
            ("Servis", [
                ("Servis kaydet", self.save_service), ("Servis aç", self.open_service),
                ("PDF servis raporu", self.pdf_report), ("JSON kaydet", lambda: self.export("json")),
                ("CSV rapor", lambda: self.export("csv")), ("Ölçümleri temizle", self.clear)]),
            ("Analiz", [
                ("Komponent bilgisi", self.show_component_info),
                ("Olası kontrolleri sırala", self.show_findings),
                ("Fotoğrafı işaretle", self.annotate)]),
            ("Yapay zekâ / Veri", [
                ("Model ile tara", self.scan_model), ("Komponent etiketle", self.label_components),
                ("Etiketleri YOLO aktar", self.export_labels)])]:
            panel = ttk.Frame(tabs, padding=8)
            tabs.add(panel, text=title)
            for index, (label, callback) in enumerate(actions):
                ttk.Button(panel, text=label, command=callback).grid(
                    row=index // 3, column=index % 3, padx=6, pady=5, sticky="ew")
            for column in range(3):
                panel.columnconfigure(column, weight=1)
        ttk.Label(main, text="Bu sürüm arıza teşhisi yapmaz; yalnızca ölçüm kaydı ve ihtiyatlı uyarılar sunar.", foreground="#555").pack(anchor="w")

    def show_component_info(self):
        name=self.component.get()
        try:
            info=component_info(name)
        except KeyError:
            messagebox.showinfo("Bilgi yok", "Bu komponent için henüz bilgi bulunmuyor.")
            return
        messagebox.showinfo(name, info["function"]+"\\n\\nKontroller:\\n"+
                            "\\n".join("- "+x for x in info["checks"])+"\\n\\nUyarı: "+info["caution"])

    def save_service(self):
        job=self.job.get().strip()
        if not job:
            messagebox.showerror("Eksik bilgi", "Önce iş numarası girin.")
            return
        try:
            path=save_job("service_jobs",job,self.device_model.get().strip() or "Belirtilmedi",
                          measurements=self.entries,model=self.device_model.get(),
                          fault_description=self.fault_description.get())
        except (OSError,ValueError) as exc:
            messagebox.showerror("Kaydetme hatası",str(exc))
            return
        messagebox.showinfo("Servis kaydedildi",str(path))

    def open_service(self):
        jobs=list_jobs("service_jobs")
        if not jobs:
            messagebox.showinfo("Kayıt yok","Kayıtlı servis bulunamadı.")
            return
        win=tk.Toplevel(self.root)
        win.title("Servis kayıtları")
        win.geometry("500x350")
        items=tk.Listbox(win)
        items.pack(fill="both",expand=True)
        for job in jobs:
            items.insert("end",job["job_id"]+" | "+job["updated_at"])
        def select():
            selected=items.curselection()
            if not selected:
                return
            try:
                record=load_job("service_jobs",jobs[selected[0]]["job_id"])
            except (OSError,ValueError) as exc:
                messagebox.showerror("Açma hatası",str(exc))
                return
            self.job.delete(0,"end")
            self.job.insert(0,record["job_id"])
            self.device_model.delete(0,"end")
            self.device_model.insert(0,record.get("model",record.get("device","")))
            self.fault_description.delete(0,"end")
            self.fault_description.insert(0,record.get("fault_description",""))
            self.entries=list(record["measurements"])
            for row in self.table.get_children():
                self.table.delete(row)
            for item in self.entries:
                self.table.insert("","end",values=(item.get("point",""),
                    item.get("mode",""),item.get("value",""),item.get("assessment","")))
            win.destroy()
        ttk.Button(win,text="Seçili kaydı aç",command=select).pack(pady=8)

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
        planned = next_checks(self.entries, self.fault_description.get())
        content = "\\n\\n".join(
            f"{i}. {f.title} [{f.priority}]\\n{f.reason}\\nSonraki adım: {f.next_step}"
            for i, f in enumerate(findings, 1))
        content += "\\n\\nArıza açıklamasına göre ek kontroller:\\n" + "\\n".join(
            "- " + item["title"] + ": " + item["reason"] for item in planned)
        win = tk.Toplevel(self.root)
        win.title("Ölçüme dayalı kontrol öncelikleri")
        win.geometry("740x430")
        box = tk.Text(win, wrap="word", padx=12, pady=12)
        box.pack(fill="both", expand=True)
        box.insert("1.0", content)
        box.configure(state="disabled")

    def scan_model(self):
        if not self.photo:
            messagebox.showinfo("Fotoğraf gerekli", "Önce kart fotoğrafı seçin.")
            return
        weights = filedialog.askopenfilename(
            title="Eğitilmiş YOLO ağırlık dosyasını seç", filetypes=[("YOLO model", "*.pt")])
        if not weights:
            return
        try:
            results = detect_components(self.photo, weights)
        except Exception as exc:
            messagebox.showerror("Model çalıştırılamadı", str(exc))
            return
        win = tk.Toplevel(self.root)
        win.title("Model önerileri - doğrulanmadı")
        win.geometry("760x430")
        box = tk.Text(win, wrap="word", padx=12, pady=12)
        box.pack(fill="both", expand=True)
        lines = ["Model çıktıları doğrulanmamıştır. Bunlar arıza teşhisi değildir.", ""]
        for i, item in enumerate(results, 1):
            lines.append(f"{i}. {item['label']} | güven: {item['confidence']:.1%} | kutu: {item['bbox_xyxy_pixels']}")
        if not results:
            lines.append("Belirlenen eşikte komponent bulunamadı.")
        box.insert("1.0", "\\n".join(lines))
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
