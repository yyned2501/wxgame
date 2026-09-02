# 点色指纹（colorprint）—— 页面身份判定

本页说明 `C:\projects\wxgame\zcds\colorprint.py` 这一层：怎么靠"点几个像素的颜色"确定当前是
哪个页面。逻辑移植自旧项目 `C:\projects\wxgame\mxdzz`（`libs/app.py` 的颜色对比部分 +
`ctrl.py` 的 `link` 状态机），针对本项目做了若干加强，见 §3。

> **边界**：点色指纹**只负责"这是什么页面"**；页面内该点哪里（`Page.act()`）在读得到字时才用 OCR，
> 读不到的（图形按钮、✕ 徽章、价格护栏）用 §12 那四把颜色尺子。两者互不干涉，不要把指纹和动作混在一起改。
>
> **用户定案（2026-09-03）**：OCR 准确率太低而且速度太慢 —— **识别成功之后，脚本里一律用点色**。
> 真机实测：点色判完全表 **2.2 ms/帧**，全图 OCR **675 ms/帧**。所以 OCR 是"点色一点收据都没有"时的
> 最后兜底，不是常规路径；`test_zero_ocr.py` 把这条钉成回归测试。

## 0. 一句话原理

一帧图像属于某页，当且仅当该页的**若干"十字 5 点判色单元"在当前帧全部命中**
（`is_multi_color`：任一点不中即整条不中）。命中即定页，**不需要 OCR**。
全中落空时还有第 2 级"**软命中**"：只差 1 个点（动画遮挡）且甩开第二名足够多，仍算点色定页、
仍不跑 OCR —— 见 §6.1。OCR 只剩"一点像素收据都没有"时的第 3 级兜底。

一页可以有多组指纹（`prints`），代表同一页面的不同形态（按钮亮/暗、有无红点等），
**任一形态全中即算这一页**。

## 1. 为什么把"猜页面"从 OCR 换到点色

之前每一帧都跑一遍 OCR，靠关键词打分选页，有三个反复出现的毛病：

1. **慢且不稳**。OCR 本身几百毫秒一轮，而且识别结果会漂：同一张图上一轮读成
   「点击继续」、下一轮读成「点击维续」，关键词就匹配不上了；`scale=0.5` 缩放还会丢小字。
2. **弹窗压在大厅上时两页关键词同时命中**，只能靠注册顺序硬压，属于碰运气。
3. **文字是最容易变的东西**（活动文案、倒计时、玩家名、数值），而页面框架像素
   （顶栏图标、按钮描边、标题底纹）几乎不变。

所以：**判页看像素，干活看文字**。像素命中就定页，OCR 只在指纹全部落空时兜底。

## 2. 与 mxdzz 的对应关系

| mxdzz | 本项目 | 说明 |
| --- | --- | --- |
| `App.same_color(c0, c1, degree=85)` | `colorprint.tolerance(degree)` | 容差公式照搬：`delta = (256 - 256 * degree // 100) // 2`，`degree=85 → ±19`（实测） |
| `App.is_color(x, y, color, degree)` | `is_color(img, x, y, color, degree, pos_tol)` | 加了 `pos_tol` 邻域漂移，见 §3-⑤ |
| `App.is_multi_color(points, degree)` | `is_multi_color(img, points, degree, pos_tol)` | 语义相同：多点全中，一票否决 |
| `App.find_multi_color_in_region(points, degree, region)` | `find_multi_color(...)` | 模板滑动反查坐标，`pick --no-cross` 用；返回 `[[y, x], ...]`，要 `(x, y)` 用 `find_multi_color_xy` |
| `App.get_points(region, n)` | `tools/pick_print.py pick` | 自动标定指纹（不再是随机采样） |
| `App.c2rgb` / `App.rgb2c` | 同名 | 0xRRGGBB ↔ [r, g, b] |
| `Ctrl.link` + `Ctrl.match()` | `Page.next_pages` + `match_print(pages, img, prefer=)` | `ctrl.py:14` `link = []`，`:103` `self.link = self.page.link`，`:37-39` 遍历 link 调 `is_multi_color(page.points)` |
| 页面类上的 `points` | `Page.points` / `Page.prints` | 后者支持一页多形态 |

## 3. 相对 mxdzz 的六项加强

1. **单点 → 十字 5 点单元**。mxdzz 的 `points` 是散落的单点，一个点撞上纯色背景就命中，
   容易误判。本项目标定单元固定为十字：`OFFSETS = [(0,0), (2,0), (-2,0), (0,2), (0,-2)]`
   （`tools/pick_print.py:35`）。一个单元 = 5 个点，一个指纹 = 3 个单元 = **15 个判色点**。
   想退回 mxdzz 的单点风格：`pick --no-cross`。
