"""Convert clicks on a scaled photo into original-image pixel coordinates."""
def image_to_widget_point(x,y,original_size,display_size,offset=(0,0)):
    ow,oh=original_size
    dw,dh=display_size
    ox,oy=offset
    if min(ow,oh,dw,dh)<=0:
        raise ValueError("Image dimensions must be positive")
    if not (ox<=x<ox+dw and oy<=y<oy+dh):
        raise ValueError("Click outside displayed photo")
    return (min(ow-1,max(0,round((x-ox)*ow/dw))),
            min(oh-1,max(0,round((y-oy)*oh/dh))))
