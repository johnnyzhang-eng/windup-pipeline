"""动作清单（Action Registry）—— 多动作而非只 walk。

每个动作定义：帧数、帧率、循环模式、逐帧姿势描述。
标准动作内置模板；自定义动作用户传 poses 即可（产品：清单可定制，非固定菜单）。
"""
from dataclasses import dataclass, field


@dataclass
class Action:
    name: str
    fps: int
    loop: str                     # none / linear / pingpong
    poses: list[str]              # 每帧姿势描述（帧数 = len(poses)）

    @property
    def n_frames(self):
        return len(self.poses)


# 内置标准动作（side/pseudo-side 横版）
STANDARD = {
    "idle": Action("idle", 8, "linear", [
        "standing at rest, weight centered, subtle breathing, arms/props relaxed",
        "very slight downward settle, shoulders lower a touch",
        "lowest point of the idle bob, chest compressed slightly",
        "starting to rise back, shoulders lifting",
        "near neutral again, tiny sway",
        "slight upward drift, breathing in",
        "highest point of idle bob, chest expanded",
        "settling back toward neutral to loop",
    ]),
    "walk": Action("walk", 10, "linear", [
        "mid-stride: one foot stepping forward, weight shifting forward, cloak/props trailing back",
        "passing: rear leg swings under body, body rising",
        "high passing point: supporting leg vertical, other lifted",
        "reaching forward: front foot about to plant",
        "opposite contact: other foot forward (mirror of frame 1)",
        "passing: rear leg swings under, body rising",
        "high passing point on the other side",
        "reaching forward, returning toward the loop start",
    ]),
    "attack": Action("attack", 12, "none", [
        "wind-up: weapon/staff drawn back, weight loaded on back foot",
        "anticipation: body coiled, arm cocked",
        "swing start: weapon accelerating forward",
        "mid-swing: weapon at horizontal, body rotating",
        "impact: weapon fully extended forward, weight on front foot",
        "follow-through: weapon past target, body committed",
        "recovery: pulling weapon back, regaining balance",
        "return to neutral stance",
    ]),
    "jump": Action("jump", 10, "none", [
        "crouch: knees bent, gathering power, arms back",
        "launch: legs extending, pushing off ground",
        "rising: body stretched upward, feet leaving ground",
        "apex: highest point, body compact, limbs tucked",
        "falling: body extending downward, preparing to land",
        "landing: knees bending to absorb impact",
    ]),
}


def get(name, custom_poses=None, fps=10, loop="none"):
    """取动作。标准动作直接取；自定义动作传 custom_poses。"""
    if custom_poses:
        return Action(name, fps, loop, custom_poses)
    if name not in STANDARD:
        raise KeyError(f"未知标准动作 {name}；自定义请传 custom_poses")
    return STANDARD[name]