2. **随机采样 → 稳定性筛选**。`App.get_points` 是随机取点；这里是先把语料里所有候选点
   跑一遍（`stable_points`），只保留"在本形态的每一帧都命中"的点（`--min-frames 1.0`），
   再贪心地挑"能排除最多数其它页面"的单元（`--min-sep 45` 保证单元分散，不挤在一块同色区域）。
3. **一页一组的 `points` → 一页多组 `prints`**。同页不同形态（`--cluster 4.0` 自动分簇）
   各存一条指纹，任一全中即判为该页。
4. **坐标归一化到基准尺寸**。指纹一律在 `REF_SIZE = (552, 1006)` 下标定（`pick` 阶段
   `im.resize(REF)`）。**匹配时不缩放图像**，而是 `scale_points()` 把坐标按
   `w/552, h/1006` 换算到当前截图尺寸——省一次重采样，也避免插值改色。**但点击坐标不做换算**，见 §4。
5. **`pos_tol` 邻域容差**。mxdzz 只比对该像素的精确位置；本项目在 `(x±pos_tol, y±pos_tol)`
   的方块里任取一像素命中即算命中，用来吸收缩放取整带来的 1 像素偏移。
6. **`print_score()`**。返回 0~1 的命中比例，把"差多少个点"量化出来，标定和排障时能看
   margin（见 §7、§10），不再只能看到"中/不中"。

## 4. 坐标与容差约定（**移植数据前务必读这段**）

- 本项目全库坐标都是 **`(x, y)` = (列, 行)**，在 `REF_SIZE = 552 x 1006` 基准下标定；
  取色是 `arr[y, x]`。
- **⚠ mxdzz 的约定正好相反**：它的 `is_color(x, y, ...)` 内部写的是 `self.capture()[x, y]`
  （`libs/app.py`），numpy 是 `[行, 列]`，所以它 `points[i][0]` 实际是**行号**。
  → **不要把 mxdzz 页面里的 `points` 数值直接搬过来**，那样等于把坐标沿主对角线镜像。
  要移植就重新用 `pick` 标一遍。
- `degree`：**越大越严格**。85 → 每通道 ±19；100 → ±0。`pos_tol`：坐标容差像素，0 = 不允许漂移。
  这两个参数都是 `Page` 的类属性（`degree` / `pos_tol`），**可以按页覆盖**；
  当前全部页面用默认 `degree=85`、`pos_tol=1`。
- 语料图片尺寸可以各不相同，但**长宽比必须和 552x1006 一致**，否则换算后坐标会整体错位。
- **⚠ 只有"判色坐标"会换算，"点击坐标"不会**。`CHEST_SLOTS`、`MASK_POINTS` 和各家 `act()` 里的坐标
  全是 552x1006 下的常量，`App.click()` 只加窗口偏移不缩放。所以**窗口必须钉在 552x1006**：
  `auto_bot.py` 每轮调 `g.set_window_size()` 校正（尺寸已对时只有一次 `GetWindowRect`，开销可忽略），
  不想让它动窗口就加 `--no-resize`（届时指纹层和动作层都可能失效）。

## 5. 标定流程（新页面 / 改版后重标）

