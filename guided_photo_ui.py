"""Photo-guided measurement window. Requires Pillow; YOLO weights optional."""
import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from guided_measurement import measurement_plan, evaluate
from detection_review import review_detections, ALLOWED
from component_ocr import read_markings
from datasheet_catalog import manufacturer_search_url
from measurement_reference import compare
from probe_points import validate_probe_points
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
            if "probe_points" in task:
                for name,color in (("red","#ff2424"),("black","#171717")):
                    px,py=task["probe_points"][name]
                    r=max(6,img.width//170)
                    draw.ellipse((px-r,py-r,px+r,py+r),fill=color,outline="#ffffff",width=2)
                    draw.text((px+r+2,py-r),name.upper(),fill=color)
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

    def read_component_code():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce komponent tespitlerini yükleyin.",parent=win)
            return
        task=tasks[index[0]]
        try:
            found=read_markings(image_path,task["bbox_xyxy_pixels"])
        except (OSError,ValueError,RuntimeError,ImportError) as exc:
            messagebox.showerror("OCR kullanılamıyor",str(exc),parent=win)
            return
        dialog=tk.Toplevel(win)
        dialog.title("Parça kodu doğrulama")
        dialog.geometry("540x300")
        ttk.Label(dialog,text="OCR tahmini; parça kodunu etiketten doğrulayın.").pack(pady=8)
        code=tk.StringVar(value=found["candidates"][0] if found["candidates"] else "")
        ttk.Entry(dialog,textvariable=code,width=42).pack(pady=8)
        ttk.Label(dialog,text="Okunan metin: "+found["raw_text"][:140],wraplength=480).pack(pady=8)
        def confirm():
            try:
                url=manufacturer_search_url(code.get())
            except ValueError as exc:
                messagebox.showerror("Geçersiz kod",str(exc),parent=dialog)
                return
            task["part_number"]=code.get().strip().upper()
            task["part_number_verified_by_user"]=True
            feedback.set("Parça kodu doğrulandı. Datasheet araması: "+url)
            dialog.destroy()
        ttk.Button(dialog,text="Kodu doğrula",command=confirm).pack(pady=8)

    def mark_probes():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce komponent seçin.",parent=win)
            return
        task=tasks[index[0]]
        dialog=tk.Toplevel(win)
        dialog.title("Prob noktalarını elle doğrula")
        dialog.geometry("480x300")
        ttk.Label(dialog,text="Fotoğraftaki piksel koordinatlarını girin; pin işlevini datasheet ile kontrol edin.",wraplength=440).pack(pady=8)
        fields={}
        for name in ("Kırmızı X","Kırmızı Y","Siyah X","Siyah Y"):
            line=ttk.Frame(dialog)
            line.pack(pady=3)
            ttk.Label(line,text=name,width=14).pack(side="left")
            field=ttk.Entry(line,width=12)
            field.pack(side="left")
            fields[name]=field
        confirmed=tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog,text="Pinleri ve ölçüm noktalarını kendim doğruladım",variable=confirmed).pack(pady=8)
        def apply():
            try:
                red=(float(fields["Kırmızı X"].get()),float(fields["Kırmızı Y"].get()))
                black=(float(fields["Siyah X"].get()),float(fields["Siyah Y"].get()))
                points=validate_probe_points(source.size,task["bbox_xyxy_pixels"],red,black,confirmed.get())
                task["probe_points"]=points
                feedback.set(points["warning"])
                render()
                dialog.destroy()
            except ValueError as exc:
                messagebox.showerror("Prob işaretleme hatası",str(exc),parent=dialog)
        ttk.Button(dialog,text="Noktaları kaydet",command=apply).pack(pady=8)

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
    def compare_reference():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce komponent seçin.",parent=win)
            return
        task=tasks[index[0]]
        if not task.get("part_number_verified_by_user"):
            messagebox.showinfo("Parça kodu","Önce Yazıyı oku ile parça kodunu doğrulayın.",parent=win)
            return
        path=filedialog.askopenfilename(parent=win,title="Doğrulanmış referans JSON seç",filetypes=[("JSON","*.json")])
        if not path:
            return
        try:
            spec=json.loads(Path(path).read_text(encoding="utf-8"))
            state=tk.Toplevel(win)
            state.title("Ölçüm koşulu")
            ttk.Label(state,text="Ölçüm kart üzerinde mi yapıldı?").pack(pady=10)
            selected=tk.StringVar(value="in_circuit")
            ttk.Radiobutton(state,text="Devre içinde",variable=selected,value="in_circuit").pack()
            ttk.Radiobutton(state,text="Devre dışında",variable=selected,value="out_of_circuit").pack()
            def apply():
                try:
                    result=compare(spec,task,value.get(),selected.get())
                    feedback.set(result["status"]+": "+result["detail"])
                    task["reference_result"]=result
                    task["reference_source"]=spec["source_url"]
                    state.destroy()
                except (ValueError,TypeError,KeyError) as exc:
                    messagebox.showerror("Karşılaştırma hatası",str(exc),parent=state)
            ttk.Button(state,text="Koşulları karşılaştır",command=apply).pack(pady=10)
        except (OSError,ValueError) as exc:
            messagebox.showerror("Referans okunamadı",str(exc),parent=win)

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
                          ("Türü doğrula / düzelt",correct_current),("Yazıyı oku",read_component_code),("Prob noktalarını işaretle",mark_probes),("Ölçümü değerlendir",submit),("Referansla karşılaştır",compare_reference),("Sonraki komponent",next_task),
                          ("Sonuçları kaydet",save_results)]:
        ttk.Button(controls,text=title,command=command).pack(side="left",padx=3)
    render()
