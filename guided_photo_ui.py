"""Photo-guided measurement window. Requires Pillow; YOLO weights optional."""
import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from guided_measurement import measurement_plan, evaluate
from detection_review import review_detections, ALLOWED
from model_inference import detect_components

def open_guided_window(parent, image_path=None):
    image_path=image_path or filedialog.askopenfilename(parent=parent,filetypes=[("Images","*.png *.jpg *.jpeg *.webp")])
    if not image_path:
        return
    try:
        source=Image.open(image_path).convert("RGB")
    except (OSError,ValueError) as exc:
        messagebox.showerror("Fotoğraf açılamadı",str(exc),parent=parent)
        return
    win=tk.Toplevel(parent)
    win.title("Fotoğrafta adım adım ölçüm")
    win.geometry("1000x820")
    win.minsize(650,550)
    tasks=[]
    detections=[]
    index=[0]
    photo=tk.Label(win)
    photo.pack(fill="both",expand=True,padx=10,pady=8)
    status=tk.StringVar(value="Önce tespit JSON dosyası yükleyin veya eğitilmiş model seçin.")
    ttk.Label(win,textvariable=status,wraplength=920).pack(padx=10,pady=5)
    ttk.Label(win,text="Prob konumları otomatik doğrulanmaz. Kart enerjisiz ve deşarj edilmiş olmalı.").pack(padx=10)
    value=tk.StringVar()
    row=ttk.Frame(win)
    row.pack(pady=6)
    ttk.Label(row,text="Fluke ölçümü:").pack(side="left")
    ttk.Entry(row,textvariable=value,width=15).pack(side="left",padx=6)
    feedback=tk.StringVar()
    ttk.Label(win,textvariable=feedback,wraplength=920).pack(padx=10,pady=6)
    def render():
        img=source.copy()
        draw=ImageDraw.Draw(img)
        if tasks:
            task=tasks[index[0]]
            x1,y1,x2,y2=task["bbox_xyxy_pixels"]
            draw.rectangle((x1,y1,x2,y2),outline="#ff2424",width=max(3,img.width//250))
            draw.text((x1,max(0,y1-18)),str(task["id"])+" "+task["source_label"],fill="#ff2424")
            status.set(f"{index[0]+1}/{len(tasks)} | {task['source_label']} | Mod: {task['mode']} | {task['instruction']}")
        img.thumbnail((920,540))
        picture=ImageTk.PhotoImage(img)
        photo.configure(image=picture)
        photo.image=picture
    def set_detections(items):
        nonlocal tasks, detections
        try:
            detections=review_detections(items)
            tasks=measurement_plan(detections)
            for task in tasks:
                x1,y1,x2,y2=task["bbox_xyxy_pixels"]
                if x1<0 or y1<0 or x2>source.width or y2>source.height:
                    raise ValueError("Komponent kutusu fotoğraf sınırları dışında")
            index[0]=0
            feedback.set("")
            render()
        except (ValueError,TypeError,KeyError) as exc:
            messagebox.showerror("Tespit verisi geçersiz",str(exc),parent=win)
    def import_json():
        path=filedialog.askopenfilename(parent=win,filetypes=[("JSON","*.json")])
        if not path:
            return
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data,list):
                raise ValueError("Tespit dosyası bir liste olmalı")
            set_detections(data)
        except (OSError,ValueError) as exc:
            messagebox.showerror("JSON okunamadı",str(exc),parent=win)
    def scan():
        path=filedialog.askopenfilename(parent=win,filetypes=[("YOLO model","*.pt")])
        if not path:
            return
        try:
            set_detections(detect_components(image_path,path))
        except (OSError,ValueError,RuntimeError,ImportError) as exc:
            messagebox.showerror("Model taraması başarısız",str(exc),parent=win)
    def correct_current():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce tespitleri yükleyin.",parent=win)
            return
        dialog=tk.Toplevel(win)
        dialog.title("Komponent türünü doğrula")
        dialog.geometry("390x170")
        ttk.Label(dialog,text="Model tahminini doğrulayın veya düzeltin:").pack(pady=8)
        selected=tk.StringVar(value=tasks[index[0]]["component"])
        ttk.Combobox(dialog,textvariable=selected,values=sorted(ALLOWED),state="readonly").pack(pady=5)
        def apply():
            try:
                new=review_detections(detections,{index[0]:selected.get()})
                detections[:]=new
                previous=tasks[index[0]]
                tasks[:]=measurement_plan(detections)
                tasks[index[0]]["status"]=previous.get("status","ölçüm bekleniyor")
                if "reading" in previous:
                    tasks[index[0]]["reading"]=previous["reading"]
                feedback.set("Komponent türü teknisyen tarafından doğrulandı.")
                render()
                dialog.destroy()
            except ValueError as exc:
                messagebox.showerror("Düzeltme hatası",str(exc),parent=dialog)
        ttk.Button(dialog,text="Onayla",command=apply).pack(pady=8)

    def submit():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce komponent tespitlerini yükleyin.",parent=win)
            return
        try:
            result=evaluate(tasks[index[0]],value.get())
            tasks[index[0]]["reading"]=float(value.get())
            tasks[index[0]]["status"]=result["status"]
            feedback.set(result["status"]+": "+result["detail"])
        except ValueError as exc:
            messagebox.showerror("Ölçüm hatası",str(exc),parent=win)
    def next_task():
        if not tasks:
            return
        index[0]=(index[0]+1)%len(tasks)
        value.set("")
        feedback.set("")
        render()
    def save_results():
        if not tasks:
            return
        path=filedialog.asksaveasfilename(parent=win,defaultextension=".json",filetypes=[("JSON","*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps({"image":str(image_path),"tasks":tasks},ensure_ascii=False,indent=2),encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Kaydetme hatası",str(exc),parent=win)
    controls=ttk.Frame(win)
    controls.pack(pady=10)
    for title,command in [("Tespit JSON aç",import_json),("Model ile tara",scan),
                          ("Türü doğrula / düzelt",correct_current),("Ölçümü değerlendir",submit),("Sonraki komponent",next_task),
                          ("Sonuçları kaydet",save_results)]:
        ttk.Button(controls,text=title,command=command).pack(side="left",padx=3)
    render()