1. **拍图**：把某页的重复截图丢进 `C:\projects\wxgame\zcds\shots\`（同一页面至少 2 张，见 §9）。
2. **登记标签**：在 `C:\projects\wxgame\zcds\tools\pick_print.py` 的 `LABELS`（`:37`）里，把图名
   追加到对应 label 的列表中，写作 `'shots/<文件名>'`（不带 `.png`）。**标注必须人工确认**，
   一张图不能同时属于两个 label。
3. **自检**：`python tools\pick_print.py check` 看标签是否齐全、尺寸是否合规格。
4. **选点**（**必须带 `--region 0,130,552,1006`** 把顶栏的账号资源数字排除掉，原因见 §9-6）：

   ```
   python -X utf8 tools\pick_print.py pick --label lobby --region 0,130,552,1006
   ```

   常用参数与默认值：`-n 5`（每形态单元上限）、`--min-cross 3`（至少几个单元）、
   `--step 4`（候选网格步长）、`--margin 8`、`--cluster 4.0`、`--degree 85`、
   `--pos-tol 1`、`--min-sep 45`、`--min-frames 1.0`、`--region x0,y0,x1,y1`、
   `--no-cross`、`--drop-lonely`。
5. **回填**：把 `pick` 打印出来的代码块**原样**贴进 `C:\projects\wxgame\zcds\pages\<label>.py`
   （单形态用 `points = [...]`，多形态用 `prints = (...)`）。**不要手改坐标数值**，
   手改等于作废整个跨帧验证；要调就改参数重跑 `pick`。
6. **验收**（两条都必须 exit 0）：

   ```
   python -X utf8 tools\pick_print.py verify -v
   python -X utf8 test_print_route.py
   ```

> 别名标签：`vip_month` 的形态被并进 `pages\vip_popup.py`（`GROUPS = {'vip_popup': ['vip_popup', 'vip_month']}`，`:61`），**不会新建 `pages\vip_month.py`**。

## 6. 路由规则（`pages/base.py`）

定页面分**三级**，逐级降级；**上一级只要给出结论就绝不花下一级那份 OCR 钱**：

```
route_prints(pages, img, prefer=()) -> (page, score, src)   # 纯点色: 全中 + 软命中, 绝不碰 OCR
detect_ocr(pages, f)                 -> (page, score)       # 第 3 级兜底, 只在上一行返回 None 后调用
```

判定顺序，**命中即返回**：

1. **指纹全中（第 1 级）**：`src = 'print-prefer'` / `'print-order'`
   - `prefer` 是上一页声明的 `next_pages`（对应 mxdzz 的 `Ctrl.link`），先只查这些候选页；
   - 没全中的话再按 `ALL_PAGES` 注册顺序查其余页。
2. **软命中（第 2 级）**：`src = 'print-prefer-soft'` / `'print-order-soft'` —— 见 §6.1。
   点色**没全中但只差 1 个点**，且甩开第二名足够多，仍然算"点色定的页"，**照样不跑 OCR**。
   主循环额外要求**连续 2 帧同一页**才按它动手（`auto_bot.SOFT_ACT_AFTER`），第 1 帧只认页不出手。
3. **全图 OCR 打分（第 3 级）**：`src = 'ocr'` —— 前两级一条收据都没有（新页面/被别的窗口挡住/改版）
   才允许花这份钱，阈值 0.3。**并列最高分时用点色部分命中率拆伙**（`detect_ocr`）：大厅右上角常驻
   "月卡"，和 `vip_popup` 的关键词同样拿 1.0，只按注册顺序会误判成弹窗 —— 真机 2026-09-02 就踩在这上面。
4. **`unknown`** → `src = 'unknown'`。

日志每轮打 `[指纹] <page> <src> <score>`，`<src>` 的取值就是上面这四种来源。

### 6.1 软命中：动画遮住一个点时不许退回 OCR（2026-09-03 落地）

**要修的坑**（真机 01:42 日志）：战斗页满屏都在动，指纹 25 个点里只要有一个被动画遮住就不算"全中"
→ 旧版整轮白退到全图 OCR（675 ms）+ 靠文字猜页。留出集 47 帧真机图上重标后的指纹已经 100% 全中，
但"差 1 点"这种最琐碎的失效在实时画面里必然反复出现，所以补一层软命中，而不是放宽容差。

`pages/base.py` 的三个常量，**三条同时成立**才算软命中（少一条就老实退回第 3 级）：

| 常量 | 值 | 为什么必须有 |
| --- | --- | --- |
| `SOFT_MIN_PTS` | 8 | 否则"1 个点没中"也满足"差 ≤1 点"，`ad_popup`/`claim_popup`/`diamond_popup`/`unknown` 这些**零点数的页**会白捡命中（0/0） |
| `SOFT_MAX_MISS` | 1 | 最多缺 1 个点，按该指纹**自身点数**换算成分数门限（15 点→≥0.933，25 点→≥0.96） |
| `SOFT_MIN_MARGIN` | 0.20 | 必须甩开第二名 0.20 以上 —— 防两张相似页在半途中转帧上互相冒充 |

- 判定函数：`best_print(page, arr)`（最强指纹及其点数）→ `soft_hit(scored)`（挑候选 + 算 margin）
  → `match_print()` 打 `-soft` 后缀 → `is_soft(src)` 给主循环用。
- **参数实验**（`scratch/scripts/soft_tune.py`，222 帧真机+语料）：`exact`（不许软命中）205、
  `m1_02`（差 1 点 + margin 0.20）**205**、`m2_02`（放宽到差 2 点）205 —— 软命中**一个误判都没增加**，
  剩下 17 帧是本来就没指纹的 `other`/`unknown`。所以取最保守的 `SOFT_MAX_MISS=1`。
- **端到端锁死**：`test_print_route.py` 第 [10] 项用假分数钉死 6 条门限，再用真图 + `blotch()` 验证
  "遮 1 点→软命中""遮 2 点→交 OCR"；`test_cpu_offline.py` 场景 [7] 验证主循环"第 1 帧不动作、
  第 2 帧放行、全程零 OCR"；`test_zero_ocr.py` 全语料 + 留出集扫描后断言 OCR 模块压根没被 import。
- **⚠ 造"差 1 点"的用例图时 `blotch` 半径必须是 `r=1`**：指纹是**十字 5 点一组**（中心 + 上下左右 2px），
  涂 7x7 会一次干掉**整个单元**（5 个点），score 直接掉到 0.800 —— 那是"页面真的变了"，不是动画遮挡。

- **`match_print()` 一旦某页全中立刻 `return`**，所以"同一帧两页同时全中"由
  **`prefer` + 注册顺序**裁决。当前注册顺序：

  ```
  ad_popup > claim_popup > chest_info > chest_open > diamond_popup
                 > vip_popup > result > battle > matching > lobby > unknown
  ```

  **弹窗必须排在大厅/战斗之前**：弹窗压住底层页面时，被压页面的框架点仍可能全部命中
  （它的顶栏还在画面外露着），靠顺序才能判成弹窗。
- `src = 'ocr'` 是**"指纹失效"信号**，不是正常路径：偶尔出现是画面剧变（可接受），
  持续出现说明页面改版了，要重新标定（§9）。`src` 带 `-soft` 偶尔出现属正常，**长期**带说明
  指纹标到了动画上，按 §9-2 重标（别靠加大 `SOFT_MAX_MISS` 掩盖）。
- `test_print_route.py` 的第 [3] 项锁死了"**像素与文字矛盾时听指纹**"：故意造一张
  大厅图但 OCR 读到弹窗文案的用例，必须判成 `lobby`。这条测试不许削弱。
  第 [6] 项锁死 §6-3 的同分 tie-break（用缩放过的真机大厅帧复现，含反向用例：只剩弹窗
  文案时不得被抢给大厅）；第 [7] 项是"顶栏闸门"，`lobby` 指纹一旦落回 y<130 直接判失败。

## 7. 当前标定状态（语料 128 张全部在 `C:\projects\wxgame\zcds\shots\`，2026-09-03 实测）

| 页面 | 形态数 | 判色点/形态 | 单元/形态 | 语料全中 | 异页误中 | margin | 各形态覆盖帧数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `lobby` | 3 | 15 | 3 | 33/33 | 0 | 0.20 | 33, 21, 12 |
| `battle` | 2 | 25 | 5 | 40/40 | 0 | 0.12 | 13, 27 |
| `result` | 1 | 25 | 5 | 16/16 | 0 | 0.12 | 16 |
| `chest_info` | 1 | 15 | 3 | 9/9 | 0 | 0.27 | 9 |
| `chest_open` | 1 | 15 | 3 | 6/6 | 0 | 0.40 | 6 |
| `vip_popup` | 2 | 15 | 3 | 8/8 | 0 | 0.13 | 4, 4 |
| `matching` | 1 | 20 | 4 | 2/2 | 0 | 0.35 | 2 |
| `ad_popup` / `claim_popup` / `diamond_popup` / `unknown` | — | 无指纹 | — | — | — | — | 只走 OCR，见 §8 |

语料分组：`battle` 40 / `lobby` 33 / `result` 16 / `other` 14 / `vip_popup` 8（另 `vip_month`
归并进 `vip_popup` 的第二形态）/ `chest_info` 9 / `chest_open` 6 / `matching` 2 = **128**。
图名一律对应 `shots\<图名>.png`，各页 `# 形态: …` 注释里列的名字同理。
带 `_live` 的真机帧由 `tools/pick_print.py` 的自动登记块并入 `LABELS`，不用手改。

