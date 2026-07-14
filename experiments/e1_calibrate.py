"""E1 阈值校准 · 用"已知好 vs 已知坏"分界定阈值 (Refs Windup #7)

好带(负例) = skeleton/boy 各 8 帧真实 walk vs 各自母版（肉眼确认同一角色）。
坏带(正例) = ① 跨角色（lirael/boy 母版 vs skeleton 母版）② 对一张干净帧注入已知扰动。
产出：两条阈值 —— 帧间抖动(相邻 Δ 绝对值) + 身份漂移(vs母版 / 序列中位数 的相对倍数)。

结论：绝对值会被姿势差污染（见 viz），漂移判据用"序列内相对离群"，抖动判据用相邻 Δ。
"""
import os, sys, glob, statistics, json
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import torch, torch.hub
torch.hub._validate_not_a_forked_repo = lambda *a, **k: None
from PIL import Image
from dreamsim import dreamsim

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
GRAY = (128, 128, 128)
ROOT = os.path.expanduser("~/jz_code/windup-pipeline/characters")
LIRAEL = os.path.expanduser("~/jz_code/2d游戏广度方向/MS1/预研-生成实测/lirael_base.png")


def load(path, bg=GRAY):
    im = Image.open(path)
    if im.mode == "RGBA":
        c = Image.new("RGB", im.size, bg); c.paste(im, mask=im.split()[3]); return c
    return im.convert("RGB")


# ---------- 已知扰动（造正例）----------
def hue_shift(im, deg):
    h, s, v = im.convert("HSV").split()
    h = h.point(lambda p: (p + int(deg / 360 * 255)) % 256)
    return Image.merge("HSV", (h, s, v)).convert("RGB")

def flip(im):            return im.transpose(Image.FLIP_LEFT_RIGHT)
def desat(im):           return im.convert("L").convert("RGB")
def occlude(im):         # 抹掉画面中心偏下一块（模拟武器/道具丢失）
    im = im.copy(); w, h = im.size
    from PIL import ImageDraw
    ImageDraw.Draw(im).rectangle([w*0.45, h*0.5, w*0.85, h*0.9], fill=GRAY); return im


def main():
    print(f"load DreamSim… device={DEVICE}")
    model, preprocess = dreamsim(pretrained=True, device=DEVICE)
    emb = lambda im: preprocess(im).to(DEVICE)
    def dist(a, b):
        with torch.no_grad(): return model(emb(a), emb(b)).item()

    report = {}
    bands = {}
    for c in ["skeleton", "boy"]:
        base = load(f"{ROOT}/{c}/01_base/chosen_base.png")
        frames = [load(p) for p in sorted(glob.glob(f"{ROOT}/{c}/03_walk_cutout/walk_0*.png"))]
        vs = [dist(base, f) for f in frames]
        med = statistics.median(vs)
        ratios = [v / med for v in vs]
        bands[c] = {"vs": vs, "median": med, "max_ratio": max(ratios),
                    "base": base, "frames": frames}
        print(f"\n[{c}] 好带 vs母版: {min(vs):.3f}–{max(vs):.3f} (中位 {med:.3f})  "
              f"相对倍数 max={max(ratios):.2f}")

    # ---- 跨角色（极端正例）----
    print("\n=== 跨角色（应远大于好带）===")
    skel_base = bands["skeleton"]["base"]; skel_med = bands["skeleton"]["median"]
    cross = {}
    for label, img in [("boy母版", bands["boy"]["base"]),
                       ("lirael母版", load(LIRAEL))]:
        d = dist(skel_base, img); cross[label] = d
        print(f"  {label} vs skeleton母版: {d:.3f}  (相对 skeleton中位 = {d/skel_med:.2f}×)")

    # ---- 注入扰动（可控正例，基于 skeleton/walk_02 干净帧）----
    print("\n=== 注入扰动 vs skeleton母版（对照干净帧 walk_02）===")
    clean = bands["skeleton"]["frames"][2]
    clean_d = dist(skel_base, clean)
    print(f"  [基准] 干净 walk_02 vs母版: {clean_d:.3f}  (相对 {clean_d/skel_med:.2f}×)")
    perturb = {"clean_walk02": clean_d}
    for label, fn in [("hue+40°", lambda: hue_shift(clean, 40)),
                      ("hue+90°", lambda: hue_shift(clean, 90)),
                      ("水平翻转", lambda: flip(clean)),
                      ("去饱和", lambda: desat(clean)),
                      ("抹武器块", lambda: occlude(clean))]:
        d = dist(skel_base, fn()); perturb[label] = d
        print(f"  {label:>10}: {d:.3f}  (相对 {d/skel_med:.2f}×)")

    # ---- 相邻帧抖动带 ----
    print("\n=== 相邻帧抖动带 ===")
    flick = {}
    for c in ["skeleton", "boy"]:
        fr = bands[c]["frames"]
        adj = [dist(fr[i-1], fr[i]) for i in range(1, len(fr))]
        flick[c] = {"min": min(adj), "max": max(adj), "mean": statistics.mean(adj)}
        print(f"  [{c}] 相邻 Δ: {min(adj):.3f}–{max(adj):.3f} (均 {statistics.mean(adj):.3f})")

    # ---- 推导阈值 ----
    good_max_ratio = max(bands["skeleton"]["max_ratio"], bands["boy"]["max_ratio"])
    flick_max = max(flick["skeleton"]["max"], flick["boy"]["max"])
    print("\n" + "=" * 56)
    print("推导阈值：")
    print(f"  好帧最高相对倍数 = {good_max_ratio:.2f}×（含最极端姿势帧，仍是同角色）")
    print(f"  → 漂移线 DRIFT_RATIO 建议 = {good_max_ratio + 0.25:.2f}×（留 0.25 余量）")
    print(f"  好帧相邻 Δ 最大 = {flick_max:.3f}")
    print(f"  → 抖动线 FLICKER_MAX 建议 = {round(flick_max + 0.04, 2):.2f}（留 ~0.04 余量）")
    print(f"  校验：跨角色相对倍数 = "
          f"{cross['boy母版']/skel_med:.2f}× / {cross['lirael母版']/skel_med:.2f}× "
          f"→ 应 >> 漂移线")
    worst_perturb = max((v/skel_med for k, v in perturb.items() if k != 'clean_walk02'))
    print(f"  校验：最重扰动相对倍数 = {worst_perturb:.2f}× → 应 > 漂移线")

    json.dump({"bands": {c: {"vs": bands[c]["vs"], "median": bands[c]["median"]} for c in bands},
               "cross": cross, "perturb": perturb, "flick": flick,
               "DRIFT_RATIO": round(good_max_ratio + 0.25, 2),
               "FLICKER_MAX": round(flick_max + 0.04, 2)},
              open(os.path.join(os.path.dirname(__file__), "e1_calib.json"), "w"),
              ensure_ascii=False, indent=2)
    print("\nSAVED e1_calib.json")


if __name__ == "__main__":
    main()
