"""NOVA DCG private local web prototype. Binds only to loopback, never deploy as-is."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import json

from PIL import Image, ImageOps

HOST, PORT = "127.0.0.1", 8765
MAX_BODY = 16 * 1024 * 1024
PAGE = r'''<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOVA DCG • PCB Studio</title>
<style>
:root{color-scheme:dark;font-family:system-ui,Arial;background:#0b1220;color:#e8eefb}
*{box-sizing:border-box}body{margin:0}header{padding:18px 26px;background:#121e30;border-bottom:1px solid #30405a;display:flex;justify-content:space-between}
main{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:18px;padding:20px;max-width:1600px;margin:auto}
section,aside{background:#152238;border:1px solid #30405a;border-radius:16px;padding:18px}
#drop{border:2px dashed #5a779e;border-radius:12px;min-height:65vh;display:grid;place-items:center;overflow:hidden;position:relative;cursor:pointer;background:#0d1727}
#drop.drag{border-color:#61d6c1;background:#20364b}
#viewport{width:100%;height:65vh;overflow:hidden;display:none;position:relative;cursor:grab}
#image{position:absolute;transform-origin:0 0;max-width:none;user-select:none;pointer-events:none}
#overlay{position:absolute;inset:0;pointer-events:none}
button{background:#294563;border:1px solid #517497;color:white;border-radius:9px;padding:10px 13px;cursor:pointer;margin:3px}
button:hover{background:#386185}h2{margin-top:0}small,.muted{color:#9db1ce}#status{margin-top:12px;min-height:22px}
.result{padding:10px;border-bottom:1px solid #33465e;cursor:pointer}.result:hover{background:#253953}
@media(max-width:850px){main{grid-template-columns:1fr}#drop,#viewport{min-height:45vh;height:45vh}}
</style><header><strong>NOVA DCG / PCB STUDIO</strong><span>Özel yerel önizleme</span></header>
<main><section><h2>Kart fotoğrafı</h2><div>
<button id="change">Fotoğraf değiştir</button><button id="plus">＋</button><button id="minus">－</button><button id="fit">Sığdır</button></div>
<input id="file" type="file" accept="image/png,image/jpeg,image/webp" hidden>
<div id="drop"><div id="hint">PCB fotoğrafını buraya sürükle veya tıkla<br><small>PNG · JPG · WebP (en fazla 12 MB)</small></div>
<div id="viewport"><img id="image" alt="PCB fotoğrafı"><canvas id="overlay"></canvas></div></div>
<div id="status" role="status">Fotoğraf bekleniyor.</div></section>
<aside><h2>Komponent adayları</h2><p class="muted">Model tahminleri elektriksel arıza kanıtı değildir.</p>
<div id="results">Henüz analiz yok.</div><h2>Fluke rehberi</h2><div id="fluke">Bir komponent seç.</div>
<p class="muted">Enerjiyi kesin, kondansatörlerin boşaldığını doğrula. Devre içi ölçüm yanıltıcı olabilir.</p></aside></main>
<script>
const $=id=>document.getElementById(id), drop=$('drop'),vp=$('viewport'),im=$('image'),cv=$('overlay');
let data=[],zoom=1,ox=0,oy=0,dragging=false,lastX=0,lastY=0;
function render(){im.style.transform=`translate(${ox}px,${oy}px) scale(${zoom})`;cv.width=vp.clientWidth;cv.height=vp.clientHeight;
let c=cv.getContext('2d');c.clearRect(0,0,cv.width,cv.height);c.lineWidth=2;c.font='12px system-ui';
data.forEach((d,i)=>{let b=d.bbox||d.box||d.xyxy;if(!Array.isArray(b)||b.length<4)return;
let x=ox+b[0]*zoom,y=oy+b[1]*zoom,w=(b[2]-b[0])*zoom,h=(b[3]-b[1])*zoom;
c.strokeStyle='#f9b54b';c.strokeRect(x,y,w,h);c.fillStyle='#f9b54b';c.fillText(String(i+1),x+3,y+13)})}
function fit(){zoom=Math.min(vp.clientWidth/im.naturalWidth,vp.clientHeight/im.naturalHeight);ox=(vp.clientWidth-im.naturalWidth*zoom)/2;oy=(vp.clientHeight-im.naturalHeight*zoom)/2;render()}
function scale(f){zoom=Math.max(.05,Math.min(12,zoom*f));render()}
$('plus').onclick=()=>scale(1.25);$('minus').onclick=()=>scale(.8);$('fit').onclick=fit;
$('change').onclick=()=>$('file').click();drop.onclick=e=>{if(e.target===drop||e.target===$('hint'))$('file').click()};
$('file').onchange=e=>{if(e.target.files[0])load(e.target.files[0])};
drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag')};
drop.ondragleave=()=>drop.classList.remove('drag');
drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');if(e.dataTransfer.files[0])load(e.dataTransfer.files[0])};
vp.onwheel=e=>{e.preventDefault();scale(e.deltaY<0?1.15:.87)};
vp.onpointerdown=e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;vp.setPointerCapture(e.pointerId)};
vp.onpointermove=e=>{if(!dragging)return;ox+=e.clientX-lastX;oy+=e.clientY-lastY;lastX=e.clientX;lastY=e.clientY;render()};
vp.onpointerup=()=>dragging=false;window.onresize=()=>{if(im.naturalWidth)render()};
const modes={resistor:'Ω (direnç)',capacitor:'Kapasitans (enerjisiz, deşarj edilmiş)',diode:'Diyot testi',led:'Diyot testi',inductor:'Ω (direnç)',connector:'Süreklilik',mosfet:'Diyot testi; pin dizilimini doğrula',transistor:'Diyot testi; pin dizilimini doğrula'};
function show(){let out=$('results');out.replaceChildren();if(!data.length){out.textContent='Komponent adayı bulunamadı.';return}
data.forEach((d,i)=>{let name=String(d.label||d.class_name||d.name||d.type||'Bilinmeyen');
let item=document.createElement('div');item.className='result';item.textContent=(i+1)+'. '+name+' — '+(typeof d.confidence==='number'?(d.confidence*100).toFixed(0)+'% güven':'güven belirtilmedi');
item.onclick=()=>{$('fluke').textContent=(modes[name.toLowerCase()]||'Şema ve datasheet doğrulaması gerekli')+'. Ölçüm değeri yalnızca doğrulanmış referansla yorumlanır.'};out.append(item)})}
async function load(file){if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>12*1024*1024){$('status').textContent='Desteklenmeyen format veya 12 MB sınırı aşıldı.';return}
const reader=new FileReader();reader.onload=async()=>{im.onload=fit;im.src=reader.result;vp.style.display='block';$('hint').style.display='none';data=[];show();$('status').textContent='Analiz çalışıyor…';
try{let response=await fetch('/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:reader.result})});let payload=await response.json();if(!response.ok)throw Error(payload.error||'Analiz başarısız');data=payload.detections;show();render();$('status').textContent=data.length+' komponent adayı bulundu. Tahminler doğrulanmalıdır.'}
catch(e){$('status').textContent='Analiz hatası: '+e.message}};reader.readAsDataURL(file)}
</script></html>'''


class Handler(BaseHTTPRequestHandler):
    def send(self, code, obj, mime="application/json"):
        payload = obj.encode("utf-8") if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/":
            return self.send(200, PAGE, "text/html")
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/analyze":
            return self.send(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                return self.send(413, {"error": "İstek boyutu sınırı aşıldı."})
            body = json.loads(self.rfile.read(size))
            encoded = body["image"].split(",", 1)[1]
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 12 * 1024 * 1024:
                return self.send(413, {"error": "Fotoğraf çok büyük."})
            with TemporaryDirectory(prefix="nova_web_") as tmp:
                path = Path(tmp) / "board.png"
                from io import BytesIO
                with Image.open(BytesIO(raw)) as source:
                    source = ImageOps.exif_transpose(source)
                    if source.width * source.height > 50_000_000:
                        return self.send(413, {"error": "Görüntü çözünürlüğü çok yüksek."})
                    source.convert("RGB").save(path)
                from auto_detector import automatic_detect
                detections = automatic_detect(path)
                clean = []
                for item in detections:
                    if isinstance(item, dict):
                        clean.append(item)
                    elif hasattr(item, "__dict__"):
                        clean.append(vars(item))
                self.send(200, {"detections": clean})
        except Exception as exc:
            self.send(500, {"error": str(exc)[:300]})


if __name__ == "__main__":
    print(f"NOVA DCG local web studio: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
