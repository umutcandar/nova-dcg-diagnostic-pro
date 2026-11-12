"""NOVA DCG V2 — single-window photo-first PCB service workspace.

Built on Tk + Pillow: no external theme needed. The detector only *suggests*
visual regions. Verified datasheets and real Fluke readings remain essential.
"""
import json
import math
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog
from PIL import Image, ImageOps, ImageTk

from auto_detector import automatic_detect
from detection_review import ALLOWED, review_detections
from fault_review import review_queue
from guided_measurement import evaluate, measurement_plan
from measurement_guides import instruction_for
from measurement_history import record_measurement, history_text
from multimeter_guides import guide_for
from pcb_viewport import Viewport

BG = "#0B1220"
CARD = "#131D2D"
CARD2 = "#1B2940"
CANVAS = "#0F1929"
LINE = "#273851"
TEXT = "#E8F0FA"
MUTED = "#94A9C2"
CYAN = "#48D5DF"
BLUE = "#3C86F5"
AMBER = "#F6B84D"
GREEN = "#60D6AA"
RED = "#F27E8A"
FONT = "Helvetica"


def action(parent, text, command, color=CARD2, fg=TEXT, width=None):
    return tk.Button(
        parent, text=text, command=command, fg=fg, bg=color,
        activebackground=BLUE, activeforeground="white",
        borderwidth=0, highlightthickness=0, relief="flat",
        cursor="hand2", padx=12, pady=9, font=(FONT, 11, "bold"),
        width=width,
    )


def section(parent, text):
    tk.Label(parent, text=text, fg=MUTED, bg=parent["bg"], anchor="w",
             font=(FONT, 10, "bold")).pack(fill="x", pady=(12, 5))


def note(parent, variable, color=TEXT, height=None):
    label = tk.Label(
        parent, textvariable=variable, bg=parent["bg"], fg=color,
        justify="left", anchor="nw", font=(FONT, 11),
        wraplength=292,
    )
    label.pack(fill="x")
    return label