**留出集**（2026-09-03）：`shots_live\dbg_*.png` 里**没进过语料**的 47 帧真机图
（battle 19 / lobby 20 / chest_info 5 / chest_open 1 / matching 1 / result 1）
点色**全中 100%、页面判定 100% 正确、零 OCR** —— 见 `test_zero_ocr.py`。
这是"重标定到底修没修好真机失效"的唯一硬证据，`verify` 的绿灯代替不了它。

**margin 怎么读**：margin 是**所有非本页的语料帧上，最高能达到的命中比例**。换算成点数：

- `0.12` → 异页最高只撞中 **3/25** 点（`battle`、`result`，25 点指纹最抗巧合）
- `0.13` → **2/15**（`vip_popup`）
- `0.20` → **3/15**（`lobby`）
- `0.27` → **4/15**（`chest_info`）
- `0.35` → **7/20**（`matching`，只有 2 帧可标，最弱的一组）
- `0.40` → **6/15**（`chest_open`）

而判定门槛是**全中（比例 1.0）**，所以最弱的 `chest_open` 也还有 **2.5 倍**余量，其余 ≥5 倍。
每页注释里那行统计就是这几列的来源，用 `C:\projects\wxgame\zcds\tools\print_stats.py` 自动重算
（加 `--dry-run` 只看表不改文件），**别手写**。

`other` 组（`dbg`、`probe_flag0`、`st_0`、`guide_live1/3`、`watch_124711~124758`、`other_quest_0022`
共 14 张）**不被任何指纹命中是正确结果**——它们不是这几个页面。其中 `guide_live1/3` 是战斗页上叠的
"指南"弹窗，刻意归 `other`，避免和 `battle` 抢身份。

