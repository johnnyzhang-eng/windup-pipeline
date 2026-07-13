# game-asset-character

从一段角色设定或一张参考图出发，得到「同一个角色的一套动作」——逐帧检查后一键导出可预览、可复用、且能直接进 Cocos / 小游戏跑起来的动作资产。差异化内核是「生成之后、进引擎之前」那段最后一公里自动化（逐帧对齐 + 循环闭合 + 去光晕 + 引擎原生交付）。

## 当前状态：MS1 空骨架（首个可串联版本）

接口为真、实现桩空、主干已串联、数据 mock。跑通冒烟即证明主干成立。

```bash
cd skeleton
python3 smoke.py          # 空跑串联，打印 mock 交付文件
python3 -m pytest -q      # 或跑冒烟测试（需 pytest）
```

## 结构

```
gac/
  models.py        领域数据模型（Project/Character/角色卡/动作/帧序列/生成记录/版本/交付包）
  interfaces.py    模块对外接口契约
  generation/      生成端（路线 A 主线 / 路线 B spike）
  lastmile/        最后一公里：matting 去光晕 · alignment 逐帧对齐 · loop 循环闭合
  packaging.py     统一输出契约打包
  export/          引擎导出（cocos 首靶 / godot P1）
  assetstore.py    角色卡 / 生成记录 / 版本
  evaluation.py    批量评测脚本
  pipeline.py      编排器（串联主干）
```

## 路线图

- MS1：主干串联可跑通（本骨架）。
- MS2：填实最后一公里（alignment / matting）与生成路线 A，导出真 Cocos 资源。
- 详见产品 Proposal 与《MS1-架构主干-空骨架》。

> 设计依据见团队产品 Proposal（§2.8 基本概念与信息结构直接映射到 `models.py`）。
