"""自动质检（QA）—— 产品差异化能力（§3.4）。

三类检查：
  A. 对齐漂移（纯 CV，免费）：跨帧脚底线 / 躯干中心的方差，超阈值标记漂移帧。
  B. 一致性（VLM，需 API）：把每帧和基准帧喂视觉模型，判"是否同一角色"。
  C. 身份漂移（DreamSim，本机秒级零 API，重依赖可选）：每帧 vs 母版的感知距离，
     按"序列内相对离群"判漂移 + 相邻帧距离判抖动。阈值见下方 C 段（Refs #7 校准）。
不合格帧 → 建议单帧重生成（regenerate）。
"""
import json, base64
from PIL import Image
from . import config, align


# ---------- A. 对齐漂移（纯 CV） ----------
def alignment_report(cutout_paths, foot_tol=6, cx_tol=12):
    """检查各帧脚底 y、躯干中心 x 的漂移。返回 {ok, frames:[{idx,foot,cx,drift}]}。"""
    rows = []
    foots, cxs = [], []
    for p in cutout_paths:
        im = Image.open(p).convert("RGBA")
        a = align.anchor(im)
        if a:
            foots.append(a[0]); cxs.append(a[1])
    if not foots:
        return {"ok": False, "reason": "no content"}
    foot_med = sorted(foots)[len(foots) // 2]
    cx_med = sorted(cxs)[len(cxs) // 2]
    bad = []
    for i, (f, c) in enumerate(zip(foots, cxs)):
        drift = abs(f - foot_med) > foot_tol or abs(c - cx_med) > cx_tol
        rows.append({"idx": i, "foot": round(f, 1), "cx": round(c, 1), "drift": drift})
        if drift:
            bad.append(i)
    return {"ok": not bad, "drift_frames": bad, "frames": rows,
            "foot_median": round(foot_med, 1), "cx_median": round(cx_med, 1)}


# ---------- B. 一致性（VLM） ----------
def vlm_consistency(base_path, frame_path, model=None):
    """问视觉模型：这两张是不是同一个角色？返回 {same:bool, notes:str}。"""
    config.require_key()
    model = model or config.VLM_MODEL
    def b64(p): return base64.b64encode(open(p, "rb").read()).decode()
    prompt = ("These are two frames of a game character. Image 1 is the reference (base). "
              "Image 2 is a generated animation frame. Answer STRICTLY as JSON: "
              '{"same_character": true/false, "issues": ["short notes on any drift in face/color/outfit/props/proportion"]}. '
              "Judge identity consistency, ignore pose differences.")
    body = {"model": model, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64(base_path)}},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64(frame_path)}},
    ]}]}
    try:
        res = config.post_json("/chat/completions", body, timeout=120)   # 带重试
        txt = res["choices"][0]["message"]["content"]
        import re
        m = re.search(r'\{.*\}', txt, re.S)
        if m:
            j = json.loads(m.group(0))
            return {"same": bool(j.get("same_character")), "notes": j.get("issues", [])}
    except Exception as e:
        return {"same": None, "notes": [f"VLM error: {str(e)[:80]}"]}
    return {"same": None, "notes": ["unparseable VLM reply"]}


# ---------- C. 身份漂移（DreamSim；本机秒级、零 API；torch 为可选重依赖） ----------
# 阈值来自校准实验 experiments/e1_calibrate.py（2026-07-14，Refs #7）：
#   · 好帧 vs母版相对倍数 ≤1.20×（含最极端姿势帧，仍是同角色）
#   · 跨角色 2.9×+（轻松爆表）；抹道具/变色/去饱和 1.2–1.4×（灰区，贴好带上沿）
#   · 水平翻转 ≈1.0×（DreamSim 近乎镜像不变 → "换手"问题它抓不到，需几何/手性检查）
# 定位：DreamSim 是"粗粒度身份守门员"——换角色轻松抓；细微单属性漂移(配色/道具)需 VLM 语义层兜底。
# 故阈值是"疑似漂移"弱信号，不当硬判死；用相对中位数(不用绝对值，绝对值被姿势差污染)。
DRIFT_RATIO = 1.5     # 帧 vs母版距离 / 序列中位数，超此=疑似漂移（好带上限 1.20，留余量）
FLICKER_MAX = 0.10    # 相邻帧距离，超此=帧间抖动（好带上限 0.062，留余量）