## 8. 为什么 `ad_popup` / `claim_popup` / `diamond_popup` 还没有指纹

语料里**没有这两页的独立标注图**（它们只在大厅截图里被部分压住出现过）。用不完整的图硬标，
标出来的点要么落在弹窗外（等于标了大厅的点），要么落在动画上，只会造成误判。
所以这两页暂时只靠 OCR 关键词（`claim_popup` 权重 1.5、`diamond_popup` 1.3，都排在 `lobby` 前）。

**升级它们不需要改代码**：补几张这两页的完整截图 → 在 `LABELS` 登记 → `pick --label claim_popup`
→ 回填 → `verify`。

## 9. 已知风险（别踩）

1. **单帧形态没有跨帧验证**。看 §7 的"各形态覆盖帧数"，凡是出现 `1` 的都是**只用一张图标定的**：
   `matching`（全部）、`result` 第 4 形态、`vip_popup` 的 `vip_month` 形态。这些形态的稳定性是"假设"，
   不是"测过"。补图优先级：`sm_after`、`st_2`。
   （`lobby` 原先的"第 3 形态 1 帧"已随 2026-09-02 重标消失，见 §9-6。）
2. **指纹刻意不覆盖动画区域**（倒计时数字、随机矿块、飘字、奖励动效）。好处是稳，
   代价是**改版换皮会整页失效**，表现为一直接 `src=ocr`。那是**重标定信号，不是 bug**，
   不要靠放宽容差去掩盖。
3. **`degree=85` / `pos_tol=1` 是在"同源重复截图"上调出来的**。真机走 PrintWindow 抓帧
   可能有色彩管理/DWM 合成带来的色差，届时需要放宽（`degree=80` 或 `pos_tol=2`），
   但**放宽之前先跑 `verify -v` 看 margin**，放宽之后必须再跑一次确认 margin 没有逼近 1.0。
4. **弹窗顺序即正确性**。新增任何弹窗页，必须注册在被压页**之前**（见 §6），否则弹窗
   出现时会被底下的 `lobby`/`battle` 抢走身份。
5. 语料里**混入不同皮肤/不同语言**的截图会直接把标定的点选歪，`pick` 前确认同质。
6. **⚠ 顶栏（y<130）是账号资源数字，不能当指纹依据**。2026-09-02 真机实测：旧 `lobby` 指纹 15 个点
   **全部**落在金币/钻石/兵力数字上，而语料 21 张恰好数值相同 -> `verify` 的 21/21 是**假绿灯**；
   换到真机只剩 11/15（固定缺 4 点，连采 8 帧一模一样），整页路由退化成 `src=ocr`，机器人 20 轮零命中。
   `lobby` 已用 `--region 0,130,552,1006` 重标（25/25 全中 / 异页误中 0 / margin 0.20，覆盖 [25, 19, 4]），
   并由 `test_print_route.py` 第 [7] 项钉死"lobby 指纹不得进 y<130"。
   - **`battle` 已同样解决**（2026-09-03）：旧指纹 15 个点全在 y58~114，语料 13 帧数值恰好相同 ->
     `verify` 的 13/13 也是**假绿灯**。真机补拍 6 帧（`shots/battle_live_004258~004314`）后实测
     旧指纹在真机帧上只中 10/15，日志长期是 `battle ocr 0.90`。用
     `pick --label battle --region 0,130,552,1006 --cluster 40` 重标成 2 形态
     （19/19 全中 / 异页误中 0 / margin 0.27 / 覆盖 13, 6），最小 y=172 已离开顶栏。
7. **弹窗有入场动画，指纹不能标在动画区**（2026-09-03 实测）。`vip_month` 旧形态在补拍的新帧上只中
   5/15，因为标定的点落在弹窗的滑入/发光动画上。改标**静止的文字行**（y538）后 2/2 全中。
   同理 `chest_info` 旧指纹是在「木箱」面板上标的，真机换成铁制宝箱只剩 9/15 —— 面板类页面的
   指纹要标在**与内容无关的框架**（标题行 / 固定的分类行）上。
8. **图形按钮 OCR 读不到，只能按颜色找**（见 §12）。这不算指纹风险，但要知道：定页可以靠像素，
   **动作坐标同样可以靠像素**，不必事事依赖 OCR 认字。

## 10. 排障

