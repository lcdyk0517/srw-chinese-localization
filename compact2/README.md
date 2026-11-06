# Super Robot Wars Compact 2 三部曲 汉化构建

把原版日文 WonderSwan ROM 的剧情、战斗台词、事件文本、名称和 UI 替换为中文，并在原版字库页之外生成中文字模。

仓库只包含**构建脚本、文本工作簿、字体和码表素材**，不包含游戏 ROM。构建时需要自备三作原版 ROM。

> **使用须知：补丁仅供自己游玩，禁止分发打补丁后的 ROM。**

当前版本：V1（2026-11-05）

技术细节（字库/4096 扩容、FA/FB 8px 页、文本重定位、跳过动画地址与验证）：
[docs/technical-notes.md](docs/technical-notes.md)

## 环境

- Python 3.12（主构建模块按 3.12 编译）
- 原版日文 ROM（自备，不随仓库提供）
- 依赖：

```bash
pip install -r requirements.txt
```

## 字体

构建需要三个字体，放在 `assets/Dai1/assets/fonts/`、`assets/Dai2/assets/fonts/`、`assets/Dai3/assets/fonts/`：

| 文件 | 说明 |
|---|---|
| `wenquanyi_9pt.ttf` | 文泉驿 9pt，随仓库提供 |
| `zpix.ttf` | Zpix 点阵字体，随仓库提供 |
| `simsun.ttc` | 宋体，**因授权不随仓库提供**，请自备放入三个目录 |

字体版权归原作者，遵循各自的原始许可；本项目的 GPLv3 不改变字体许可。

## 快速开始

```bash
pip install -r requirements.txt

python build.py \
  --d1 "Super Robot Taisen Compact 2 - Dai-1-bu - Chijou Gekidou Hen (Japan).ws" \
  --d2 "Super Robot Taisen Compact 2 - Dai-2-bu - Uchuu Gekishin Hen (Japan) (Rev 4).ws" \
  --d3 "Super Robot Taisen Compact 2 - Dai-3-bu - Ginga Kessen Hen (Japan) (Rev 2).ws" \
  -o out
```

原版 CRC 必须匹配：

| 作品 | CRC32 |
|---|---|
| 第1部 地上激动篇 | `782877BC` |
| 第2部 宇宙激震篇（Rev 4） | `ECBB46DE` |
| 第3部 银河决战篇（Rev 2） | `0B0F8981` |

输出：

```
out/超级机器人大战compact2-1[cn][lcdyk][v1].ws
out/超级机器人大战compact2-2[cn][lcdyk][v1].ws
out/超级机器人大战compact2-3[cn][lcdyk][v1].ws
```

构建在临时目录 `compact2-build-*` 中完成，结束自动清理；加 `--keep-work` 可保留中间产物。

## 目录

```
assets/
  Dai1/ text.xlsx、ws2lib.py、assets/（cmap_fixed、字体、码表素材）
  Dai2/ 同上 + event_bank_zh.json
  Dai3/ 同上 + event_bank_zh.json
tools/
  build_xbank.py        构建入口/跨 bank 剧情重排
  story_xfunc2.py       剧情两行重排与载入器
  ws2_common.py         文本读取
  build_test_import_full.pyc  主文本/名称/UI 导入模块
  build_lib_append.py / font4096.py  辅助源码
build.py                三部曲统一构建入口
index.html              网页补丁（三部曲自动识别，宋体/融合像素双字体）
```

## 网页补丁（双字体）

`index.html` 是自包含的纯静态补丁页：拖入三部曲任意一部日文原版 `.ws`，
先按 CRC 识别作品并校验，再选择「宋体」或「融合像素」，浏览器本地应用
内嵌的 XDF1 补丁并校验输出 CRC；不上传 ROM、不依赖服务器。

重新生成前需要两套字体 ROM 和两套跳过版：

```bash
# 一次构建宋体 + 融合像素 CN ROM
python build.py --d1 <D1.ws> --d2 <D2.ws> --d3 <D3.ws> --fonts both -o out

# 跳过版：用外部跳过动画构建器生成，并放到独立目录（文件名固定）
#   skip/D1_CN_skip.ws / D2_CN_skip.ws / D3_CN_skip.ws
#   skip/D1_CN_fusion_skip.ws / D2_CN_fusion_skip.ws / D3_CN_fusion_skip.ws
# 注意跳过版不要放进 --fusion-dir，融合 ROM 选择会优先匹配 D*_CN*fusion*.ws

# 生成网页
python tools/make_patch_web.py --orig-dir <原版目录> \
  --simsun-dir out --fusion-dir out --skip-dir skip -o index.html
```

当前网页内嵌的补丁输出 CRC：

| 作品 | 宋体 CN | 宋体 + 跳过 | 融合像素 CN | 融合 + 跳过 |
|---|---|---|---|---|
| D1 | `C31AFCE9` | `9B7C0AED` | `49DBB3FA` | `11BD45FE` |
| D2 | `D08AD539` | `E027E087` | `7F77CF5C` | `2E984730` |
| D3 | `12228B0B` | `8D75B504` | `7BD93CEA` | `E48E02E5` |

