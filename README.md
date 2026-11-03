# SRW 汉化补丁与工具

本仓库提供《超级机器人大战》系列（WonderSwan / WonderSwan Color）的汉化补丁与构建工具。
所有项目只包含补丁、构建脚本、文本工作簿和码表素材，**不包含游戏 ROM**；用自备的原版日文 ROM 即可复现构建。

## 项目

| 项目 | 平台 | 内容 |
|---|---|---|
| [compact2/](compact2/) | WS 2MB ×3 | 《超级机器人大战 COMPACT2》三部曲汉化 |
| [compact3/](compact3/) | WSC 4MB | 《超级机器人大战 COMPACT3》汉化，另含网页补丁页 |

### compact2

三部曲统一入口：

```bash
pip install -r requirements.txt

python build.py \
  --d1 "第1部.ws" --d2 "第2部.ws" --d3 "第3部.ws" -o out
```

- 原版 CRC32：第1部 `782877BC`、第2部 `ECBB46DE`、第3部 `0B0F8981`
- 详见 [compact2/README.md](compact2/README.md)

### compact3

```bash
pip install -r requirements.txt

python build.py -i "原版.wsc" -o "输出.wsc"
```

- 网页补丁：双击 `compact3/index.html`，拖入原版日文 ROM，校验通过后本地打补丁（不上传、不联网）
- 详见 [compact3/README.md](compact3/README.md)

## 构建环境

- Python 3.10+，依赖见各项目 `requirements.txt`
- 字体：`zpix.ttf`、`wenquanyi_9pt.ttf` 等随仓库提供；**宋体 `simsun.ttc` 因授权不随仓库分发**，请自备放入各项目的 `assets/fonts/`
- 构建生成的 ROM 与码表已被 `.gitignore` 忽略

## 使用须知

- 仓库只包含补丁与工具，**不提供游戏 ROM**。
- 补丁仅供自己游玩，**禁止分发汉化后的 ROM**。
- 请使用自己拥有的正版原版 ROM。

## 反馈

Bug 反馈、参与剧情翻译或校准：QQ **lcdyk66**，备注「游戏名 + 出现什么 bug」或「游戏名 + 翻译 / 校准」。

## 许可

GPLv3.0，见 [LICENSE](LICENSE)。
