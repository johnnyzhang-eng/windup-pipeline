"""E1 slice-1 · DreamSim 身份漂移探针  (Refs Windup #7 · research/06)

对每个角色跑两组 DreamSim 距离：
  1) 母版(基准帧) vs 每一帧  —— 跨帧身份漂移（离得越远越可能"换了个角色"）
  2) 相邻帧两两            —— 帧间跳变（步态本身会有变化，做参照基线）

抠图帧是 RGBA 透明底，按 research/06 先合成到统一灰底再喂 DreamSim，去掉
"透明 vs 不透明"带来的背景偏置。DreamSim = CLIP+DINO 集成，比 LPIPS/裸CLIP 更贴人眼。

用法：
  ./.venv-pose/bin/python e1_dreamsim_probe.py <char_dir> [<char_dir> ...]
  例：e1_dreamsim_probe.py ~/jz_code/windup-pipeline/characters/skeleton
"""
import os, sys, glob, json, statistics

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内镜像下 backbone 权重

import torch
import torch.hub
# Clash fake-ip 劫持 api.github.com → torch.hub 的 _validate_not_a_forked_repo（调 GitHub API
# 校验 backbone 仓）会挂；但 github release/codeload 文件下载正常（1.17G ckpt 已下成功）。
# 跳过这一次 API 校验即可，不影响 backbone 权重下载。
torch.hub._validate_not_a_forked_repo = lambda *a, **k: None
from PIL import Image
from dreamsim import dreamsim

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
BG = (128, 128, 128)  # 统一中性灰底


def load_on_bg(path):
    """任意图 → RGB；RGBA 用 alpha 合成到统一灰底（去背景偏置）。"""
    im = Image.open(path)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, BG)
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB")


def probe_char(char_dir, model, preprocess):
    char_dir = os.path.expanduser(char_dir)
    name = os.path.basename(char_dir.rstrip("/"))
    base = os.path.join(char_dir, "01_base", "chosen_base.png")
    frames = sorted(glob.glob(os.path.join(char_dir, "03_walk_cutout", "walk_0*.png")))
    if not os.path.exists(base) or not frames:
        print(f"[skip] {name}: 缺 base 或 frames (base={os.path.exists(base)}, frames={len(frames)})")
        return None

    def emb(path):
        return preprocess(load_on_bg(path)).to(DEVICE)

    base_t = emb(base)
    vs_master, adjacent = [], []

    print(f"\n===== {name}  (device={DEVICE}, {len(frames)} 帧) =====")
    print("-- 母版 vs 每帧 --")
    with torch.no_grad():
        for f in frames:
            d = model(base_t, emb(f)).item()
            vs_master.append(d)
            print(f"  {os.path.basename(f):>12}: {d:.4f}")
        print("-- 相邻帧 --")
        fembs = [emb(f) for f in frames]
        for i in range(len(fembs) - 1):
            d = model(fembs[i], fembs[i + 1]).item()
            adjacent.append(d)
            print(f"  {i}->{i+1}: {d:.4f}")

    summ = {
        "char": name, "n_frames": len(frames),
        "vs_master": {"min": min(vs_master), "max": max(vs_master),
                      "mean": statistics.mean(vs_master)},
        "adjacent": {"min": min(adjacent), "max": max(adjacent),
                     "mean": statistics.mean(adjacent)},
        "worst_frame_idx": max(range(len(vs_master)), key=lambda i: vs_master[i]),
    }
    print(f"  母版vs帧:  min={summ['vs_master']['min']:.4f}  "
          f"max={summ['vs_master']['max']:.4f}  mean={summ['vs_master']['mean']:.4f}")
    print(f"  相邻帧:    min={summ['adjacent']['min']:.4f}  "
          f"max={summ['adjacent']['max']:.4f}  mean={summ['adjacent']['mean']:.4f}")
    print(f"  最漂移帧:  #{summ['worst_frame_idx']} (母版距离 {vs_master[summ['worst_frame_idx']]:.4f})")
    return summ


def main(dirs):
    print(f"加载 DreamSim (ensemble)… device={DEVICE}")
    model, preprocess = dreamsim(pretrained=True, device=DEVICE)
    results = [r for d in dirs if (r := probe_char(d, model, preprocess))]
    print("\n===== JSON 汇总 =====")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:] or [
        "~/jz_code/windup-pipeline/characters/skeleton",
        "~/jz_code/windup-pipeline/characters/boy",
    ]
    main(args)
