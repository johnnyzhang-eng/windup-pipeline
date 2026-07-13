"""自动角色描述 —— 换角色不用手写 --desc，指一张图即可。

用视觉模型看参考图，生成一段"身份描述"填进角色卡。这是"一套代码、多角色"
可扩展的关键：加一个角色 = 加一张图，描述自动来，不写代码、不手写 prompt。
"""
import json, base64, re, urllib.request
from . import config


def describe_character(ref_path, model=None):
    """看参考图 → 返回 {desc, palette, view} 供角色卡使用。"""
    config.require_key()
    model = model or config.VLM_MODEL
    b = base64.b64encode(open(ref_path, "rb").read()).decode()
    prompt = (
        "You are building a game character sheet. Look at this character image and output STRICT JSON: "
        '{"desc": "one concise English sentence capturing art style + key identity features '
        '(hair, outfit, props, colors, body type) — used to keep the character consistent across frames", '
        '"palette": "main colors, comma separated", '
        '"view": "front|profile|pseudo-side|three-quarter (the view in THIS image)"}. '
        "Be specific about distinguishing features (e.g. broken sword, antler crown), omit background.")
    body = {"model": model, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}},
    ]}]}
    req = urllib.request.Request(config.API_BASE + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {config.API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = r.read().decode()
    content = json.loads(txt)["choices"][0]["message"]["content"]
    m = re.search(r'\{.*\}', content, re.S)
    if m:
        return json.loads(m.group(0))
    return {"desc": content.strip()[:300], "palette": "", "view": "unknown"}
