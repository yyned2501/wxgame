# zcds 架构文档

> 占城大师后台挂机 v3.x。重构目标 = 解耦 + 分层 + 共享代码到 libs。
> 文档维护者：zcds 维护者
> 最后更新：2026-09-09

## 1. 顶层分层

```
zcds/
├── ARCHITECTURE.md          ← 本文档
├── README.md                ← 用户文档（怎么跑、怎么验证）
├── COLORPRINT.md            ← 点色指纹原理
│
├── libs/                    ← 共享库（被 pages/auto_bot/tools 依赖）
│   ├── window.py            ← 窗口/截图/click/drag（封装 game_utils）
│   ├── color.py             ← 点色指纹（封装 colorprint）
│   ├── vision.py            ← OCR + ScreenFeature（封装 vision）
│   ├── routing.py           ← 路由 + 软命中（从 pages/base.py 抽出）
│   └── config.py            ← PAGE_CFG/WATCH_ADS 等全局常量
│
├── pages/                   ← 页面实现（依赖 libs）
│   ├── base.py              ← Page 基类（已瘦身 ~200 行）
│   ├── battle.py lobby.py ...
│
├── auto_bot.py              ← 主类 App（主循环 + 组装 libs 依赖）
│
├── tools/                   ← 独立 CLI 工具（不再 import auto_bot）
│   └── live_audit.py pick_print.py ...
│
├── tests/                   ← 回归脚本（test_*.py 移到这里）
│   └── test_battle_loop.py test_print_route.py ...
│
├── shots/  shots_live/      ← 标定语料 + 真机取证帧（不入 git）
├── wxapkg_out/              ← 微信小程序解包产物（不入 git）
├── scratch/                 ← 一次性脚本/中间产物（不入 git）
└── tools/{dump_renderer,wxapkg_dec,wasm_map,api_client,...}  ← 逆向工具
```

## 2. 依赖方向（单向向下）

```
                 ┌─────────────────────┐
                 │       App           │  ← 主类，主循环
                 │   (auto_bot.py)     │
                 └──────────┬──────────┘
                            │ 注入 Window/Color/Vision
                            ▼
       ┌────────────────────────────────────────┐
       │              libs/                     │
       │  window  color  vision  routing        │
       └──────────┬───────────────┬─────────────┘
                  │               │
                  ▼               ▼
            ┌──────────┐   ┌────────────────┐
            │  pages/  │   │      tools/     │
            │ 17 个页面│   │ 独立 CLI 脚本   │
            └──────────┘   └────────────────┘
                  │               │
                  └───────┬───────┘
                          ▼
                    ┌──────────┐
                    │  tests/  │
                    │ 18 个回归 │
                    └──────────┘
```

**铁律**：
- `pages/` **绝不** import `auto_bot` 或 `tools`
- `tools/` **绝不** import `auto_bot.App` 或 `pages`
- `libs/` **绝不** import `pages` 或 `auto_bot`
- 唯一反向入口：`App` 主动调用 `Page.act(ctx)`，`tools/*` 通过独立 CLI 调用

## 3. libs/ 模块职责 (2026-09-09 修正: libs 只放通用工具, 不掺业务)

**铁律**: libs/ **绝不操作业务**. 业务函数 (广告/弹窗/引导/导航/转场) 留在 `pages/base.py` 或独立业务模块.

| 模块 | 旧位置 | 职责 (无业务) |
|---|---|---|
| `libs/window.py` | `game_utils.py` | hwnd 查找/截图/click/drag/widget 子窗口查找. **类封装**取代 `g.u32.PostMessageW` |
| `libs/color.py` | `colorprint.py` | 点色指纹 (REF_SIZE/print_score/tolerance/is_color). **类封装** |
| `libs/vision.py` | `vision.py` | OCR (rapidocr 封装)、ScreenFeature 数据结构 |
| `libs/routing.py` | `pages/base.py` | 路由: route_prints/is_soft/match_print/detect_ocr/route/select_page (无游戏知识, 纯框架) |
| `libs/config.py` | `config.py` | PAGE_CFG (每页 ROI/poll/ocr_gap)、WATCH_ADS、AD_FOCUS |

