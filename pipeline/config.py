"""共享配置。API key 从环境变量读，绝不硬编码。

用法：
    export SUFY_KEY=你的key          # 图像生成 API 的 key
    export SUFY_BASE=https://.../v1   # 可选，OpenAI 兼容端点，默认见下
"""
import os

API_KEY = os.environ.get("SUFY_KEY", "")
API_BASE = os.environ.get("SUFY_BASE", "https://openai.sufy.com/v1")
IMAGE_MODEL = os.environ.get("SUFY_IMAGE_MODEL", "gemini-2.5-flash-image")
VLM_MODEL = os.environ.get("SUFY_VLM_MODEL", "gemini-2.5-flash")   # 质检/描述用视觉模型（实测稳定）

# 生成时统一的背景/风格约束（避开角色主色 → 用品红；无阴影便于抠图）
BG_MAGENTA = "SOLID MAGENTA background #FF00FF"
NO_SHADOW = "NO shadow"

# sprite 规格
CELL = 256          # 单帧输出边长
FOOT_RATIO = 0.90   # 脚底基线在画布高度的比例

def require_key():
    if not API_KEY:
        raise SystemExit("请先设置环境变量 SUFY_KEY（图像生成 API 的 key）")
    return API_KEY
