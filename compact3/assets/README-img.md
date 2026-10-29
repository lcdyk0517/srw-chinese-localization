# 标题/图形素材

命名：`<名字>-jp.png` 原图，`<名字>-cn.png` 汉化图；构建优先 `-cn`，没有就用 `-jp`。

当前只导入：
- `title-bg-cn.png`（或 `-jp`）：标题背景/LOGO 合成层，块 `0x5196C8`。
- `title-logo-layer-cn.png`/`-jp.png`：LOGO 图层源；`title-bg` 已包含 LOGO，引擎同一压缩块不再重复写。

已取消/删除：
- `title-push-text-cn`、`title-menu-text-cn`：标题文字不汉化，保留 `-jp` 参考。
- `final-card-text-cn`、`stage2-title-cn`：最终话卡和第二话卡取消，保留 `-jp` 参考。
- `title-fire-jp.png`、`stage-titles/`：已删除。
- 截图/模板/导出索引不在本目录；参考在 `产物/素材/`。

单元/OAM 映射在 `构建/assets/cells/title-bg.cells.json`。