**被删除** (2026-09-09 用户反馈"libs 不应操作业务"):
- ~~`libs/ad.py`~~ -> 业务, 放 pages/base.py (`ad_close_pos`/`ad_claim_pos`/`ad_pill_state` 等)
- ~~`libs/modal.py`~~ -> 业务, 放 pages/base.py (`find_close_badge`/`guide_modal`/`is_transition` 等)
- ~~`libs/navigation.py`~~ -> 业务, 放 pages/base.py (`nav_present`/`nav_tab_cx` 等)

```python
# ❌ 旧：全局函数模块
import game_utils as g
g.find_game_window()
g.u32.PostMessageW(hwnd, 0x0201, 0, lp)

# ✅ 新：类封装 + 依赖注入
from libs.window import Window
class App:
    def __init__(self):
        self.window = Window()
    def click(self, x, y):
        self.window.click(self.ctx, x, y)   # ctx 由 App 持有
```

## 4. Page 基类瘦身

旧 `pages/base.py` **805 行**（基类 + 路由 + 通用动作全塞一起），重构后：

| 内容 | 旧位置 | 新位置 | 行数预估 |
|---|---|---|---|
| Page 类（act/detect/fingerprints/points） | `pages/base.py` | `pages/base.py` | ~150 |
| route_prints、is_soft、print_match | `pages/base.py` | `libs/routing.py` | ~100 |
| find_close_badge、is_countdown | `pages/base.py` | `libs/color.py` | ~80 |
| color_button、color_pixels | `pages/base.py` | `libs/color.py` | ~100 |
| CHEST_BLOCK_ALL、CHEST_PAID_BLOCK 等常量 | `pages/base.py` | `libs/config.py` | ~30 |

新 `pages/base.py` 只剩 ~150-200 行 Page 类骨架。

## 5. 依赖注入流程

```python
# auto_bot.py
class App:
    def __init__(self):
        self.window = Window()           # hwnd + 截图 + click + drag
        self.color = Color()             # 点色指纹 + color_pixels
        self.vision = Vision(self.window)  # OCR + ScreenFeature
        self.ctx = Ctx(window=self.window, color=self.color, vision=self.vision)
        self.pages = {p.name: p() for p in ALL_PAGES}

    def step(self):
        img = self.window.capture()
        feature = self.vision.ocr(img) if need_ocr else ScreenFeature(img=img)
        page = self._route(feature)
        acted = page.act(self.ctx)
        return page, acted, ...
```

每个 Page 的 `act(ctx)` 通过 ctx 拿到 window/color/vision 实例，**不再用全局函数**。

## 6. tools 改独立 CLI

旧 `tools/live_audit.py` 等会 `from auto_bot import App` 拿主类实例，**反依赖**。

新设计：每个工具独立脚本，自己开窗口/跑 OCR/判页：

```python
# tools/live_audit.py (CLI 入口)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shots-dir', default='shots_live')
    args = ap.parse_args()
    win = Window()
    color = Color()
    for f in glob(f'{args.shots_dir}/*.png'):
        img = win.capture_from_file(f)
        page = route_image(img, color)   # 用 libs 的路由
        if not check_label(f, page):
            print(f'{f}: 标签 vs 路由不一致')
            sys.exit(1)
```

不再 `import auto_bot`，彻底独立。

## 7. 与 mxdzz 的关系

README 提到 `mxdzz/` 是**只读参考**（同类自动化脚本，点色指纹/页面路由从这里移植）。

**zcds 不依赖 mxdzz 代码**，但**代码风格参照** mxdzz：
- 点色指纹判定口径一致
- 页面路由逻辑（route_prints/is_soft）类似
- 命名约定一致

未来如果抽公共库到上层 `libs/`，应该是 zcds 和 mxdzz **共享**的，但现在 zcds 独立 libs/。

## 8. 测试组织

旧 `test_*.py` 散在 zcds/ 根目录，18 个回归脚本。
新位置 `tests/`，import 路径同步更新（`pages.X` → `libs.X` 等）。

回归入口：
```bash
pytest tests/                    # 跑全部
pytest tests/test_battle_loop.py # 单跑
```

## 9. 重构步骤（已完成 TaskList）

1. ✅ 写 ARCHITECTURE.md（本文件）
2. 建 libs/ 骨架 + 搬 game_utils/colorprint/vision
3. Page 基类瘦身 805→200 行
4. 17 个页面迁到 libs 依赖
5. App 依赖注入
6. tools 改成独立 CLI
7. test_*.py 移到 tests/
8. 回归测试 + git commit

每步独立 commit，失败可回滚。