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
from photo_coordinates import image_to_widget_point
from pin_mapping import suggest_probe_pair
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

    def click_to_mark_probes():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce komponent seçin.",parent=win)
            return
        task=tasks[index[0]]
        dialog=tk.Toplevel(win)
        dialog.title("Fotoğrafa tıklayarak prob noktası seç")
        dialog.geometry("980x680")
        ttk.Label(dialog,text="Önce KIRMIZI, sonra SİYAH probun temas noktasına tıklayın. Pinleri datasheet ile doğrulayın.").pack(pady=6)
        preview=source.copy()
        preview.thumbnail((930,520))
        display_size=preview.size
        preview_tk=ImageTk.PhotoImage(preview)
        canvas=tk.Canvas(dialog,width=display_size[0],height=display_size[1],highlightthickness=0)
        canvas.pack(pady=6)
        canvas.create_image(0,0,image=preview_tk,anchor="nw")
        canvas.image=preview_tk
        points=[]
        def clicked(event):
            try:
                point=image_to_widget_point(event.x,event.y,source.size,display_size)
                x1,y1,x2,y2=task["bbox_xyxy_pixels"]
                if not (x1<=point[0]<=x2 and y1<=point[1]<=y2):
                    raise ValueError("Seçilen nokta komponent kutusunun dışında")
                if len(points)>=2:
                    points.clear()
                    canvas.delete("probe")
                points.append(point)
                color="red" if len(points)==1 else "black"
                canvas.create_oval(event.x-6,event.y-6,event.x+6,event.y+6,fill=color,outline="white",tags="probe")
            except ValueError as exc:
                messagebox.showwarning("Geçersiz nokta",str(exc),parent=dialog)
        canvas.bind("<Button-1>",clicked)
        confirmed=tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog,text="Pin işlevlerini ve prob yerlerini kendim doğruladım",variable=confirmed).pack()
        def apply():
            if len(points)!=2:
                messagebox.showwarning("Eksik seçim","İki prob noktasını seçin.",parent=dialog)
                return
            try:
                result=validate_probe_points(source.size,task["bbox_xyxy_pixels"],points[0],points[1],confirmed.get())
                task["probe_points"]=result
                feedback.set(result["warning"])
                render()
                dialog.destroy()
            except ValueError as exc:
                messagebox.showerror("Doğrulama hatası",str(exc),parent=dialog)
        ttk.Button(dialog,text="Prob noktalarını kaydet",command=apply).pack(pady=8)

    def map_datasheet_pins():
        if not tasks:
            messagebox.showinfo("Tespit gerekli","Önce komponent seçin.",parent=win)
            return
        task=tasks[index[0]]
        path=filedialog.askopenfilename(parent=win,title="Doğrulanmış pinout JSON seç",filetypes=[("JSON","*.json")])
        if not path:
            return
        try:
            pinout=json.loads(Path(path).read_text(encoding="utf-8"))
            if not pinout.get("technician_verified"):
                raise ValueError("Pinout teknisyen tarafından doğrulanmamış")
            pins=pinout.get("pins",{})
            if not pins:
                raise ValueError("Pinout boş")
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showerror("Pinout hatası",str(exc),parent=win)
            return
        dialog=tk.Toplevel(win)
        dialog.title("Pinleri fotoğrafla eşleştir")
        dialog.geometry("600x720")
        ttk.Label(dialog,text="Datasheet pin numaralarını fotoğraftaki koordinatlarla eşleştirin.",wraplength=540).pack(pady=8)
        preview=source.copy()
        preview.thumbnail((530,300))
        display_size=preview.size
        preview_tk=ImageTk.PhotoImage(preview)
        canvas=tk.Canvas(dialog,width=display_size[0],height=display_size[1],highlightthickness=0)
        canvas.pack(pady=4)
        canvas.create_image(0,0,image=preview_tk,anchor="nw")
        canvas.image=preview_tk
        photo_pins={}
        numbers=[str(number) for number in pins]
        active=tk.StringVar(value=numbers[0])
        ttk.Label(dialog,text="Pin numarasını seçin, fotoğraftaki karşılığına tıklayın.").pack()
        ttk.Combobox(dialog,textvariable=active,values=numbers,state="readonly").pack()
        def pin_clicked(event):
            try:
                point=image_to_widget_point(event.x,event.y,source.size,display_size)
                x1,y1,x2,y2=task["bbox_xyxy_pixels"]
                if not (x1<=point[0]<=x2 and y1<=point[1]<=y2):
                    raise ValueError("Pin noktası komponent kutusu dışında")
                number=active.get()
                photo_pins[number]=list(point)
                canvas.delete("pin_"+number)
                canvas.create_oval(event.x-5,event.y-5,event.x+5,event.y+5,
                                   fill="yellow",outline="black",tags="pin_"+number)
                canvas.create_text(event.x+10,event.y-8,text=number,anchor="w",
                                   fill="yellow",tags="pin_"+number)
                remaining=[n for n in numbers if n not in photo_pins]
                if remaining:
                    active.set(remaining[0])
            except ValueError as exc:
                messagebox.showwarning("Pin konumu",str(exc),parent=dialog)
        canvas.bind("<Button-1>",pin_clicked)
        roles=sorted(set(pins.values()))
        red=tk.StringVar(value=roles[0])
        black=tk.StringVar(value=roles[-1])
        for name,var in (("Kırmızı prob pin işlevi",red),("Siyah prob pin işlevi",black)):
            ttk.Label(dialog,text=name).pack()
            ttk.Combobox(dialog,textvariable=var,values=roles,state="readonly").pack()
        confirm=tk.BooleanVar(value=False)
        ttk.Checkbutton(dialog,text="Pin yönünü, işlevlerini ve fotoğraf konumlarını doğruladım",variable=confirm).pack(pady=8)
        def apply():
            try:
                if not confirm.get():
                    raise ValueError("Teknisyen onayı gerekli")
                proposal=suggest_probe_pair(pinout,photo_pins,red.get(),black.get())
                result=validate_probe_points(source.size,task["bbox_xyxy_pixels"],
                    proposal["red"]["point"],proposal["black"]["point"],True)
                task["probe_points"]=result
                task["pin_mapping"]=proposal
                feedback.set("Datasheet pin eşleştirmesi doğrulandı; elektriksel sağlamlık henüz belirlenmedi.")
                render()
                dialog.destroy()
            except (ValueError,TypeError,KeyError) as exc:
                messagebox.showerror("Pin eşleştirme hatası",str(exc),parent=dialog)
        ttk.Button(dialog,text="Pin eşleştirmesini kaydet",command=apply).pack(pady=8)

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
    controls.pack(pady=10,fill="x")
    for idx,(title,command) in enumerate([("Tespit JSON aç",import_json),("Model ile tara",scan),
                          ("Türü doğrula / düzelt",correct_current),("Yazıyı oku",read_component_code),("Prob noktalarını işaretle",mark_probes),("Fotoğrafa tıklayarak prob seç",click_to_mark_probes),("Datasheet pinlerini eşleştir",map_datasheet_pins),("Ölçümü değerlendir",submit),("Referansla karşılaştır",compare_reference),("Sonraki komponent",next_task),
                          ("Sonuçları kaydet",save_results)]):
        ttk.Button(controls,text=title,command=command).grid(row=idx//3,column=idx%3,padx=3,pady=3,sticky="ew")
    render()
