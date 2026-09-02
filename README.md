# wxgame —— 微信小游戏脚本集

一个游戏一个文件夹。当前内容：

| 目录 | 游戏 | 说明 |
|---|---|---|
| `C:\projects\wxgame\zcds\` | **占城大师** | 后台自动挂机机器人 + 逆向资料（主力项目，v3.1） |
| `C:\projects\wxgame\mxdzz\` | （旧项目） | 以前做的项目（同类自动化脚本），**只读参考**：点色指纹/页面路由就是从这里移植过来的。运行时不依赖它，也别往它目录里写东西 |

## 加一个新游戏怎么做

1. **新建一个游戏文件夹**，名字用 ASCII 短名（如 `zcds`），别用中文。
   原因：像 `battle_scan.py` 这种代码要 `import cv2` 并 `np.load(...)`，OpenCV 在含非 ASCII
   字符的 Windows 路径上会静默失败（读图返回 None / 加载模板报错），排查很痛。
2. **照抄 `zcds\` 的内部结构**（这套结构是被验证过的，工具的路径推导依赖它）：

   ```
   <游戏名>/
     auto_bot.py          主循环：抓窗口 -> route() 定页面 -> page.act() 动作
     colorprint.py        点色指纹原语（tolerance / is_color / print_score / scale_points）
     pages/               一个页面一个文件：points 指纹(定身份) + act()(OCR 动作)
     pages/base.py        Page 基类 + route()/match_print() 路由
     shots/               标定语料截图（同一尺寸，本项目 552x1006）
     tools/               标定器：pick_print.py(check/pick/verify) + print_stats.py
     scratch/             一次性脚本/中间产物归档 + MANIFEST.tsv + restore.py
     COLORPRINT.md        点色指纹那一层的说明
   ```

   `tools/*.py` 里 `ROOT = dirname(dirname(__file__))`，所以 **tools 必须和 pages、shots 同级**，
   不能提到上一层当公共工具，否则它会把 `C:\projects` 当成项目根。
3. **可复用 vs 专属**：`colorprint.py` + `pages/base.py` 的 `route()` 是通用的，直接拷；
   `tools/pick_print.py` 的 `LABELS`/`GROUPS`/`OFFSETS` 和 `shots/` 语料是游戏专属，要重新标定。
   先别急着抽象成公共库——等第二个游戏真跑起来，重复的地方才有意义。
4. **坐标约定注意**：本项目 `is_color(img, x, y, ...)` 是 **(x=列, y=行)**，
   和 mxdzz 的 `capture()[x, y]`（实际是 [行, 列]）**正好相反**，别把 mxdzz 页面里的 points 数值直接搬过来。
5. **不要在代码里写绝对路径**。统一从 `__file__` 推：
   `ROOT = os.path.dirname(os.path.abspath(__file__))`（`zcds/config.py` 里已经暴露了 `ROOT` / `SHOTS_DIR`）。
   这条是全项目扫出来的教训：搬家前 `C:\projects\wxgame` 被硬编码在 **111 个文件 / 205 处**（还没算 `bot.log` 里 1706 条历史输出）。

## 约定（所有游戏文件夹共用）

- 临时文件一律进该游戏的 `scratch/`（`scripts/` `images/` `data/` 三类），并且**只搬不删**，
  同时往 `scratch/MANIFEST.tsv` 记一条「原相对路径 -> 现相对路径 -> 字节数」，配 `restore.py` 能一键搬回。
- 日志（`bot.log`）是历史记录，**不去改写它里面的旧路径**，保持原样。
- 文本行尾：`.py` 用 BOM+CRLF 或无 BOM+CRLF 都行，但**不允许同一文件里混着 CRLF 和裸 LF**。
- 没有 git。所以任何「整理」都只做移动，不做删除。
- 搬家要可逆：`zcds\scratch\restore.py`（还原 scratch 归档）、`zcds\scratch\relocate.py`（把整个游戏
  文件夹挪回上一级或别的目录），两个都支持 `--dry-run`，且绝不覆盖已存在的目标。