| 症状 | 怎么看 | 怎么办 |
| --- | --- | --- |
| 某页 `verify` 不过 | `verify -v` 看命中比例 | 比例 ≈0.93（14/15 之类）= 差点，通常是被动画或弹窗盖住 → 补拍重标；比例 <0.4 = 整页框架变了或坐标错 → 查截图尺寸/长宽比/是否改版 |
| 日志一直 `print-*-soft` | `missing_points(img, fp)` 点名是哪几个点 | 偶尔一次正常（动画遮挡，见 §6.1）；**同一页长期 soft** = 指纹标到了动画上 → 重标，别去加大 `SOFT_MAX_MISS` |
| 不知道是哪个点漏了 | `colorprint.missing_points(img, fp, degree, pos_tol)` | 返回这帧里没命中的点，按坐标去图上眼看 |
| 一直接 `src=ocr` | 日志里 `[指纹] <page> <src> <score>` | 说明该页所有形态都没全中 → 按 §9-2 重标定，别去动 OCR 关键词 |
| 两页互相抢 | `verify` 的命中矩阵行 | 把冲突页的指纹错开区域重标（加大 `--min-sep`，或用 `--region` 限定） |
| 想救急放宽 | 单页 `degree = 80` 或 `pos_tol = 2` | 只改那一页的类属性，然后**必须**重跑 `verify`，确认 margin 没接近 1.0 |
| 换账号 / 资源一变就整页认不出 | `test_print_route.py` 第 [7] 项会点名指纹落在顶栏的页 | 指纹落在顶栏资源数字上 → 用 `--region 0,130,552,1006` 重标（见 §9-6） |

## 11. 文件一览

