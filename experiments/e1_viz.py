"""E1 可视化 · 把 DreamSim 距离叠到真实帧上 (Refs Windup #7)

每个角色一行：母版 + 8 帧。帧下方标"vs母版"距离，帧左上标相邻 Δ（与前一帧），
序列内最离群帧（vs母版最大）红框 + 红字。输出单张 PNG，直接双击看，无需 localhost。

距离计算用与探针一致的灰底(128)预处理以对齐数字；显示缩略图用浅底更清楚。
用法：./.venv-pose/bin/python e1_viz.py            # 默认 skeleton + boy
"""
import os, sys, glob, statistics
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import torch, torch.hub
torch.hub._validate_not_a_forked_repo = lambda *a, **k: None  # 跳过被 Clash 挂的 api.github.com 校验
from PIL import Image, ImageDraw, ImageFont
from dreamsim import dreamsim

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
GRAY = (128, 128, 128)      # 喂 DreamSim 的统一底（与探针一致）
LIGHT = (245, 245, 245)     # 显示底
THUMB, PAD, CAPH, TITLEH = 190, 20, 52, 40
RED, ORANGE, DARK, GREYT = (200, 40, 40), (210, 120, 20), (40, 40, 40), (120, 120, 120)


def load(path, bg):
    im = Image.open(path)
    if im.mode == "RGBA":
        c = Image.new("RGB", im.size, bg); c.paste(im, mask=im.split()[3]); return c
    return im.convert("RGB")


def fnt(sz):
    for p in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

F_CAP, F_SM, F_TITLE = fnt(22), fnt(18), fnt(24)


def thumb(path):
    im = load(path, LIGHT); im.thumbnail((THUMB, THUMB))
    c = Image.new("RGB", (THUMB, THUMB), LIGHT)
    c.paste(im, ((THUMB - im.width) // 2, (THUMB - im.height) // 2))
    return c


def render_char(char_dir, model, preprocess):
    name = os.path.basename(char_dir.rstrip("/"))
    base = os.path.join(char_dir, "01_base", "chosen_base.png")
    frames = sorted(glob.glob(os.path.join(char_dir, "03_walk_cutout", "walk_0*.png")))
    emb = lambda p: preprocess(load(p, GRAY)).to(DEVICE)
    with torch.no_grad():
        bt = emb(base)
        vs = [model(bt, emb(f)).item() for f in frames]
        fe = [emb(f) for f in frames]
        adj = [None] + [model(fe[i-1], fe[i]).item() for i in range(1, len(frames))]
    worst = max(range(len(vs)), key=lambda i: vs[i])
    adj_worst = max(range(1, len(adj)), key=lambda i: adj[i])

    ncell = len(frames) + 1
    W = ncell * THUMB + (ncell + 1) * PAD
    H = TITLEH + THUMB + CAPH + PAD
    row = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(row)
    title = (f"{name}  ·  母版vs帧 {min(vs):.3f}–{max(vs):.3f} (均 {statistics.mean(vs):.3f})  ·  "
             f"相邻 {min(x for x in adj if x):.3f}–{max(x for x in adj if x):.3f} "
             f"(均 {statistics.mean([x for x in adj if x]):.3f})  ·  最可疑 #{worst}")
    d.text((PAD, 8), title, fill=DARK, font=F_TITLE)

    def cell(idx, img, top_label, cap, cap_color, boxed, adjv=None):
        x = PAD + idx * (THUMB + PAD); y = TITLEH
        row.paste(img, (x, y))
        if boxed:
            for w in range(4):
                d.rectangle([x - w, y - w, x + THUMB + w, y + THUMB + w], outline=RED)
        if top_label:
            d.text((x + 4, y + 2), top_label, fill=(adjv and adj[adjv] == max(a for a in adj if a)) and ORANGE or GREYT, font=F_SM)
        d.text((x + 4, y + THUMB + 4), cap, fill=cap_color, font=F_CAP)

    cell(0, thumb(base), "", "母版", DARK, False)
    for i, f in enumerate(frames):
        top = f"Δ{adj[i]:.3f}" if adj[i] is not None else ""
        cap = f"#{i}  {vs[i]:.3f}"
        cell(i + 1, thumb(f), top, cap, RED if i == worst else DARK, i == worst, adjv=i)
    return row, {"name": name, "vs": vs, "adj": adj, "worst": worst}


def main(dirs):
    print(f"load DreamSim… device={DEVICE}")
    model, preprocess = dreamsim(pretrained=True, device=DEVICE)
    rows = [render_char(os.path.expanduser(d), model, preprocess) for d in dirs]
    imgs = [r[0] for r in rows]
    legend_h = 60
    W = max(im.width for im in imgs)
    H = sum(im.height for im in imgs) + legend_h
    out = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for im in imgs:
        out.paste(im, (0, y)); y += im.height
    d = ImageDraw.Draw(out)
    d.text((20, y + 12), "距离 0=同一角色 · 越大越可能漂移　|　#i 下方=该帧vs母版　|　Δ=与前一帧(帧间抖动)　|　"
                         "红框=序列内最离群帧　|　注：母版是站立、帧是行走，vs母版含姿势差，看'谁离群'而非绝对值",
           fill=DARK, font=F_SM)
    outpath = os.path.join(os.path.dirname(__file__), "e1_dreamsim_viz.png")
    out.save(outpath)
    print("SAVED", outpath, out.size)


if __name__ == "__main__":
    dirs = sys.argv[1:] or ["~/jz_code/windup-pipeline/characters/skeleton",
                            "~/jz_code/windup-pipeline/characters/boy"]
    main(dirs)
