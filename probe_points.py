"""Technician-confirmed probe coordinates on a PCB photograph.

Coordinates are explicit photo pixels; never guessed from component bounding boxes.
"""
import math

def validate_probe_points(image_size, bbox, red, black, confirmed=False):
    width,height=image_size
    if not confirmed:
        raise ValueError("Teknisyen pinleri ve prob noktalarını doğrulamalı")
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in [width,height,*bbox,*red,*black]):
        raise ValueError("Koordinatlar sayısal ve sonlu olmalı")
    if width<=0 or height<=0 or len(bbox)!=4 or len(red)!=2 or len(black)!=2:
        raise ValueError("Geçersiz fotoğraf veya koordinat")
    x1,y1,x2,y2=bbox
    if not (0<=x1<x2<=width and 0<=y1<y2<=height):
        raise ValueError("Komponent kutusu fotoğraf dışında")
    for point in (red,black):
        x,y=point
        if not (x1<=x<=x2 and y1<=y<=y2):
            raise ValueError("Prob noktası seçili komponent kutusu dışında")
    if tuple(red)==tuple(black):
        raise ValueError("İki prob aynı noktada olamaz")
    return {"red":list(red),"black":list(black),"confirmed_by_technician":True,
            "warning":"Bu işaretler yalnızca teknisyenin seçtiği yerlerdir; elektriksel pin işlevi otomatik doğrulanmadı."}
