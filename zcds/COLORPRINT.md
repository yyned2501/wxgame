# 点色指纹（colorprint）—— 页面身份判定

本页说明 `C:\projects\wxgame\zcds\colorprint.py` 这一层：怎么靠"点几个像素的颜色"确定当前是
哪个页面。逻辑移植自旧项目 `C:\projects\wxgame\mxdzz`（`libs/app.py` 的颜色对比部分 +
`ctrl.py` 的 `link` 状态机），针对本项目做了若干加强，见 §3。

> **边界**：点色指纹**只负责"这是什么页面"**。页面内该点哪里（`Page.act()`）仍然走 OCR
> 认文字，两者互不干涉，不要把指纹和动作混在一起改。

## 0. 一句话原理

一帧图像属于某页，当且仅当该页的**若干"十字 5 点判色单元"在当前帧全部命中**
（`is_multi_color`：任一点不中即整条不中）。命中即定页，**不需要 OCR**。

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
   `w/552, h/1006` 换算到当前截图尺寸——省一次重采样，也避免插值改色。
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

## 5. 标定流程（新页面 / 改版后重标）

1. **拍图**：把某页的重复截图丢进 `C:\projects\wxgame\zcds\shots\`（同一页面至少 2 张，见 §9）。
2. **登记标签**：在 `C:\projects\wxgame\zcds\tools\pick_print.py` 的 `LABELS`（`:37`）里，把图名
   追加到对应 label 的列表中，写作 `'shots/<文件名>'`（不带 `.png`）。**标注必须人工确认**，
   一张图不能同时属于两个 label。
3. **自检**：`python tools\pick_print.py check` 看标签是否齐全、尺寸是否合规格。
4. **选点**：

   ```
   python -X utf8 tools\pick_print.py pick --label battle
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

## 6. 路由规则（`pages/base.py: route()`）

```
route(pages, f, prefer=()) -> (page, score, src)
```

判定顺序，**命中即返回**：

1. **`prefer` 优先**：`prefer` 是上一页声明的 `next_pages`（对应 mxdzz 的 `Ctrl.link`）。
   只在这些候选页里找全中的指纹 → `src = 'print-prefer'`。
2. **注册顺序兜底**：`prefer` 里没有全中的，再按 `ALL_PAGES` 注册顺序找 → `src = 'print-order'`。
3. **OCR 打分**：指纹一条都没全中，退回 OCR 关键词打分（阈值 0.3）→ `src = 'ocr'`。
4. **`unknown`** → `src = 'unknown'`。

`src` 的四种取值就是这四种来源，日志里会打 `[指纹] <page> <src> <score>`。

- **`match_print()` 一旦某页全中立刻 `return`**，所以"同一帧两页同时全中"由
  **`prefer` + 注册顺序**裁决。当前注册顺序：

  ```
  claim_popup > chest_info > diamond_popup > vip_popup > result > battle > matching > lobby > unknown
  ```

  **弹窗必须排在大厅/战斗之前**：弹窗压住底层页面时，被压页面的框架点仍可能全部命中
  （它的顶栏还在画面外露着），靠顺序才能判成弹窗。
- `src = 'ocr'` 是**"指纹失效"信号**，不是正常路径：偶尔出现是动画遮挡（可接受），
  持续出现说明页面改版了，要重新标定（§9）。
- `test_print_route.py` 的第 [3] 项锁死了"**像素与文字矛盾时听指纹**"：故意造一张
  大厅图但 OCR 读到弹窗文案的用例，必须判成 `lobby`。这条测试不许削弱。

## 7. 当前标定状态（语料 70 张全部在 `C:\projects\wxgame\zcds\shots\`，实测）

| 页面 | 形态数 | 判色点/形态 | 单元/形态 | 语料全中 | 异页误中 | margin | 各形态覆盖帧数 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `lobby` | 3 | 15 | 3 | 21/21 | 0 | 0.13 | 17, 20, 1 |
| `battle` | 3 | 15 | 3 | 13/13 | 0 | 0.20 | 13, 2, 1 |
| `result` | 4 | 15 | 3 | 13/13 | 0 | 0.27 | 3, 3, 7, 1 |
| `chest_info` | 1 | 15 | 3 | 7/7 | 0 | 0.27 | 7 |
| `vip_popup` | 2 | 15 | 3 | 5/5 | 0 | 0.13 | 4, 1 |
| `matching` | 1 | 15 | 3 | 1/1 | 0 | 0.20 | 1 |
| `claim_popup` / `diamond_popup` / `unknown` | — | 无指纹 | — | — | — | — | 只走 OCR，见 §8 |

语料分组：`lobby` 21 / `battle` 13 / `result` 13 / `chest_info` 7 / `vip_popup` 5
（含 1 张 `vip_month`）/ `matching` 1 / `other` 10 = **70**。图名一律对应 `shots\<图名>.png`，各页 `# 形态: …` 注释里列的名字同理。

**margin 怎么读**：margin 是**所有非本页的语料帧上，最高能达到的命中比例**。
`margin x 15` 就是最坏情况下别的页能撞中的点数：

- `0.13` → 异页最高只撞中 **2/15** 点
- `0.20` → **3/15**
- `0.27` → **4/15**

而判定门槛是 **15/15（比例 1.0）**，所以最小余量约 **5 倍**（1.0 vs 0.27）。
每页注释里那行统计就是这几列的来源，用 `C:\projects\wxgame\zcds\tools\print_stats.py` 自动重算
（加 `--dry-run` 只看表不改文件），**别手写**。

