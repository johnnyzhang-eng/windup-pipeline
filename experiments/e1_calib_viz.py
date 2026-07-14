"""E1 校准可视化 · 灵敏度阶梯 (Refs Windup #7)
一行展示：干净帧 + 5 种已知扰动 + 2 个跨角色，每张标 DreamSim 相对倍数，
底部画好带/灰区/跨角色三段色带，直观看"多大的变化=多大的数"。
"""
import os, glob, statistics
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import torch, torch.hub
torch.hub._validate_not_a_forked_repo = lambda *a, **k: None
from PIL import Image, ImageDraw, ImageFont
from dreamsim import dreamsim

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
GRAY = (128, 128, 128); LIGHT = (245, 245, 245)
ROOT = os.path.expanduser("~/jz_code/windup-pipeline/characters")
LIRAEL = os.path.expanduser("~/jz_code/2d游戏广度方向/MS1/预研-生成实测/lirael_base.png")
TH, PAD = 200, 16

def load(p, bg=GRAY):
    im = Image.open(p)
    if im.mode == "RGBA":
        c = Image.new("RGB", im.size, bg); c.paste(im, mask=im.split()[3]); return c
    return im.convert("RGB")
def fnt(s):
    # PingFang.ttc 在本机 cannot open → STHeiti 是可靠的中文兜底
    for p in ["/System/Library/Fonts/STHeiti Medium.ttc","/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/System/Library/Fonts/PingFang.ttc","/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(p, s)
        except: pass
    return ImageFont.load_default()
F, FS, FT = fnt(20), fnt(16), fnt(23)
def hue(im,d):
    h,s,v=im.convert("HSV").split(); h=h.point(lambda p:(p+int(d/360*255))%256)
    return Image.merge("HSV",(h,s,v)).convert("RGB")
def occ(im):
    im=im.copy(); w,h=im.size; ImageDraw.Draw(im).rectangle([w*.45,h*.5,w*.85,h*.9],fill=GRAY); return im
def thumb(im):
    im=im.copy(); im.thumbnail((TH,TH)); c=Image.new("RGB",(TH,TH),LIGHT)
    c.paste(im,((TH-im.width)//2,(TH-im.height)//2)); return c

model, pre = dreamsim(pretrained=True, device=DEVICE)
emb=lambda im: pre(im).to(DEVICE)
def dist(a,b):
    with torch.no_grad(): return model(emb(a),emb(b)).item()

sbase=load(f"{ROOT}/skeleton/01_base/chosen_base.png")
frames=[load(p) for p in sorted(glob.glob(f"{ROOT}/skeleton/03_walk_cutout/walk_0*.png"))]
med=statistics.median([dist(sbase,f) for f in frames])
clean=frames[2]

# (标签, 图, 显示底色用浅色版)
items=[("干净帧", clean, clean),
       ("色相+40°", hue(clean,40), hue(clean.convert("RGBA") if clean.mode=="RGBA" else clean,40)),
       ("色相+90°", hue(clean,90), hue(clean,90)),
       ("去饱和", clean.convert("L").convert("RGB"), clean.convert("L").convert("RGB")),
       ("抹武器", occ(clean), occ(clean)),
       ("换成boy", load(f"{ROOT}/boy/01_base/chosen_base.png"), load(f"{ROOT}/boy/01_base/chosen_base.png")),
       ("换成lirael", load(LIRAEL), load(LIRAEL))]

cells=[]
for label,measure,show in items:
    r=dist(sbase,measure)/med
    cells.append((label, thumb(show), r))

n=len(cells)+1  # +母版
W=n*TH+(n+1)*PAD; H=40+TH+46+70
out=Image.new("RGB",(W,H),(255,255,255)); d=ImageDraw.Draw(out)
d.text((PAD,8),"DreamSim 灵敏度阶梯：同一张干净帧施加已知改动 → 相对倍数（÷序列中位数）。看它对什么敏感、对什么麻木",fill=(30,30,30),font=FT)
# 母版
d.text((PAD,40+TH+6),"skeleton母版",fill=(30,30,30),font=F); out.paste(thumb(sbase),(PAD,40))
for i,(label,img,r) in enumerate(cells):
    x=PAD+(i+1)*(TH+PAD); y=40
    out.paste(img,(x,y))
    col=(40,150,40) if r<=1.2 else (210,120,20) if r<1.5 else (200,40,40)
    d.text((x+4,y+TH+4),f"{label}",fill=(30,30,30),font=F)
    d.text((x+4,y+TH+24),f"{r:.2f}×",fill=col,font=F)
# 色带说明
by=40+TH+52
d.text((PAD,by),"绿 ≤1.20× 好带(同角色·含极端姿势)   |   橙 1.2–1.5× 灰区(细微漂移:配色/道具,DreamSim感觉弱)   |   红 ≥1.5× 明显漂移",fill=(30,30,30),font=FS)
d.text((PAD,by+22),"关键：翻转≈麻木(DreamSim近乎镜像不变,'换手'问题它抓不到→需几何/手性检查)；跨角色轻松爆表(2.9×+)；细微单属性漂移贴着好带上沿(需VLM语义层)",fill=(90,90,90),font=FS)
outp=os.path.join(os.path.dirname(__file__),"e1_calib_viz.png")
out.save(outp); print("SAVED",outp,out.size)