class Workspace:
    def __init__(self, root):
        self.root = root
        self.root.title("NOVA DCG  |  Diagnostic Studio V2")
        self.root.geometry("1500x900")
        self.root.minsize(1080, 690)
        self.root.configure(bg=BG)
        self.image_path = None
        self.image = None
        self.tasks = []
        self.selected = None
        self.viewport = Viewport()
        self.picture = None
        self.image_status = tk.StringVar(value="PCB fotoğrafını yükleyerek otomatik taramayı başlatın.")
        self.status = tk.StringVar(value="HAZIR  •  Model önerileri kesin arıza teşhisi değildir")
        self.detection_count = tk.StringVar(value="0 komponent")
        self.zoom_text = tk.StringVar(value="100%")
        self.component_title = tk.StringVar(value="Komponent seçilmedi")
        self.component_meta = tk.StringVar(value="Bir kutuyu veya listedeki bir parçayı seçin.")
        self.mode_text = tk.StringVar(value="—")
        self.setup_text = tk.StringVar(value="—")
        self.probes_text = tk.StringVar(value="—")
        self.expected_text = tk.StringVar(value="Doğrulanmış teknik veri bulunmuyor.")
        self.next_text = tk.StringVar(value="—")
        self.measure_result = tk.StringVar(value="Ölçüm yapılmadı.")
        self.nominal = tk.StringVar()
        self.tolerance = tk.StringVar()
        self.unit = tk.StringVar()
        self.reading = tk.StringVar()
        self.verified_nominal = tk.BooleanVar(value=False)
        self.class_choice = tk.StringVar(value="Bilinmiyor")
        self._events = queue.Queue()
        self._scan_number = 0
        self._busy = False
        self._mouse_down = None
        self._dragged = False
        self._render_pending = False
        self._render_job = None
        self._poll_job = None
        self._closed = False
        self._set_theme()
        self._build()
        self.root.bind("<Control-o>", lambda _e: self.choose_photo())
        self.root.bind("<Control-s>", lambda _e: self.save_session())
        self._poll_job = self.root.after(150, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _set_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Nova.Treeview", background=CARD, fieldbackground=CARD,
                        foreground=TEXT, borderwidth=0, rowheight=32,
                        font=(FONT, 11))
        style.configure("Nova.Treeview.Heading", background=CARD2, foreground=MUTED,
                        relief="flat", font=(FONT, 10, "bold"), padding=9)
        style.map("Nova.Treeview", background=[("selected", "#245F96")],
                  foreground=[("selected", "white")])
        style.configure("Nova.TCombobox", padding=7)
        style.configure("Nova.Horizontal.TProgressbar", troughcolor=BG, background=CYAN,
                        borderwidth=0)

    def _build(self):
        header = tk.Frame(self.root, bg=CARD, height=76, padx=22, pady=13)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="NOVA", fg=CYAN, bg=CARD,
                 font=(FONT, 22, "bold")).pack(side="left")
        tk.Label(header, text="DCG", fg=TEXT, bg=CARD,
                 font=(FONT, 22, "bold")).pack(side="left", padx=(4, 15))
        tk.Label(header, text="DIAGNOSTIC STUDIO  /  V2", fg=MUTED, bg=CARD,
                 font=(FONT, 11, "bold")).pack(side="left")
        action(header, "Fotoğraf değiştir", self.choose_photo, BLUE).pack(side="right", padx=(8, 0))
        action(header, "Çalışmayı kaydet", self.save_session).pack(side="right", padx=(8, 0))
        action(header, "Yeniden tara", self.rescan).pack(side="right", padx=(8, 0))

        body = tk.Frame(self.root, bg=BG, padx=14, pady=13)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, minsize=245)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, minsize=340)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=CARD, width=245, padx=13, pady=15)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_propagate(False)
        tk.Label(left, text="KOMPONENTLER", fg=TEXT, bg=CARD,
                 font=(FONT, 12, "bold")).pack(anchor="w")
        note(left, self.detection_count, CYAN)
        self.parts = ttk.Treeview(left, style="Nova.Treeview", show="headings",
                                  columns=("id", "class", "confidence"), selectmode="browse")
        for key, name, w in (("id", "#", 32), ("class", "Tip", 112), ("confidence", "Güven", 64)):
            self.parts.heading(key, text=name)
            self.parts.column(key, width=w, stretch=(key == "class"), anchor="w")
        self.parts.pack(fill="both", expand=True, pady=(16, 8))
        self.parts.bind("<<TreeviewSelect>>", self._select_tree)
        tk.Label(left, text="Sarı kutu: model önerisi\nTurkuaz kutu: seçili parça\nHiçbiri elektriksel doğrulama değildir.",
                 fg=MUTED, bg=CARD, justify="left", anchor="w",
                 font=(FONT, 10)).pack(fill="x", pady=12)
        self.progress = ttk.Progressbar(left, style="Nova.Horizontal.TProgressbar",
                                        mode="indeterminate")
        self.progress.pack(fill="x")
        note(left, self.image_status, MUTED)

        center = tk.Frame(body, bg=CARD, padx=8, pady=8)
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        tools = tk.Frame(center, bg=CARD, height=45)
        tools.pack(fill="x", pady=(0, 8))
        tk.Label(tools, text="PCB GÖRÜNÜMÜ", fg=TEXT, bg=CARD,
                 font=(FONT, 12, "bold")).pack(side="left", padx=7)
        action(tools, "Sığdır", self.fit_image).pack(side="right", padx=3)
        action(tools, "−", lambda: self.zoom_center(1 / 1.25), width=2).pack(side="right", padx=3)
        action(tools, "+", lambda: self.zoom_center(1.25), width=2).pack(side="right", padx=3)
        tk.Label(tools, textvariable=self.zoom_text, fg=CYAN, bg=CARD,
                 font=(FONT, 11, "bold"), width=6).pack(side="right")
        self.canvas = tk.Canvas(center, bg=CANVAS, highlightthickness=0, bd=0,
                                relief="flat", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self._zoom_at(1.17, e.x, e.y))
        self.canvas.bind("<Button-5>", lambda e: self._zoom_at(1 / 1.17, e.x, e.y))
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release_drag)
        tk.Label(center, text="Tekerlek: yakınlaştır  •  Sürükle: gezin  •  Kutuyu seç: Fluke rehberi",
                 fg=MUTED, bg=CARD, font=(FONT, 10)).pack(fill="x", pady=(7, 1))

        right = tk.Frame(body, bg=CARD, width=340)
        right.grid(row=0, column=2, sticky="nsew")
        right.grid_propagate(False)
        inspector_canvas = tk.Canvas(right, bg=CARD, highlightthickness=0, bd=0)
        inspector_canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=inspector_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        inspector_canvas.configure(yscrollcommand=scrollbar.set)
        inspector = tk.Frame(inspector_canvas, bg=CARD, padx=16, pady=13)
        window_id = inspector_canvas.create_window((0, 0), window=inspector, anchor="nw")
        inspector.bind("<Configure>", lambda _e: inspector_canvas.configure(
            scrollregion=inspector_canvas.bbox("all")
        ))
        inspector_canvas.bind("<Configure>", lambda e: inspector_canvas.itemconfigure(
            window_id, width=e.width
        ))
        self._build_inspector(inspector)

        footer = tk.Frame(self.root, bg=BG, padx=20, pady=8)
        footer.pack(fill="x")
        tk.Label(footer, textvariable=self.status, fg=MUTED, bg=BG,
                 anchor="w", font=(FONT, 10)).pack(fill="x")

    def _build_inspector(self, panel):
        tk.Label(panel, text="FLUKE ÖLÇÜM ASİSTANI", fg=CYAN, bg=CARD,
                 font=(FONT, 12, "bold")).pack(anchor="w", pady=(0, 10))
        tk.Label(panel, textvariable=self.component_title, fg=TEXT, bg=CARD,
                 anchor="w", font=(FONT, 17, "bold"), wraplength=305).pack(fill="x")
        note(panel, self.component_meta, MUTED)
        section(panel, "KOMPONENT TÜRÜ")
        self.class_menu = ttk.Combobox(
            panel, style="Nova.TCombobox", textvariable=self.class_choice,
            values=sorted(ALLOWED), state="readonly"
        )
        self.class_menu.pack(fill="x")
        self.class_menu.bind("<<ComboboxSelected>>", self.correct_component)
        section(panel, "FLUKE MODU")
        tk.Label(panel, textvariable=self.mode_text, fg=GREEN, bg=CARD,
                 anchor="w", font=(FONT, 17, "bold"), wraplength=300).pack(fill="x")
        section(panel, "HAZIRLIK VE GÜVENLİK")
        note(panel, self.setup_text)
        section(panel, "PROB NOKTALARI")
        note(panel, self.probes_text)
        section(panel, "BEKLENEN SONUÇ")
        note(panel, self.expected_text, AMBER)
        section(panel, "SONRAKİ KONTROL")
        note(panel, self.next_text)
        tk.Frame(panel, height=1, bg=LINE).pack(fill="x", pady=(15, 6))
        tk.Label(panel, text="DOĞRULANMIŞ REFERANS", fg=MUTED, bg=CARD,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        refrow = tk.Frame(panel, bg=CARD)
        refrow.pack(fill="x", pady=6)
        for variable, caption, width in (
            (self.nominal, "Nominal", 9), (self.tolerance, "± %", 6),
            (self.unit, "Birim", 7)
        ):
            stack = tk.Frame(refrow, bg=CARD)
            stack.pack(side="left", padx=(0, 5))
            tk.Label(stack, text=caption, bg=CARD, fg=MUTED,
                     font=(FONT, 9)).pack(anchor="w")
            tk.Entry(stack, textvariable=variable, width=width, bg=CARD2, fg=TEXT,
                     insertbackground=TEXT, relief="flat", highlightthickness=1,
                     highlightbackground=LINE, font=(FONT, 11)).pack(ipady=6)
        tk.Checkbutton(panel, text="Nominal değeri veri sayfasıyla doğruladım",
                       variable=self.verified_nominal, command=self.refresh_guide,
                       bg=CARD, fg=TEXT, selectcolor=CARD2, activebackground=CARD,
                       activeforeground=TEXT, font=(FONT, 10),
                       highlightthickness=0).pack(anchor="w", pady=(0, 4))
        action(panel, "Referans aralığını göster", self.refresh_guide).pack(fill="x")
        section(panel, "FLUKE OKUMASI (MANUEL)")
        measure = tk.Frame(panel, bg=CARD)
        measure.pack(fill="x")
        tk.Entry(measure, textvariable=self.reading, bg=CARD2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=(FONT, 13),
                 highlightthickness=1, highlightbackground=LINE).pack(
                     side="left", fill="x", expand=True, ipady=8, padx=(0, 5)
                 )
        action(measure, "Kaydet", self.save_measurement, color=BLUE).pack(side="right")
        note(panel, self.measure_result, MUTED)
        action(panel, "Ölçüm geçmişi / analiz", self.show_history).pack(fill="x", pady=(10, 0))
        tk.Label(panel, text="Tek fotoğraf veya tek Fluke değeri sağlamlığı kanıtlamaz.",
                 fg=MUTED, bg=CARD, wraplength=295, justify="left",
                 font=(FONT, 9)).pack(anchor="w", pady=(10, 0))

    def _resize(self, event):
        old_w, old_h = self.viewport.canvas_width, self.viewport.canvas_height
        self.viewport.canvas_width = max(event.width, 1)
        self.viewport.canvas_height = max(event.height, 1)
        if self.image and old_w > 0 and old_h > 0:
            self.viewport.pan((event.width - old_w)/2, (event.height - old_h)/2)
        self._schedule_render()

    def choose_photo(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="PCB fotoğrafını seç",
            filetypes=[("PCB Fotoğrafları", "*.jpg *.jpeg *.png *.webp"),
                       ("Tüm dosyalar", "*.*")]
        )
        if path:
            self.open_photo(path)

    def open_photo(self, path):
        try:
            with Image.open(path) as opened:
                photo = ImageOps.exif_transpose(opened).convert("RGB")
            if min(photo.size) <= 0:
                raise ValueError("Fotoğraf boyutu geçersiz.")
        except (OSError, ValueError) as exc:
            self.status.set("FOTOĞRAF HATASI  •  " + str(exc))
            return False
        self.image_path = str(Path(path).resolve())
        self.image = photo
        self.tasks = []
        self.selected = None
        self._scan_number += 1
        self.viewport.image_width, self.viewport.image_height = photo.size
        self.viewport.canvas_width = max(1, self.canvas.winfo_width())
        self.viewport.canvas_height = max(1, self.canvas.winfo_height())
        self.viewport.fit()
        self._refresh_parts()
        self._clear_selection()
        self._schedule_render()
        self.start_analysis()
        return True

    def rescan(self):
        if not self.image_path:
            self.status.set("Önce bir PCB fotoğrafı seçin.")
            return
        self.tasks = []
        self.selected = None
        self._refresh_parts()
        self._clear_selection()
        self.start_analysis()

    def start_analysis(self):
        """Use a worker to avoid blocking the Tk event loop while YOLO runs."""
        if not self.image_path:
            return
        self._scan_number += 1
        generation = self._scan_number
        path = self.image_path
        self._busy = True
        self.progress.start(12)
        self.image_status.set("Model kontrol ediliyor / analiz hazırlanıyor...")
        self.status.set("TARAMA  •  Birinci çalıştırmada model dosyası indirilebilir")
        def work():
            try:
                result = automatic_detect(
                    path, progress=lambda msg: self._events.put((generation, "progress", msg))
                )
                self._events.put((generation, "result", result))
            except Exception as exc:
                self._events.put((generation, "error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if self._closed:
            return
        self._poll_job = None
        try:
            while True:
                generation, kind, value = self._events.get_nowait()
                if generation != self._scan_number:
                    continue
                if kind == "progress":
                    self.image_status.set(value)
                elif kind == "error":
                    self._busy = False
                    self.progress.stop()
                    self.image_status.set("Analiz başlatılamadı. " + value)
                    self.status.set("MODEL HATASI  •  " + value[:180])
                elif kind == "result":
                    self._busy = False
                    self.progress.stop()
                    try:
                        self.tasks = measurement_plan(review_detections(value))
                    except (ValueError, TypeError, KeyError) as exc:
                        self.image_status.set("Modelin döndürdüğü kutular geçersiz: " + str(exc))
                        self.tasks = []
                    self._refresh_parts()
                    self._schedule_render()
                    if self.tasks:
                        self.select_index(0)
                    self.image_status.set(f"{len(self.tasks)} model adayı bulundu (henüz doğrulanmadı).")
                    self.status.set("TARAMA BİTTİ  •  Parçayı seçerek Fluke modunu görüntüleyin")
        except queue.Empty:
            pass
        if not self._closed and self.root.winfo_exists():
            self._poll_job = self.root.after(150, self._poll)

    def _refresh_parts(self):
        existing = self.parts.get_children()
        if existing:
            self.parts.delete(*existing)
        for idx, task in enumerate(self.tasks):
            confidence = task.get("confidence")
            score = f"{confidence:.0%}" if isinstance(confidence, (int,float)) else "—"
            self.parts.insert("", "end", iid=str(idx), values=(
                idx + 1, task["source_label"], score
            ))
        self.detection_count.set(f"{len(self.tasks)} komponent adayı")

    def _select_tree(self, _event=None):
        items = self.parts.selection()
        if items:
            self.select_index(int(items[0]))

    def select_index(self, index):
        if index is None or not 0 <= index < len(self.tasks):
            return
        if self.selected != index:
            self.nominal.set("")
            self.tolerance.set("")
            self.unit.set("")
            self.reading.set("")
            self.verified_nominal.set(False)
        self.selected = index
        if str(index) not in self.parts.selection():
            self.parts.selection_set(str(index))
            self.parts.see(str(index))
        task = self.tasks[index]
        self.component_title.set(f"{index + 1:02d}  /  {task['source_label']}")
        conf = task.get("confidence")
        confidence = f"{conf:.0%}" if isinstance(conf, (int,float)) else "belirtilmedi"
        self.component_meta.set(f"Model güveni: {confidence}  ·  Görsel tespit; doğrulanmadı")
        self.class_choice.set(task["component"])
        self.refresh_guide()
        self.measure_result.set(
            f"Kayıtlı ölçüm sayısı: {len(task.get('measurement_history', []))}"
        )
        self._schedule_render()

    def _clear_selection(self):
        self.component_title.set("Komponent seçilmedi")
        self.component_meta.set("Fotoğraf yüklendiğinde komponentler otomatik taranır.")
        self.class_choice.set("Bilinmiyor")
        for variable in (self.mode_text, self.setup_text, self.probes_text, self.next_text):
            variable.set("—")
        self.expected_text.set("Nominal ve tolerans doğrulanmadan sayısal aralık verilmez.")
        self.measure_result.set("Ölçüm yapılmadı.")

    def correct_component(self, _event=None):
        if self.selected is None:
            return
        task = self.tasks[self.selected]
        chosen = self.class_choice.get()
        if chosen not in ALLOWED:
            return
        task["component"] = chosen
        task["source_label"] = chosen
        task["mode"], description = instruction_for(chosen)
        task["instruction"] = description + " Kart enerjisiz ve deşarj edilmiş olmalı."
        task["technician_verified_type"] = True
        self.component_title.set(f"{self.selected + 1:02d}  /  {chosen}")
        self._refresh_parts()
        self.parts.selection_set(str(self.selected))
        self.refresh_guide()
        self._schedule_render()

    def refresh_guide(self):
        if self.selected is None:
            return
        task = self.tasks[self.selected]
        arguments = {}
        if self.verified_nominal.get():
            try:
                if not self.nominal.get().strip() or not self.tolerance.get().strip() or not self.unit.get().strip():
                    raise ValueError("Nominal, tolerans ve birim birlikte gerekli.")
                n = float(self.nominal.get().replace(",", "."))
                t = float(self.tolerance.get().replace(",", "."))
                if not math.isfinite(n) or not math.isfinite(t) or n < 0 or not 0 <= t <= 100:
                    raise ValueError("Değer veya tolerans geçersiz.")
                arguments = dict(nominal=n, tolerance_percent=t, unit=self.unit.get().strip())
            except ValueError as exc:
                self.expected_text.set("Doğrulanmış değer hatası: " + str(exc))
                return
        guided = guide_for(task["component"], **arguments)
        if "status" in guided:
            self.mode_text.set(task["mode"])
            self.setup_text.set("Ölçümden önce kartın enerjisiz ve deşarj edilmiş olduğundan emin olun.")
            self.probes_text.set("Pinleri veya terminalleri üretici datasheet'iyle doğrulayın.")
            self.expected_text.set("Tip / veri sayfası doğrulanmadan referans verilemez.")
            self.next_text.set("Parça kodunu, tipini ve ölçüm koşullarını doğrulayın.")
        else:
            self.mode_text.set(guided["mode"])
            self.setup_text.set(guided["setup"])
            self.probes_text.set(guided["probes"])
            self.expected_text.set(guided["expected"])
            self.next_text.set(guided["next_step"])

    def save_measurement(self):
        if self.selected is None:
            self.measure_result.set("Önce fotoğrafta bir komponent seçin.")
            return
        task = self.tasks[self.selected]
        value = self.reading.get().strip().replace(",", ".")
        try:
            number = float(value)
            result = evaluate(task, number)
            mode = self.mode_text.get()
            unit = self.unit.get().strip() if self.verified_nominal.get() else ""
            record_measurement(task, number, result["status"], result["detail"], mode=mode, unit=unit)
        except (ValueError, TypeError) as exc:
            self.measure_result.set("Hatalı Fluke okuması: " + str(exc))
            return
        self.reading.set("")
        self.measure_result.set(
            f"{len(task['measurement_history'])}. ölçüm kaydedildi  ·  {result['status']}\n{result['detail']}"
        )
        self.status.set("ÖLÇÜM KAYDEDİLDİ  •  Referans koşulları ayrıca doğrulanmalıdır")

    def show_history(self):
        if self.selected is None:
            self.status.set("Ölçüm geçmişi için önce komponent seçin.")
            return
        task = self.tasks[self.selected]
        dialog = tk.Toplevel(self.root, bg=CARD)
        dialog.title(f"Ölçüm geçmişi — komponent {self.selected + 1}")
        dialog.geometry("660x400")
        tk.Label(dialog, text=task["source_label"], bg=CARD, fg=CYAN,
                 font=(FONT, 18, "bold")).pack(anchor="w", padx=20, pady=20)
        text = tk.Text(dialog, bg=CANVAS, fg=TEXT, insertbackground=TEXT,
                       wrap="word", relief="flat", padx=15, pady=15, font=(FONT, 11))
        text.pack(fill="both", expand=True, padx=18, pady=(0, 20))
        text.insert("1.0", history_text(task) + "\n\n")
        for item in review_queue([task]):
            text.insert("end", "Sonraki kontrol: " + item["reason"])
        text.configure(state="disabled")

    def save_session(self):
        if not self.image_path:
            self.status.set("Kaydedilecek fotoğraf yok.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".json", initialfile="nova_dcg_analiz.json",
            filetypes=[("NOVA DCG oturum dosyası", "*.json")]
        )
        if not path:
            return
        try:
            output = {
                "format": "nova-dcg-v2",
                "image": self.image_path,
                "warning": "Model kutuları doğrulanmamış öneridir; ölçümler manuel girildi.",
                "tasks": self.tasks,
            }
            Path(path).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set("ÇALIŞMA KAYDEDİLDİ  •  " + path)
        except OSError as exc:
            self.status.set("KAYDETME HATASI  •  " + str(exc))

    def fit_image(self):
        if self.image:
            self.viewport.fit()
            self._schedule_render()

    def zoom_center(self, factor):
        self._zoom_at(factor, self.canvas.winfo_width()/2, self.canvas.winfo_height()/2)

    def _zoom_at(self, factor, x, y):
        if self.image is None:
            return
        self.viewport.zoom(factor, x, y)
        self._schedule_render()

    def _wheel(self, event):
        if event.delta:
            self._zoom_at(1.17 if event.delta > 0 else 1 / 1.17, event.x, event.y)

    def _start_drag(self, event):
        self._mouse_down = (event.x, event.y, event.x, event.y)
        self._dragged = False

    def _drag(self, event):
        if not self._mouse_down:
            return
        start_x, start_y, old_x, old_y = self._mouse_down
        if abs(event.x-start_x) + abs(event.y-start_y) >= 5:
            self._dragged = True
        if self._dragged:
            self.viewport.pan(event.x-old_x, event.y-old_y)
            self._schedule_render()
        self._mouse_down = (start_x, start_y, event.x, event.y)

    def _release_drag(self, event):
        if not self._dragged and self.image and self.tasks:
            result = self.viewport.find_box(
                [task["bbox_xyxy_pixels"] for task in self.tasks], event.x, event.y
            )
            if result is not None:
                self.select_index(result)
        self._mouse_down = None

    def _schedule_render(self):
        if not self._closed and not self._render_pending:
            self._render_pending = True
            self._render_job = self.root.after_idle(self._render)

    def _render(self):
        if self._closed:
            return
        self._render_job = None
        self._render_pending = False
        self.canvas.delete("all")
        if self.image is None:
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            self.canvas.create_text(w/2, h/2-18, text="PCB FOTOĞRAFINI YÜKLEYİN",
                                    fill=TEXT, font=(FONT, 18, "bold"))
            self.canvas.create_text(w/2, h/2+20,
                                    text="Fotoğraf seçildiğinde analiz kendiliğinden başlayacak.",
                                    fill=MUTED, font=(FONT, 11))
            return
        bounds = self.viewport.visible_crop()
        if bounds:
            left, top, right, bottom = bounds
            crop = self.image.crop(bounds)
            w = max(1, round((right-left)*self.viewport.scale))
            h = max(1, round((bottom-top)*self.viewport.scale))
            if w > 0 and h > 0:
                resized = crop.resize((w, h), Image.Resampling.BILINEAR)
                self.picture = ImageTk.PhotoImage(resized)
                x, y = self.viewport.to_canvas(left, top)
                self.canvas.create_image(x, y, anchor="nw", image=self.picture)
        for idx, task in enumerate(self.tasks):
            x1, y1, x2, y2 = task["bbox_xyxy_pixels"]
            ax, ay = self.viewport.to_canvas(x1, y1)
            bx, by = self.viewport.to_canvas(x2, y2)
            cw, ch = self.viewport.canvas_width, self.viewport.canvas_height
            if bx < 0 or by < 0 or ax > cw or ay > ch:
                continue
            active = idx == self.selected
            color = CYAN if active else AMBER
            self.canvas.create_rectangle(ax, ay, bx, by, outline=color,
                                         width=3 if active else 2)
            # Avoid tiny illegible captions until the user zooms in.
            if bx - ax >= 24 or active:
                caption = f"{idx+1}  {task['source_label']}"
                tx, ty = max(2, ax), max(2, ay-16)
                text_id = self.canvas.create_text(
                    tx+4, ty, anchor="nw", text=caption,
                    fill=BG if active else TEXT,
                    font=(FONT, 10, "bold")
                )
                x0, y0, x1b, y1b = self.canvas.bbox(text_id)
                tag = self.canvas.create_rectangle(
                    x0-2, y0-2, x1b+2, y1b+2,
                    fill=CYAN if active else CARD2, outline=""
                )
                self.canvas.tag_lower(tag, text_id)
        self.zoom_text.set(f"{self.viewport.scale*100:.0f}%")


    def close(self):
        """Prevent orphaned Tk callbacks when the application exits."""
        if self._closed:
            return
        self._closed = True
        self._scan_number += 1  # Discard late background results.
        self.progress.stop()
        for job in (self._poll_job, self._render_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self.root.destroy()


def main():
    root = tk.Tk()
    Workspace(root)
    root.mainloop()


if __name__ == "__main__":
    main()