`other` 组（`dbg`、`probe_flag0`、`st_0`、`guide_live1/3`、`watch_124711~124758` 共 10 张）
**不被任何指纹命中是正确结果**——它们不是这 6 个页面。其中 `guide_live1/3` 是战斗页上叠的
"指南"弹窗，刻意归 `other`，避免和 `battle` 抢身份。

## 8. 为什么 `claim_popup` / `diamond_popup` 还没有指纹

语料里**没有这两页的独立标注图**（它们只在大厅截图里被部分压住出现过）。用不完整的图硬标，
标出来的点要么落在弹窗外（等于标了大厅的点），要么落在动画上，只会造成误判。
所以这两页暂时只靠 OCR 关键词（`claim_popup` 权重 1.5、`diamond_popup` 1.3，都排在 `lobby` 前）。

**升级它们不需要改代码**：补几张这两页的完整截图 → 在 `LABELS` 登记 → `pick --label claim_popup`
→ 回填 → `verify`。

## 9. 已知风险（别踩）

1. **单帧形态没有跨帧验证**。看 §7 的"各形态覆盖帧数"，凡是出现 `1` 的都是**只用一张图标定的**：
   `matching`（全部）、`lobby` 第 3 形态、`battle` 第 3 形态、`result` 第 4 形态、
   `vip_popup` 的 `vip_month` 形态。这些形态的稳定性是"假设"，不是"测过"。
   补图优先级：`sm_after`、`st_2`。
2. **指纹刻意不覆盖动画区域**（倒计时数字、随机矿块、飘字、奖励动效）。好处是稳，
   代价是**改版换皮会整页失效**，表现为一直接 `src=ocr`。那是**重标定信号，不是 bug**，
   不要靠放宽容差去掩盖。
3. **`degree=85` / `pos_tol=1` 是在"同源重复截图"上调出来的**。真机走 PrintWindow 抓帧
   可能有色彩管理/DWM 合成带来的色差，届时需要放宽（`degree=80` 或 `pos_tol=2`），
   但**放宽之前先跑 `verify -v` 看 margin**，放宽之后必须再跑一次确认 margin 没有逼近 1.0。
4. **弹窗顺序即正确性**。新增任何弹窗页，必须注册在被压页**之前**（见 §6），否则弹窗
   出现时会被底下的 `lobby`/`battle` 抢走身份。
5. 语料里**混入不同皮肤/不同语言**的截图会直接把标定的点选歪，`pick` 前确认同质。

## 10. 排障

| 症状 | 怎么看 | 怎么办 |
| --- | --- | --- |
| 某页 `verify` 不过 | `verify -v` 看命中比例 | 比例 ≈0.93（14/15 之类）= 差点，通常是被动画或弹窗盖住 → 补拍重标；比例 <0.4 = 整页框架变了或坐标错 → 查截图尺寸/长宽比/是否改版 |
| 不知道是哪个点漏了 | `colorprint.missing_points(img, fp, degree, pos_tol)` | 返回这帧里没命中的点，按坐标去图上眼看 |
| 一直接 `src=ocr` | 日志里 `[指纹] <page> <src> <score>` | 说明该页所有形态都没全中 → 按 §9-2 重标定，别去动 OCR 关键词 |
| 两页互相抢 | `verify` 的命中矩阵行 | 把冲突页的指纹错开区域重标（加大 `--min-sep`，或用 `--region` 限定） |
| 想救急放宽 | 单页 `degree = 80` 或 `pos_tol = 2` | 只改那一页的类属性，然后**必须**重跑 `verify`，确认 margin 没接近 1.0 |

## 11. 文件一览

| 路径 | 作用 |
| --- | --- |
| `C:\projects\wxgame\zcds\colorprint.py` | 指纹原语：`tolerance` / `is_color` / `is_multi_color` / `print_score` / `scale_points` / `missing_points` / `find_multi_color` |
| `C:\projects\wxgame\zcds\pages\base.py` | `Page` 基类（`points` / `prints` / `degree` / `pos_tol` / `fingerprints()` / `print_match()`）+ `match_print()` + `route()` |
| `C:\projects\wxgame\zcds\pages\*.py` | 各页面的指纹（本文管的）与 `act()` 动作（OCR，本文不管） |
| `C:\projects\wxgame\zcds\tools\pick_print.py` | 标定工具：`check` / `pick` / `verify` |
| `C:\projects\wxgame\zcds\tools\print_stats.py` | 重算并写回各页指纹的统计注释（`--dry-run` 只看表） |
| `C:\projects\wxgame\zcds\shots\` | 70 张标定语料，`LABELS` 以 `shots/<图名>` 引用 |
| `C:\projects\wxgame\zcds\scratch\` | 一次性逆向脚本与中间产物（**运行时不依赖**，见 `scratch\README.txt`） |
| `C:\projects\wxgame\zcds\test_print_route.py` | 离线回归测试（5 项断言，70 张语料） |
| `C:\projects\wxgame\zcds\auto_bot.py` | 主循环接线处：`route(self.pages, self.f, prefer=self.expected or ())` |

> `tools\pick_print.py` 和 `test_print_route.py` 只依赖 `numpy` + `PIL`，**可以在没装
> pywin32 / rapidocr 的机器上完全离线跑**（本项目所有验证都这么做）。
> 真要跑机器人才需要 `pywin32`（截屏/点击）和 `rapidocr`（`act()` 层认字）。
>
> mxdzz 只作为结构与算法参考，运行时不依赖它，也不要往它的目录里写东西。