_DS = {}  # DreamSim 懒加载缓存：模型只加载一次


def _dreamsim_model():
    """懒加载 DreamSim（首次下载 ckpt，之后缓存）。不可用则抛异常，由调用方降级。"""
    if "model" not in _DS:
        import os
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内镜像下 backbone
        import torch, torch.hub
        # 本机 Clash fake-ip 劫持 api.github.com → torch.hub 校验 backbone 仓会挂，跳过该校验
        torch.hub._validate_not_a_forked_repo = lambda *a, **k: None
        from dreamsim import dreamsim
        dev = "mps" if torch.backends.mps.is_available() else "cpu"
        model, preprocess = dreamsim(pretrained=True, device=dev)
        _DS.update(model=model, preprocess=preprocess, device=dev, torch=torch)
    return _DS


def _gray_tensor(ds, path):
    """RGBA 抠图帧合成到统一灰底(128) 去背景偏置 → 预处理张量（与校准实验一致）。"""
    im = Image.open(path)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (128, 128, 128))
        bg.paste(im, mask=im.split()[3]); im = bg
    else:
        im = im.convert("RGB")
    return ds["preprocess"](im).to(ds["device"])


def dreamsim_drift(base_path, cutout_paths, drift_ratio=DRIFT_RATIO, flicker_max=FLICKER_MAX):
    """身份层信号：每帧 vs母版感知距离(相对序列中位数判离群) + 相邻帧抖动。
    返回 {available, median, frames:[{idx,vs_master,ratio,drift}], adjacent,
          drift_frames, jitter_frames, worst_idx, thresholds}。
    DreamSim 未安装/加载失败 → {available: False, reason}，不阻断其余质检。"""
    try:
        ds = _dreamsim_model()
    except Exception as e:
        return {"available": False, "reason": f"dreamsim 不可用: {str(e)[:100]}"}
    if not cutout_paths:
        return {"available": True, "median": 0.0, "frames": [], "adjacent": [],
                "drift_frames": [], "jitter_frames": [], "worst_idx": None,
                "thresholds": {"drift_ratio": drift_ratio, "flicker_max": flicker_max}}
    torch = ds["torch"]
    with torch.no_grad():
        bt = _gray_tensor(ds, base_path)
        fts = [_gray_tensor(ds, p) for p in cutout_paths]
        vs = [ds["model"](bt, ft).item() for ft in fts]
        adj = [None] + [ds["model"](fts[i - 1], fts[i]).item() for i in range(1, len(fts))]
    med = sorted(vs)[len(vs) // 2]
    frames = []
    for i, v in enumerate(vs):
        ratio = v / med if med else 0.0
        frames.append({"idx": i, "vs_master": round(v, 4),
                       "ratio": round(ratio, 2), "drift": ratio >= drift_ratio})
    return {"available": True, "median": round(med, 4), "frames": frames,
            "adjacent": [None if a is None else round(a, 4) for a in adj],
            "drift_frames": [f["idx"] for f in frames if f["drift"]],
            "jitter_frames": [i for i, a in enumerate(adj) if a is not None and a >= flicker_max],
            "worst_idx": max(range(len(vs)), key=lambda i: vs[i]),
            "thresholds": {"drift_ratio": drift_ratio, "flicker_max": flicker_max}}


def run_qa(base_path, cutout_paths, use_vlm=False, use_dreamsim=False):
    """综合质检：几何对齐(A) + 可选身份漂移(C·DreamSim) + 可选一致性(B·VLM)。返回报告 dict。"""
    rep = {"alignment": alignment_report(cutout_paths)}
    if use_dreamsim:
        rep["identity"] = dreamsim_drift(base_path, cutout_paths)
    if use_vlm:
        rep["consistency"] = [
            {"idx": i, **vlm_consistency(base_path, p)}
            for i, p in enumerate(cutout_paths)]
        rep["consistency_fail"] = [c["idx"] for c in rep["consistency"] if c["same"] is False]
    return rep
