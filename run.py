#!/usr/bin/env python3
"""Windup 管线主流程：一张角色参考图 → 走路动作包（GIF + sprite sheet + 元数据）。

用法：
    export SUFY_KEY=你的图像API_key
    python run.py --ref path/to/character.png --name lirael \
        --desc "pixel-art druid: red hair, antler crown, green hooded cloak, staff with blue orb" \
        --mode desc            # desc=动作描述驱动(长裙/复杂角色)；skeleton=骨架驱动(露腿角色)

产出：characters/<name>/ 下 01_base / 02_walk_raw / 03_walk_cutout / 04_output。

注：生成步骤需联网 + 有效 SUFY_KEY；抠图/对齐/打包为本地纯 CV，无需联网。
"""
import argparse, os
from pipeline import config, generate, skeleton_gen, matte, align, pack

# 走路循环 4 个关键相位的动作描述（desc 模式用）
WALK_POSES_DESC = [
    ("contact",  "mid-stride: one foot stepping forward, weight shifting forward, arms/props swinging naturally"),
    ("passing",  "legs together under the body, body at highest point"),
    ("contact2", "opposite foot stepping forward, mirror of the first stride"),
    ("passing2", "legs together again, returning toward the start of the loop"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="角色参考图路径")
    ap.add_argument("--name", required=True, help="角色名（输出文件夹名）")
    ap.add_argument("--desc", required=True, help="角色身份描述（英文，喂给模型锁一致性）")
    ap.add_argument("--mode", choices=["desc", "skeleton"], default="desc")
    ap.add_argument("--outroot", default="characters")
    args = ap.parse_args()

    root = os.path.join(args.outroot, args.name)
    d_base = os.path.join(root, "01_base")
    d_raw = os.path.join(root, "02_walk_raw")
    d_cut = os.path.join(root, "03_walk_cutout")
    d_out = os.path.join(root, "04_output")
    for d in (d_base, d_raw, d_cut, d_out):
        os.makedirs(d, exist_ok=True)

    # ① 视角规整 → 伪侧面基准帧
    print("① 视角规整 → 伪侧面基准帧 ...")
    base = os.path.join(d_base, "chosen_base.png")
    if not generate.to_side_view(args.ref, args.desc, base):
        raise SystemExit("视角规整失败（检查 SUFY_KEY / 网络）")

    # ③④ 逐帧生成走路
    skels = skeleton_gen.make_walk_skeletons(os.path.join(root, "_skeletons")) \
        if args.mode == "skeleton" else [None] * len(WALK_POSES_DESC)
    raw_paths = []
    for (tag, pose), sk in zip(WALK_POSES_DESC, skels):
        out = os.path.join(d_raw, f"walk_{tag}.png")
        print(f"④ 生成 walk/{tag} ...")
        if generate.gen_frame(base, args.desc, pose, out, skeleton_path=sk):
            raw_paths.append(out)

    # ⑤ 抠图
    cut_paths = []
    for p in raw_paths:
        out = os.path.join(d_cut, os.path.basename(p))
        print(f"⑤ 抠图 {os.path.basename(p)} ...")
        matte.cutout(p, out); cut_paths.append(out)

    # ⑥ 对齐
    print("⑥ 逐帧对齐 ...")
    frames = align.align_frames(cut_paths)

    # ⑦ 打包
    print("⑦ 打包 sprite sheet / JSON / plist / GIF ...")
    n = len(frames)
    pack.sprite_sheet(frames, os.path.join(d_out, "sprite_sheet.png"))
    pack.write_json(n, config.CELL, os.path.join(d_out, "sprite_sheet.json"))
    pack.write_plist(n, config.CELL, os.path.join(d_out, "sprite_sheet.plist"))
    pack.gif(frames, os.path.join(d_out, "walk.gif"))
    print(f"完成 ✅  产出在 {d_out}/  （{n} 帧）")


if __name__ == "__main__":
    main()
