"""Interactive image markers; Pillow required."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw

def mark_photo(parent, path):
    source=Image.open(path).convert("RGB")
    scale=min(1.0, 850/source.width, 560/source.height)
    shown=source.resize((round(source.width*scale),round(source.height*scale)))
    win=tk.Toplevel(parent)
    win.title("Kart fotoğrafı - ölçüm noktalarını işaretle")
    win.transient(parent)
    canvas=tk.Canvas(win,width=shown.width,height=shown.height,cursor="crosshair")
    canvas.pack(padx=10,pady=10)
    tkimg=ImageTk.PhotoImage(shown)
    canvas.create_image(0,0,image=tkimg,anchor="nw")
    canvas.image=tkimg
    points=[]
    def click(event):
        x,y=event.x,event.y
        if not (0<=x<shown.width and 0<=y<shown.height):
            return
        n=len(points)+1
        points.append((x/scale,y/scale,n))
        canvas.create_oval(x-8,y-8,x+8,y+8,outline="red",width=2)
        canvas.create_text(x,y,text=str(n),fill="yellow",font=("Helvetica",10,"bold"))
    canvas.bind("<Button-1>",click)
    def save():
        if not points:
            messagebox.showinfo("Bilgi","Önce fotoğraf üzerinde nokta seçin.",parent=win)
            return
        filename=filedialog.asksaveasfilename(parent=win,defaultextension=".png",filetypes=[("PNG","*.png")])
        if not filename:
            return
        out=source.copy()
        draw=ImageDraw.Draw(out)
        radius=max(8,int(8/scale))
        for x,y,n in points:
            x,y=round(x),round(y)
            draw.ellipse((x-radius,y-radius,x+radius,y+radius),outline="red",width=4)
            draw.text((x-4,y-6),str(n),fill="yellow",stroke_width=1,stroke_fill="black")
        out.save(filename)
        parent.annotated_photo=filename
        messagebox.showinfo("Kaydedildi","İşaretli fotoğraf kaydedildi ve rapor için seçildi.",parent=win)
        win.destroy()
    bar=ttk.Frame(win)
    bar.pack(pady=8)
    ttk.Label(bar,text="Ölçüm noktalarına tıklayın; numaralar sırayla eklenir.").pack(side="left",padx=8)
    ttk.Button(bar,text="İşaretli fotoğrafı kaydet",command=save).pack(side="left")