2026-11-03：武器名统一 80px（零距离光束加农炮、奥克斯坦发射器 88px / 11 格），FA/FB 8px 页；所有 `alloc_text`/`_alloc_bank35` 重定位串要求前一个字节为 FF、尾部只保留 1 个 FF 终止符，芯片/通关标签改为独立分配；修复跳过版奇迹说明串尾 FF 被「动画 开」覆盖导致的多余字；修复 D1/D2 反击战跳过白屏（单位结构例程入口改为含 `push ax/dx` 序言的 `F000:5136` / `F000:5204`）；D1/D2 无援护空跑改为直接泵战斗脚本解释器（`E000:3E20` / `E000:46A0`，按 `0x887/0x889` 在两种解释器间分流），白屏从约 100 帧降到 10 帧以内；援护战改为逐帧 `int 0x25`，避免漏掉援护单位结算导致伤害丢失或花屏；结算后的单位表与完整动画逐字节一致；跳过动画版同步重建。
2026-11-05：机体名统一为 `GP03 石斛兰`、`GP03S 雄蕊`（D1/D2/D3 名称表与索引同步），D2 相关剧情台词改为「雄蕊 / 与GP03S 雄蕊合体后」。
2026-11-06：台词引用修补改为按指针表特征匹配：只改前后连续 5 项单调、且相邻项都落在同一偏移区间的真正表项；bank25/26 事件脚本里的 `45 E6 CF 69 4D` 字节流不再误改（D1 `0x254208` 曾因此战斗后跳飞白屏）。

网页补丁在汉化完成后会弹窗询问「是否同时打上跳过动画补丁？」；选择是则再应用一份以汉化输出为源的 XDF，选否只保留汉化。跳过版系统菜单第 6 项为「动画 开 / 动画 关」，中间用一个双字节空白字模。

网页下载名：汉化 `…[v1].ws`，跳过动画 `…[v1][skip].ws`；融合像素为 `…[v1][fusion].ws` / `…[v1][fusion][skip].ws`。

网页补丁只包含补丁数据，不包含 ROM；请勿把打补丁后的 ROM 上传或再分发。

## 构建内容

- 剧情/战斗台词/事件 bank、旁白、名称、UI 文本导入
- 名称表重排、别名/爱称同步、剧情说话人按名称表解析
- 跨 bank 剧情重排与载入器补丁
- F1 宏：长武器名、机体名、角色名、菜单标签
- 9 字以上角色/机体名 F1 宏（名称指针重定向，保留原字模与码位）
- F1 宏在 `text.xlsx` 的 `F1宏` 页配置：宏号、目标宽、字宽、逐字宽、字间距、字体、字号、模式；`F1宏说明` 页有列说明
- **武器名 80px（FA 页 + FB 宏）**：`FA页` 页存每作的 8×16 单字节字模页、4096 字库跳板、cave、FB 处理器/表/体地址、名称表范围；`FB武器名` 页逐条配置布局（逐字/S-DX）、左右空、ASCII 宽/间隔、逐字宽、条带宽、格数、FA 起始格、FB 号。名称池里只写 `FB id FF`（3 字节），FB 体每字节一个 FA 格号，FF 结束；FA/FB 走 ROM 原生单字节 8px 绘制路径，原 `01-DF`、`E0-EF`、`F2-F9` 不动。构建时自动审计正文不得出现 FA/FB 前导码，并在产物写 `FAFB表.txt`
- 事件 bank 0x18/0x1A（通关奖励、戈尔曼等事件台词）
- 奇迹说明、艾克塞琳·勃朗宁等固定串修订

## 说明

主文本导入模块 `tools/build_test_import_full.pyc` 目前以编译字节码形式提供（其原始 `.py` 在历史编辑中丢失，恢复工作仍在进行）。构建在 Python 3.12 下可复现；欢迎协助恢复源码。构建工作簿统一命名为 `text.xlsx`；编译模块内部仍写死旧中文文件名，`build_xbank.py` 会在构建期间临时生成兼容副本并在结束后删除。

已知未译：无。D3 结局 bank3B（552 行）与最终章 bank18（496 行）已收入 `text.xlsx` 的 `剧情_3B`/`剧情_18` 并翻译导入；三作名称表已统一，战斗台词说话人名与名称表一致。

## 版权与许可

- 本项目代码和文档以 **GNU General Public License v3.0** 发布，见 [LICENSE](LICENSE)。
- Copyright (C) 2026 lcdyk and contributors。
- 游戏 ROM、游戏原文、图像及其他原作素材版权归原权利人所有，**不在本项目的 GPL 授权范围内**。
- 本项目是非官方粉丝汉化，与版权方无关；不提供、不鼓励传播 ROM。请支持正版。
- `simsun.ttc` 因授权原因不随仓库分发；文泉驿、Zpix 等第三方字体遵循各自许可证。
- 请勿在 Issue、PR 或仓库中上传 ROM、存档或宋体字体文件。

## Bug 反馈

QQ：**lcdyk0517**，备注「游戏名 + 问题」，附截图；有存档或即时存档更好。请勿发送 ROM。

## 文本入库（TSV 镜像）

与 compact3 相同：`assets/DaiN/text/*.tsv` + `_manifest.json` 是入库源，
每个 sheet 一个 TSV，改动可按行 diff。`assets/DaiN/text.xlsx` 仅作本地编辑面
（已 gitignore）。构建时 `build.py` 调用 `tools/text_sync.py` 从 TSV 重建
`text.build.xlsx`，原有解析逻辑不变。

- 在 Excel 改完：`python tools/text_sync.py --game Dai2 export`
- 新 clone 生成可编辑工作簿：`python tools/text_sync.py --game Dai2 xlsx`
- 校验 TSV 与 xlsx 一致：`python tools/text_sync.py --game Dai2 check`
