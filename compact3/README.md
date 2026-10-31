# WSC 汉化构建工具

把原版日文 WonderSwan Color ROM 的剧情、名称和 UI 文本替换为中文，并在原版字库页之外生成新的中文字模。

仓库只包含**构建脚本、文本工作簿、字体和码表素材**，不包含游戏 ROM。构建时需要自备原版 ROM。

> **使用须知：补丁仅供自己游玩，禁止分发打补丁后的 ROM。**

当前汉化版本：**V1**（2026-10-26）

## 特性

- 剧情、序章/通关旁白、名称、UI 文本原位导入，保留原指针和原文位置
- 在原版字库页之外生成中文字模（E000–E7FF，双 bank）
- F1 预渲染宏：长武器名、机体名、角色名、菜单标签
- 名称表重排、别名和爱称同步，剧情说话人按名称表解析
- 构建时校验字体、行宽、码表回读和指针
- 自动生成码表，包含中文码表、特殊字模、单字节和带 tile 的日文码表

## 环境

- Python 3.10+
- 原版日文 ROM（自备，不随仓库提供）
- 依赖：

```bash
pip install -r requirements.txt
```

## 字体

构建需要三个字体：

| 文件 | 说明 |
|---|---|
| `assets/fonts/wenquanyi_9pt.ttf` | 文泉驿 9pt，随仓库提供 |
| `assets/fonts/zpix.ttf` | Zpix 点阵字体，随仓库提供 |
| `assets/fonts/simsun.ttc` | 宋体，**因授权不随仓库提供**，请自备放入该路径 |

构建启动时会检查这三个字体，缺少会直接报错。字体版权归原作者，遵循各自的原始许可；本项目的 GPLv3 不改变字体许可。

## 快速开始

```bash
pip install -r requirements.txt

# 把自备的 simsun.ttc 放到 assets/fonts/simsun.ttc

python build.py -i "原版游戏.wsc" -o "输出游戏.wsc"
```

Windows 下路径含空格或中文时请加引号。

## 命令行

| 参数 | 说明 |
|---|---|
| `-i, --input` | 原版日文 ROM，必填 |
| `-o, --output` | 输出中文 ROM，必填 |
| `--text` | 文本工作簿，默认从 `assets/text/*.tsv` 重建（无 TSV 时用 `assets/text.xlsx`） |
| `--codebook` | 码表输出，默认 `<输出名>_码表.xlsx` |
| `--no-xlsx` | 不生成码表 |
| `--dry-run` | 只校验数据，不写 ROM |

示例：

```bash
python build.py -i "../original.wsc" -o "../output.wsc" \
  --text assets/text.xlsx --codebook "../output_码表.xlsx"
```

## 文本编辑与同步

git 里保存的是纯文本镜像 `assets/text/*.tsv`（每个工作表一个文件，commit diff 逐行可见）；
`assets/text.xlsx` 已移出版本库。两者通过 `text_sync.py` 同步：

```bash
python text_sync.py export          # 在 Excel 里改完 text.xlsx 后：xlsx -> TSV，然后提交 TSV
python text_sync.py xlsx            # 新 clone 后：TSV -> 重建 assets/text.xlsx（供 Excel 编辑 / sync_names.py）
python text_sync.py check           # 检查本地 text.xlsx 与 TSV 是否一致
```

- 构建不需要 xlsx：`build.py` 会自动从 TSV 重建 `assets/text.build.xlsx`（已忽略）再解析。
- 在 Excel 里改完忘记 `export` 时，构建会提示 text.xlsx 比 TSV 新。
- 改名称表后照旧运行 `sync_names.py`（它编辑的是 `assets/text.xlsx`），完成后 `export` 再提交。
- 不要用 Excel 直接编辑 TSV（会破坏编码/转义）；要改文本就在 xlsx 里改，或直接改 TSV。

## 网页打补丁

`index.html` 是自带补丁数据的单文件页面，可直接双击打开，也可以放到 GitHub Pages。拖入原版 ROM，校验通过后页面会显示 **补丁信息（V1、破解/初翻、校准、测试、杂活）** 和原版→输出 CRC；确认后点击应用，即可下载汉化 ROM。所有处理都在浏览器本地完成，不上传 ROM。

需要支持 `DecompressionStream` 的新版 Chrome / Edge / Firefox。补丁只适用于页面显示的原版 CRC；换 ROM 或重新构建后，用同一条命令重新生成页面：

```bash
python make_patch_web.py -i "原版.wsc" -o "汉化.wsc"
```

