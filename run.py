#!/usr/bin/env python3
"""Windup 管线主流程 —— 一套代码，任意角色。

换角色 = 换参数（不改代码）。每个角色 = 一张参考图 + 一个自动生成的角色卡。

    export SUFY_KEY=你的图像API_key

    # 全自动（连描述都不用手写，视觉模型自动看图生成角色卡）：
    python run.py --ref character.png --name lirael --actions idle,walk,attack

    # 想手写描述也行：
    python run.py --ref character.png --name lirael --desc "pixel druid, green cloak, staff" --actions walk

    # 单帧重生成（核心卖点：坏哪帧只重那帧）：
    python run.py --regen lirael walk 3

产出：characters/<name>/  card.json · provenance.jsonl · 各动作 raw/cutout · 04_output(sheet/json/plist/tres/gif)
可复现性：角色卡固定身份 + provenance 记录每次生成的 prompt/成本/时间（图像生成有随机性，
流程与参数可复现，非像素级一致 —— 行业常态）。
"""
import argparse, os, time
from pipeline import (config, character, actions, describe, generate,
                      matte, align, pack, provenance, qa, regenerate, autofix)


def build_actions(spec):
    """'idle,walk,attack' -> [Action]"""
    return [actions.get(n.strip()) for n in spec.split(",") if n.strip()]


def gen_action(card, act, outroot, use_vlm_qa=False):
    root = card.dir(outroot)
    d_raw = os.path.join(root, f"02_{act.name}_raw")
    d_cut = os.path.join(root, f"03_{act.name}_cutout")
    d_out = os.path.join(root, "04_output")
    for d in (d_raw, d_cut, d_out):
        os.makedirs(d, exist_ok=True)

    for i, pose in enumerate(act.poses):
        raw = os.path.join(d_raw, f"{act.name}_{i:02d}.png")
        print(f"  ④ 生成 {act.name}/{i} ...")
        t = time.time()
        if not generate.gen_frame(card.base_frame, card.desc, pose, raw):
            print(f"    ✗ 帧 {i} 首次失败，autofix 阶段会再补"); continue
        provenance.record(card.name, act.name, i, pose, config.IMAGE_MODEL,
                          elapsed_s=time.time()-t, outroot=outroot)
        matte.cutout(raw, os.path.join(d_cut, f"{act.name}_{i:02d}.png"))

    # ⑥⑦ + 自动修残次帧（质检→对被标记帧单帧重生成，最多 2 轮）+ 打包 + 尺寸档
    report = autofix.autofix_action(card, act, outroot, max_rounds=2, use_vlm=use_vlm_qa)
    frames = align.align_frames(
        sorted(os.path.join(d_cut, f) for f in os.listdir(d_cut) if f.endswith(".png")))
    pack.size_tiers(frames, os.path.join(d_out, "tiers"), act.name)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help="角色参考图")
    ap.add_argument("--name", help="角色名（输出文件夹）")
    ap.add_argument("--desc", default="", help="角色描述（留空则自动看图生成）")
    ap.add_argument("--actions", default="walk", help="逗号分隔，如 idle,walk,attack")
    ap.add_argument("--qa-vlm", action="store_true", help="开启视觉模型一致性质检（花 API）")
    ap.add_argument("--outroot", default="characters")
    ap.add_argument("--regen", nargs=3, metavar=("NAME", "ACTION", "IDX"),
                    help="单帧重生成：--regen lirael walk 3")
    args = ap.parse_args()

    if args.regen:
        name, action, idx = args.regen
        regenerate.regenerate_frame(name, action, int(idx), args.outroot)
        return

    if not (args.ref and args.name):
        ap.error("生成需要 --ref 和 --name")

    # ① 视角规整前：建角色卡（描述自动或手写）
    if args.desc:
        info = {"desc": args.desc, "palette": "", "view": "unknown"}
    else:
        print("① 自动看图生成角色描述 ...")
        info = describe.describe_character(args.ref)
        print(f"   描述：{info['desc']}")
    card = character.CharacterCard(name=args.name, desc=info["desc"],
                                   palette=info.get("palette", ""),
                                   ref_image=args.ref, view=info.get("view", ""))

    print("① 视角规整 → 伪侧面基准帧 ...")
    base = os.path.join(card.dir(args.outroot), "01_base"); os.makedirs(base, exist_ok=True)
    card.base_frame = os.path.join(base, "chosen_base.png")
    if not generate.to_side_view(args.ref, card.desc, card.base_frame):
        raise SystemExit("视角规整失败（检查 SUFY_KEY / 网络）")
    card.save(args.outroot)

    reports = {}
    for act in build_actions(args.actions):
        print(f"▶ 动作 {act.name}（{act.n_frames} 帧）")
        reports[act.name] = gen_action(card, act, args.outroot, use_vlm_qa=args.qa_vlm)

    # 汇总
    cost = provenance.summary(card.name, args.outroot)
    print(f"\n完成 ✅  {card.dir(args.outroot)}/")
    print(f"   动作：{', '.join(reports)}")
    print(f"   生成 {cost['runs']} 次 · 估算成本 ¥{cost['cost_yuan_est']} · 耗时 {cost['total_elapsed_s']}s")
    for a, r in reports.items():
        al = r["alignment"]
        print(f"   [{a}] 对齐漂移帧：{al.get('drift_frames', [])}"
              + (f" · 一致性不合格帧：{r.get('consistency_fail', [])}" if 'consistency' in r else ""))
    print("   漂移/不合格帧可用：python run.py --regen <name> <action> <idx> 单帧重生成")


if __name__ == "__main__":
    main()
