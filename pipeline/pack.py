"""⑦ 打包：对齐后的帧 → sprite sheet + JSON(TexturePacker) + plist(Cocos) + GIF 预览。"""
import json
from PIL import Image


def sprite_sheet(frames, out_png):
    """横向拼 sprite sheet。frames: [PIL.Image(cell×cell)]。"""
    cell = frames[0].width; n = len(frames)
    sheet = Image.new("RGBA", (cell * n, cell), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.alpha_composite(f, (i * cell, 0))
    sheet.save(out_png)
    return sheet


def write_json(n, cell, out_json, sheet_name="sprite_sheet.png"):
    """TexturePacker 风格 JSON（Phaser / 通用可读）。"""
    tp = {"frames": {}, "meta": {"app": "Windup", "image": sheet_name,
          "format": "RGBA8888", "size": {"w": cell * n, "h": cell}, "scale": "1"}}
    for i in range(n):
        tp["frames"][f"walk_{i:02d}.png"] = {
            "frame": {"x": i * cell, "y": 0, "w": cell, "h": cell},
            "rotated": False, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": cell, "h": cell},
            "sourceSize": {"w": cell, "h": cell},
            "pivot": {"x": 0.5, "y": 0.08}}   # 脚底中心
    open(out_json, "w").write(json.dumps(tp, indent=2, ensure_ascii=False))


def write_plist(n, cell, out_plist, sheet_name="sprite_sheet.png"):
    """Cocos SpriteFrames plist。"""
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
         '<plist version="1.0"><dict>', '<key>frames</key><dict>']
    for i in range(n):
        p += [f'<key>walk_{i:02d}.png</key><dict>',
              f'<key>frame</key><string>{{{{{i*cell},0}},{{{cell},{cell}}}}}</string>',
              '<key>offset</key><string>{0,0}</string>', '<key>rotated</key><false/>',
              f'<key>sourceColorRect</key><string>{{{{0,0}},{{{cell},{cell}}}}}</string>',
              f'<key>sourceSize</key><string>{{{cell},{cell}}}</string>', '</dict>']
    p += ['</dict>', '<key>metadata</key><dict>', '<key>format</key><integer>2</integer>',
          f'<key>size</key><string>{{{cell*n},{cell}}}</string>',
          f'<key>textureFileName</key><string>{sheet_name}</string>', '</dict>', '</dict></plist>']
    open(out_plist, "w").write("\n".join(p))


def gif(frames, out_gif, duration=120, bg=(40, 40, 55, 255)):
    """合成预览 GIF（GIF 不支持 alpha 动画，铺底色）。"""
    def ondark(im):
        base = Image.new("RGBA", im.size, bg)
        return Image.alpha_composite(base, im).convert("P", palette=Image.ADAPTIVE)
    g = [ondark(f) for f in frames]
    g[0].save(out_gif, save_all=True, append_images=g[1:],
              duration=duration, loop=0, disposal=2)