## 目录

```
assets/
  text/                      文本镜像 TSV（git 唯一事实源，每表一个文件 + _manifest.json）
  text.xlsx                  文本工作簿（gitignored；由 text_sync.py 生成/导出）
  text.build.xlsx            构建时从 TSV 重建的工作簿（gitignored，自动生成）
  verified_kanji.jsonl       日文码表核对数据
  fonts/                     正文、单字节、F1 宏使用的字体
  img/                       标题文字层/背景 PNG（-cn 优先，-jp 为原图；含单元表）
build.py                     构建脚本
titleimg.py                  标题文字图块：PNG → 压缩块 → 写回 ROM
finalcard.py                 最终话标题卡：PNG → 两块 LZSS → 写回 ROM
stagecard.py                 第二话标题卡第二行：PNG → 0x730A02 块
make_patch_web.py            生成自带补丁的 index.html
index.html                   网页打补丁页面
sync_names.py                按名称表同步剧情说话人（可选工具，编辑 text.xlsx）
text_sync.py                 text.xlsx 与 assets/text/*.tsv 的双向同步
patch_notes.md               11 行非文本字节改动的逐条说明
LICENSE                      GPLv3.0
requirements.txt             Python 依赖
```

## 输出

- `-o` 指定的中文 ROM；发布版命名为 `超级机器人大战compact3[cn][lcdyk][v1].wsc`，与 `index.html` 打补丁后下载的文件名一致
- 默认在同目录生成 `<输出名>_码表.xlsx`，包含：
  - `中文码表`：新字模的码位、字符、槽位、字模 hex、使用次数
  - `特殊字模`：覆盖原字库槽的特殊字模
  - `单字节`：ASCII/数字字模
  - `日文码表`：F200–F9FF 共 2048 项，列为 `Fxxx码 / 日文字 / tile / 字模`
  - `统计`、`校验`

码表和 ROM 输出已被 `.gitignore` 忽略，不会误提交。

## 汉化范围

- 正文、序章和通关旁白、角色/机体/武器/道具名称、UI 文本、F1 宏已导入
- 图片标题只做了最终话；常规关卡标题是叠在地图上的文字，不做图片汉化
- 翻译和校对数据都在 `assets/text/`（TSV 镜像，对应 `assets/text.xlsx`），构建不读 `校准` 列

## 常见问题

**缺少字体**
构建会列出缺失路径。宋体需自备；文泉驿和 Zpix 在仓库内。

**文本工作簿被 WPS 占用**
可复制一份临时工作簿，用 `--text` 指向副本构建：

```bash
python build.py -i original.wsc -o output.wsc --text temp.xlsx
```

**输出 CRC 和文档里的不一样**
CRC 随文本、字体和构建数据变化，以实际构建为准。

**没有原版 ROM**
本项目不提供 ROM。请使用自己拥有的正版 ROM，并遵守当地法律。

## 汉化信息（V1）

- 破解：deepseek v4.1flash
- 文本初翻译：deepseek v4.1flash
- 文本第一轮校准：glm5.3
- 文本第二轮校准：gemini + glm5.3flash 翻译，deepseek 4.1flash 筛选
- 流程测试：Lily
- 干杂活：lcdyk

## Bug 反馈

遇到 bug 请添加 QQ：**lcdyk66**，备注「游戏名 + 出现什么 bug」，并附上截图；有存档或即时存档更好。请勿发送 ROM。

如果愿意参与剧情翻译或校准，也欢迎添加同一个 QQ，备注「游戏名 + 翻译」或「游戏名 + 校准」。

## 版权与许可

- 本项目代码和文档以 **GNU General Public License v3.0** 发布，见 [LICENSE](LICENSE)。
- Copyright (C) 2026 lcdyk and contributors。
- 游戏 ROM、游戏原文、图像及其他原作素材的版权归原权利人所有，**不在本项目的 GPL 授权范围内**。
- 本项目是非官方粉丝汉化，与版权方无关；不提供、不鼓励传播 ROM。请支持正版。
- `simsun.ttc` 因授权原因不随仓库分发；文泉驿、Zpix 等第三方字体遵循各自的原始许可证。
- 请勿在 Issue、PR 或仓库中上传 ROM、存档或宋体字体文件。

## 贡献

欢迎提交 Issue 和 PR。提交前请：

1. 确认没有包含 ROM、存档或宋体字体；
2. 用自备原版 ROM 跑通 `python build.py -i ... -o ...`；
3. 文本改动尽量附上对应的页面/索引，方便复核。
