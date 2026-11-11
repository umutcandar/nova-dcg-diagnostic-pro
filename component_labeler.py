"""Manual PCB component region labeling. No automatic image recognition."""
import json
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

COMPONENTS = ["Direnç", "Kondansatör", "Diyot", "Entegre", "Transistör", "Bobin", "Konnektör", "Bilinmiyor"]

def normalized_box(x1,y1,x2,y2,width,height):
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image size")
    a,b=sorted((max(0,min(width,x1)),max(0,min(width,x2))))
    c,d=sorted((max(0,min(height,y1)),max(0,min(height,y2))))
    if b-a < 2 or d-c < 2:
        raise ValueError("Select a larger region")
    return [round(a/width,6),round(c/height,6),round(b/width,6),round(d/height,6)]

def launch_labeler(parent, image_path):
    source=Image.open(image_path).convert("RGB")
    scale=min(1.0,900/source.width,620/source.height)
    view=source.resize((max(1,round(source.width*scale)),max(1,round(source.height*scale))))
    win=tk.Toplevel(parent)
    win.title("NOVA DCG - Komponent bölgesi etiketleme")
    tkimg=ImageTk.PhotoImage(view)
    canvas=tk.Canvas(win,width=view.width,height=view.height,cursor="crosshair")
    canvas.pack(padx=10,pady=10)
    canvas.create_image(0,0,image=tkimg,anchor="nw")
    canvas.image=tkimg
    toolbar=ttk.Frame(win)
    toolbar.pack(fill="x",padx=10,pady=8)
    kind=tk.StringVar(value=COMPONENTS[0])
    ttk.Combobox(toolbar,textvariable=kind,values=COMPONENTS,state="readonly",width=18).pack(side="left")
    ttk.Label(toolbar,text="Bir parçayı dikdörtgen içine almak için sürükleyin.").pack(side="left",padx=12)
    regions=[]
    state={"start":None,"rect":None}
    def down(e):
        state["start"]=(e.x,e.y)
        state["rect"]=canvas.create_rectangle(e.x,e.y,e.x,e.y,outline="#ffcc00",width=2)
    def move(e):
        if state["start"] and state["rect"]:
            x,y=state["start"]
            canvas.coords(state["rect"],x,y,e.x,e.y)
    def up(e):
        if not state["start"]:
            return
        x,y=state["start"]
        state["start"]=None
        try:
            box=normalized_box(x/scale,y/scale,e.x/scale,e.y/scale,source.width,source.height)
        except ValueError:
            canvas.delete(state["rect"])
            return
        regions.append({"label":kind.get(),"bbox_xyxy_normalized":box,"source":"manual","verified":False})
        canvas.create_text(x,y,text=kind.get(),anchor="sw",fill="yellow")
    canvas.bind("<ButtonPress-1>",down)
    canvas.bind("<B1-Motion>",move)
    canvas.bind("<ButtonRelease-1>",up)
    def save():
        if not regions:
            messagebox.showinfo("Boş","Önce en az bir parça işaretleyin.",parent=win)
            return
        path=filedialog.asksaveasfilename(parent=win,defaultextension=".json",filetypes=[("JSON","*.json")])
        if not path:
            return
        data={"schema_version":1,"image":str(Path(image_path).resolve()),
              "image_width":source.width,"image_height":source.height,
              "coordinate_system":"xyxy_normalized","regions":regions,
              "note":"Labels are manual and not automatically verified."}
        Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        messagebox.showinfo("Kaydedildi",f"{len(regions)} bölge kaydedildi.",parent=win)
    ttk.Button(toolbar,text="Etiketleri JSON kaydet",command=save).pack(side="right")
