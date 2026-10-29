"""Deterministic restricted-markup lettering, shared by preview and confirmation."""
from html.parser import HTMLParser
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
from zet.services.scene_text_style_service import FONTS

class Runs(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.runs=[]
        self.feed(text); self.close()
        if self.stack: raise ValueError("Close all bold and italic tags.")
    def handle_starttag(self, tag, attrs):
        if attrs or tag not in {"b","i","strong","em","br"}: raise ValueError("Use only b, i, strong, em and br tags without attributes.")
        if tag == "br": self.handle_data("\n")
        else: self.stack.append(tag)
    def handle_startendtag(self, tag, attrs):
        if tag != "br": raise ValueError("Only br may be self-closing.")
        self.handle_starttag(tag, attrs)
    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag: raise ValueError("Formatting tags must be correctly nested.")
    def handle_data(self, text):
        self.runs.extend((c, bool(set(self.stack)&{"b","strong"}), bool(set(self.stack)&{"i","em"})) for c in text)
    def handle_comment(self, data): raise ValueError("Comments are not supported.")
    def handle_decl(self, decl): raise ValueError("HTML declarations are not supported.")
    def handle_pi(self, data): raise ValueError("Processing instructions are not supported.")

def render(size, entries, placements, style):
    image=Image.new("RGBA",size); errors=[]; w,h=size; scale=w/1216
    fonts=[ImageFont.truetype(str(Path("C:/Windows/Fonts")/name), max(1,round(style["font_size"]*scale))) for name in FONTS[style["font_family"]]]
    for entry in entries:
        try:
            runs=Runs(entry["text"]).runs
            if not ''.join(c for c,_,_ in runs).strip(): raise ValueError("Enter text.")
            place=placements.get(entry["id"], {}); box=place.get("box")
            if not box or len(box)!=4: raise ValueError("Place this text on the image.")
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in box): raise ValueError("Invalid box.")
            x,y,bw,bh=box
            if min(x,y)<0 or min(bw,bh)<=0 or x+bw>1.000001 or y+bh>1.000001: raise ValueError("Keep the box inside the image.")
            x,y,bw,bh=x*w,y*h,bw*w,bh*h
            padding=style["padding"]*scale+style["outline_width"]*scale
            inset=1/math.sqrt(2) if style["shape"]=="ellipse" else 0.94 if style["shape"]=="rounded" else 1
            aw,ah=bw*inset-2*padding,bh*inset-2*padding
            lines=[[]]; widths=[0]
            for char,bold,italic in runs:
                font=fonts[int(bold)+2*int(italic)]; cw=font.getlength(char) if char!='\n' else 0
                if char=='\n': lines.append([]); widths.append(0); continue
                if widths[-1]+cw>aw and lines[-1]:
                    split=next((i for i in range(len(lines[-1])-1,-1,-1) if lines[-1][i][0]==' '), None)
                    carry=[] if split is None else lines[-1][split+1:]
                    if split is not None: lines[-1]=lines[-1][:split]; widths[-1]=sum(f.getlength(c) for c,f in lines[-1])
                    lines.append(carry); widths.append(sum(f.getlength(c) for c,f in carry))
                lines[-1].append((char,font)); widths[-1]+=cw
            lineh=max(sum(f.getmetrics()) for f in fonts)*1.15
            if aw<=0 or ah<=0 or max(widths)>aw or len(lines)*lineh>ah: raise ValueError("Text overflows: enlarge the box or edit the text.")
            mask=Image.new("L",size); d=ImageDraw.Draw(mask); rect=(round(x),round(y),round(x+bw),round(y+bh))
            if style["shape"]=="ellipse": d.ellipse(rect,fill=255)
            elif style["shape"]=="rounded": d.rounded_rectangle(rect,radius=min(bw,bh)*0.15,fill=255)
            else: d.rectangle(rect,fill=255)
            if entry.get("tail")=="straight":
                tip=place.get("tip")
                if not tip or len(tip)!=2 or any(not isinstance(v,(float,int)) or not math.isfinite(v) or not 0<=v<=1 for v in tip): raise ValueError("Place the tail tip inside the image.")
                tx,ty=tip[0]*w,tip[1]*h
                if x<=tx<=x+bw and y<=ty<=y+bh: raise ValueError("Move the tail tip outside the bubble.")
                angle=place.get("attachment",math.atan2((ty-y-bh/2)/bh,(tx-x-bw/2)/bw))
                if not isinstance(angle,(int,float)) or not math.isfinite(angle): raise ValueError("Invalid attachment.")
                cx,cy=x+bw/2,y+bh/2; dx,dy=math.cos(angle),math.sin(angle)
                radius=1 if style["shape"]=="ellipse" else 1/max(abs(dx),abs(dy))
                ax,ay=cx+dx*bw/2*radius,cy+dy*bh/2*radius
                half=min(12*scale,bw/8,bh/8)
                d.polygon([(ax-dy*half,ay+dx*half),(tx,ty),(ax+dy*half,ay-dx*half),(cx,cy)],fill=255)
            stroke=round(style["outline_width"]*scale)
            if stroke:
                outer=mask.filter(ImageFilter.MaxFilter(stroke*2+1)); layer=Image.new("RGBA",size,style["outline_color"]);layer.putalpha(ImageChops.subtract(outer,mask));image.alpha_composite(layer)
            layer=Image.new("RGBA",size,style["background_color"]);layer.putalpha(mask.point(lambda v:round(v*style["opacity"])));image.alpha_composite(layer)
            draw=ImageDraw.Draw(image); yy=y+(bh-len(lines)*lineh)/2
            for line,width in zip(lines,widths):
                xx=x+(bw-width)/2
                for char,font in line:
                    draw.text((xx,yy+max(f.getmetrics()[0] for f in fonts)),char,font=font,fill=style["text_color"],anchor="ls");xx+=font.getlength(char)
                yy+=lineh
        except ValueError as exc: errors.append({"id":entry["id"],"message":str(exc)})
    return image,errors