| 路径 | 作用 |
| --- | --- |
| `C:\projects\wxgame\zcds\colorprint.py` | 指纹原语：`tolerance` / `is_color` / `is_multi_color` / `print_score` / `scale_points` / `missing_points` / `find_multi_color` |
| `C:\projects\wxgame\zcds\pages\base.py` | `Page` 基类（`points` / `prints` / `degree` / `pos_tol` / `fingerprints()` / `print_match()`）+ `best_print()` / `soft_hit()` / `match_print()` / `route_prints()` / `is_soft()` / `detect_ocr()` |
| `C:\projects\wxgame\zcds\pages\*.py` | 各页面的指纹（本文管的）与 `act()` 动作（OCR，本文不管） |
| `C:\projects\wxgame\zcds\tools\pick_print.py` | 标定工具：`check` / `pick` / `verify` |
| `C:\projects\wxgame\zcds\tools\print_stats.py` | 重算并写回各页指纹的统计注释（`--dry-run` 只看表） |
| `C:\projects\wxgame\zcds\shots\` | 128 张标定语料（552x1006，含 2026-09-02/03 真机帧），`LABELS` 以 `shots/<图名>` 引用 |
| `C:\projects\wxgame\zcds\shots_live\` | 真机取证帧：`peek_*` = 只读探针，`dbg_*` = 主循环 `--shots N`，`probe_*` = 定点探针（**不入库**） |
| `C:\projects\wxgame\zcds\scratch\` | 一次性逆向脚本与中间产物（**运行时不依赖**，见 `scratch\README.txt`）；`live_probe2.py` / `scale_experiment.py` / `live_stability.py` / `live_collect.py` 是真机取证脚本 |
| `C:\projects\wxgame\zcds\scratch\scripts\test_chest_paid.py` | 真机帧离线回放：主循环同款 ROI(0.10~0.90) + scale 0.5 跑 11 帧，免费帧必点、付费帧必拒 |
| `C:\projects\wxgame\zcds\test_print_route.py` | 离线回归测试（10 项，128 张语料；[10] = §6.1 软命中门限） |
| `C:\projects\wxgame\zcds\test_zero_ocr.py` | **「定页面零 OCR」回归**：128 语料 + 47 真机留出帧必须全被点色定页，扫完断言 OCR 模块没被 import |
| `C:\projects\wxgame\zcds\test_cpu_offline.py` | 主循环离线集成（7 个场景，20 帧只花 4 次 OCR，场景 [7] = 软命中稳帧放行） |
| `C:\projects\wxgame\zcds\test_battle_loop.py` | 战斗循环回归：进场帧清空 `clicked_cells` 并当场出手，整轮零 OCR |
| `C:\projects\wxgame\zcds\test_price_guard.py` | 价格护栏回归（21 项，合成文本框 + 合成图像，不依赖 OCR） |
| `C:\projects\wxgame\zcds\auto_bot.py` | 主循环接线处：`route_prints(self.pages, img, prefer=self.expected or ())`，返回 `None` 才 `vision.ocr(force=True)` |

> `tools\pick_print.py` 和 `test_print_route.py` 只依赖 `numpy` + `PIL`，**可以在没装
> pywin32 / rapidocr 的机器上完全离线跑**（本项目所有验证都这么做）。
> 真要跑机器人才需要 `pywin32`（截屏/点击）和 `rapidocr`（`act()` 层认字）。
>
> mxdzz 只作为结构与算法参考，运行时不依赖它，也不要往它的目录里写东西。

## 12. 除页面指纹外的四把「颜色尺子」

指纹管的是「这一帧是哪一页」。真机跑起来后发现还有四件事**必须**用像素判据、OCR 干不了：

| 判据 | 位置 | 干什么 | 标定值（实测） |
| --- | --- | --- | --- |
| `find_close_badge(img)` | `pages/base.py` | 找弹窗右上角那个**红底白叉 ✕**，返回点击坐标 | 红 mask `(r>185)&(g<105)&(b<105)&(r-max(g,b)>90)`；12px 网格 + BFS 连通域；红像素 550~950（实测 716~818）、外接框 30~60（实测 36~48）、框内白像素 ≥60（实测 142~163）；多候选取**最靠右**；106 帧 0 误报，单帧 15~20ms |
| `is_back_arrow(img)` | `pages/base.py` | 认左下角那个**青色返回箭头**，用于从没有指纹的侧页（任务/商店）逃回大厅 | 框 `(38,950,90,992)` 内 `(b>170)&(g<140)&(r<150)` 像素数 150~1000；实测任务页 463 / 大厅·结算·宝箱面板 0 / 战场页 1860（超上限，且战场是已知页）；点击点 `(63,970)` |
| `PRICE_RE` | `pages/chest_info.py` | **不是找按钮，是拒绝按钮**：邻域出现价格文字就拒点 | `[￥¥] ?\d` / `\d+ ?元` / 钻石 / 宝石 / 充值；邻域 ±70/±60px |
| `PRICE_BARE_RE` + `gem_cost_pixels(img,cx,cy)` | `pages/chest_info.py` | 认"花钱立即开箱"：把按钮**下方**的纯数字当价格，再数按钮正下方窄带里的**紫宝石像素**，任一命中就拒点 | 裸数字 `^\d{1,4}$`（只在按钮下方 `0<=dy<=60`、±70px 内生效）；宝石带 `(-45,12,45,45)` 相对按钮中心；mask `(r>170)&(g<130)&(b>150)`；阈值 **60**；实测免费 9 帧 **0** / 付费帧 **362** |

### 为什么这四条不走 OCR

- **✕ 是图形不是文字**：月卡/VIP 弹窗的关闭键是一个红色圆形徽章，OCR 读不出来。旧代码找不到
  `X`/`关闭` 关键字就退回点遮罩，而遮罩点是固定的 `(270,860)` —— dry-run 8 轮全在重复同一个无效点击，
  弹窗关不掉，挂机原地卡死。改成按颜色找徽章后真机实测：`(455,461)` 一击关闭 → 下一轮 `lobby` 1.00。
  命中点复核：`chest_info` 面板算出 `(468,165)`，和手工标定的 `CLOSE_POS=(470,167)` 只差 2px。
- **侧页根本没有指纹**：任务/商店这类页面没进 `ALL_PAGES`，`route()` 只能给 `unknown 0.00`，
  而 `unknown.act()` 只会瞎点遮罩 → 玩家手动点进任务页，机器人就永久卡在那。
  左下角返回箭头是这类页共同的、纯图形的出口，用颜色认它比给每个侧页标指纹便宜得多。
- **价格判据分两层，颜色只在窄带里可用**：顶栏那颗紫宝石图标主色约 `(222,62,246)`，看着很好认，但全语料
  89 帧里 **77 帧**都有同色系紫 UI（面板底纹、按钮描边、奖励光效），**整帧**按颜色判价会误伤到不能点，
  所以 `PRICE_RE` 先认**文字**（￥/元/钻石/宝石/充值）。真机翻车那次（`README.md` 六类问题第 6 条）
  付费按钮下方只有裸数字 `30`、不带单位，文字判据一条都不命中 —— 于是补 `PRICE_BARE_RE`（按钮下方的
  纯数字 = 价格）和 `gem_cost_pixels()`：**按钮正下方 33px 的窄带**里没有别的紫源，免费 9 帧恒 0、
  付费帧 362，这个尺度上颜色是干净的。两条判据由 `test_price_guard.py` 的 21 个用例锁死。

> 这四把尺子都是 numpy 级别的像素判据（15~20ms），比再跑一次 OCR 便宜，也不受缩放影响。
> 新增同类判据时请像 `find_close_badge` 一样：**先把阈值和实测分布写进注释**，再跑一遍全语料确认 0 误报。
## 13. 动作层也改成点色：`result` / `chest_open` / `lobby` 全轮零 OCR（2026-09-03 落地）

§12 那四把尺子是「点色做判据的特例」，这一节是**整页动作层都不再读字**。
页面把 `Page.act_needs_ocr = False` 之后，`App.step()` 给这些页只塞 `ScreenFeature(img=img, boxes=[], joined="")`：
`act()` 里**只能**用 `ctx.f.img` 数像素，真去调 `ctx.f.find()` 不会报错，只会静默拿到空结果。

| 页 / 判据 | 探针框 | 颜色·阈值（degree90 = 每通道 ±13） | 实测落点 |
| --- | --- | --- | --- |
| `result` 继续按钮 | `CONTINUE_BOX=(150,780,420,970)` | `0xCC56FF` ≥ **800** px，取**外接框中心** | 有礼包横幅 2968px → (275,830)；无横幅 2981px → (275,912)；真机 2848px → (275,910) |
| `chest_open` 底部主按钮 | `BOT_BOX=(150,880,410,960)` | 白 `0xFFFFFF` ≥ **600** px | 6 帧恒 (275,917) —— 「领取奖励」「点击关闭」两种文案的按钮中心完全重合，一次取色通吃 |
| `chest_open` 左上跳过 | `SKIP_BOX=(20,120,160,175)` | 白 ≥ **300** px | (82,142)；只在按钮未出（动画期）存在 → 节流键 `chest_open_claim`，消失后是 `chest_open_close` |
| `lobby` 玩家对战 | `PVP_BOX=(60,640,290,720)` | 金 `0xFDCA33` ≥ **3000** px | 33 帧恒 (180,675)（实测 n=6405~6539） |
| `lobby` 宝箱槽 ×4 | 按钮框 `cx±45, y838..882`；左半 `(cx-34,846,cx-14,874)` | 金 ≥**500** 判「有按钮」；左半金 ≥**250** 判 [开启]；白 ≥**120** 判 [点击解锁] | 四态码 `o`/`a`/`u`/`.`，点 `o`/`u` 中最左一格 |

要点（全是踩过的坑）：

- **绝对像素框合法的前提**是 `ensure_window_size()` 把窗口钉死在 `REF_SIZE=(552,1006)`；用 `--no-resize` 时这些框全部作废。
- **`result` 只在「整屏唯一一个亮紫块」时可信**：`watch_124707` 是激励视频盖在结算页上的帧，扫描 n=0 → 本帧**不动作**。
  旧版在这里靠 OCR 找「点击继续」，读到遮罩上的广告文案就瞎点一次。背景紫是 `0x621FAD`（差 >100/通道），degree90 下与按钮完全分开。
- **宝箱四槽靠「金色被挡住了多少」分家**：[开启] 整块纯金（框内 1235~1241，左半 380~400）；
  [[AD]加速] 金按钮左边贴了张蓝票券图标（框内 789~818，左半只剩 123~133）；[点击解锁] 是深色底白字（框内金 0，白 143~176）；空槽全 0。
  票券色 `AAE4FF`/`6FC2F2`/`223F6B` 与金色不搭，所以只数金色就能把 [开启] 和 [[AD]] 分开。
  这组区间来自 33 帧 × 4 槽 = **132 个观测**，逐帧与 OCR 真值人工核对过；
  复核脚本 `scratch/scripts/slot_truth2.py`（输出 `scratch/o_truth2.txt`），**改阈值后重跑它即回归**。
- **[[AD]加速]那一格一律不点**（`config.WATCH_ADS=False`），点下去 = 看激励视频加速；可点集只有 `o`/`u`。
- **[点击解锁]的白阈值取 120 是留了边际的**：[开启]/[[AD]] 按钮自带的白描边只有 70~100，不会串判。
- **按钮行 y 必须掐在 838..882**：上面 y810..826 是卡片标题带（宝箱名 + 计时角标），角标颜色随档位变，罩进来就成了假指纹。
- 结算页「领取礼包」那条分支仍然读字，但被 `if WATCH_ADS:` 短路在最前面 —— 默认配置下 result 一整轮一次 OCR 都不跑。

**回归锁**：

- `test_act_zero_ocr.py`：断言三页 `act_needs_ocr is False`（打印「动作层仍需读文字的页: ad_popup claim_popup chest_info」）、
  result 16 帧 / chest_open 6 帧 / lobby 15 帧的**逐帧落点表**、33 帧大厅「每帧恰好一次点击且落点 ∈ 4 槽 ∪ 玩家对战、`a` 格绝不被点」、
  以及 `WATCH_ADS=True` 时才允许惰性调 `need_text()`。桩里把 `ScreenFeature.find/find_boxes/has/near` 与 `ctx.need_text()` 全部改成抛异常 ——
  动作层只要伸手动 OCR 就当场炸。
- `test_cpu_offline.py` 场景 1/3/5/7 断言大厅·战斗·结算·软命中帧 `ocr=False`；现在 21 帧总共只跑 2 次 OCR，且两次都在 `chest_info`。

> 结论：**大厅 + 战斗 + 结算 + 开箱动画四类页已经全程零 OCR**，全项目只剩 `chest_info`（价格护栏，按设计保留）、
> `ad_popup`、`claim_popup` 三条 OCR 路径。耗时对比：点色全表 2.2ms / 大厅 ROI OCR 369ms / 全图 OCR 675ms。
