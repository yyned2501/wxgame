# 占城大师（zcds）—— 后台自动挂机 v3.1

游戏窗口标题含「占城大师」，进程是 `WeChatAppEx.exe`（微信小游戏容器）。
路线：**不走 API**（mini-data 加密层没破，逆向结论见 `AUTOMATION_REPORT.md`；该报告属逆向资料，不入库），
改成「抓窗口截图 -> 点色指纹定页面 -> OCR 决定动作 -> PostMessage 点击」，后台跑，不抢前台。

## 跑起来

```
cd C:\projects\wxgame\zcds
python -m pip install -r requirements.txt   # 首次装依赖(版本已实测锁定)
python auto_bot.py                          # 需要游戏窗口已经打开
```

前置条件：游戏窗口已经打开。找不到窗口时 `auto_bot.py` 会抛
`RuntimeError: 找不到游戏窗口, 请先打开 占城大师`。

> 机器人启动后每轮都会把窗口外框钉成 **552x1006**（点色指纹和点击坐标的标定基准），
> 最大化会先还原再改尺寸；不想动窗口加 `--no-resize`。

| 开关 | 作用 |
|---|---|
| `--dry-run` | 只打印行为不真点；配 `--max-steps 8` 就是"真机只读冒烟"，先看路由对不对再放它点 |
| `--max-steps N` | 跑满 N 轮退出（回归/取证用），0 = 不限 |
| `--shots N` | **取证：每轮把当前帧存成 `shots_live/dbg_<轮>_<页>_<时分秒>.png`**。要查"这一下点在哪""按钮上有没有价格"就靠它，不改动任何行为 |
| `--max-battles N` | 打满 N 场退出 |
| `--no-resize` | 不钉窗口尺寸（指纹会整片失效，一般别关） |
| `--no-low-cpu` / `--affinity N` | CPU 降载开关（把微信进程设低优先级 / 限核） |

## 离线验证（不用开游戏，只读 `shots/` 里已导出的 128 张截图）

> **`shots/` 语料不入 git**（128 张 / 50.6 MB，截图顶部带账号昵称）。
> 所以 clone 之后本节命令会因为找不到语料而报错：需要在游戏里自己采集截图，
> 在 `tools/pick_print.py` 的 `LABELS` 里登记后 `pick --label` 采指纹。定页逻辑本身不受影响。

```
python -X utf8 test_print_route.py            # 10 项断言 / 128 张语料：路由回归([10]=软命中门限)
python -X utf8 test_zero_ocr.py               # 定页面零 OCR: 128 语料+47 真机留出帧全要点色定页, 且 OCR 模块没被 import
python -X utf8 test_price_guard.py            # 21 项：绝不替玩家点付费按钮(文字/裸数字/宝石像素, 不依赖 OCR)
python -X utf8 tools\pick_print.py check      # 语料与 LABELS 是否对得上
python -X utf8 tools\pick_print.py verify     # 点色指纹逐张判定，应 128/128 通过（14 张 other 无指纹，按设计交 OCR）
python -X utf8 tools\print_stats.py --dry-run # 重算各页指纹统计，应与注释逐字一致
python -X utf8 test_cpu_offline.py            # 主循环离线集成 7 场景（需要 rapidocr）：21 帧只花 2 次 OCR（都在 chest_info 护栏）
python -X utf8 test_act_zero_ocr.py           # 动作层零 OCR：result/chest_open/lobby 逐帧落点表，一调 OCR 当场炸
python -X utf8 test_battle_loop.py            # 连打 3 场：进战斗页必须清空已点格子
```

## 当前进度（2026-09-03 晚复验：离线 6 个测试全绿 + 定页面零 OCR + 大厅/战斗/结算/开箱动作层也零 OCR）

| 层 | 状态 | 证据 |
|---|---|---|
| 抓窗 + 后台点击 | 通 | `game_utils.py` 纯 ctypes（PrintWindow / PostMessage），不需要 pywin32；真机 31 ms/帧 |
| 点色指纹定页面 | 7/11 页 | `pick_print.py verify` 通过 128 / 不通过 0（14 张 `other` 无指纹，按设计交 OCR）；`test_print_route.py` 10 项断言全过 |
| 页面动作 `act()` | 11/11 页都有 | 但 `ad_popup` / `claim_popup` / `diamond_popup` 只有 OCR 关键词（没语料标不了） |
| 动作层点色（零 OCR） | 4 页已切换 | `lobby` / `result` / `chest_open`（+ 本来就是纯点色的 `battle`）整轮不跑 OCR；`test_act_zero_ocr.py` 逐帧落点锁死，判据表见 `COLORPRINT.md` §13 |
| 战斗自动化 | 通 | `test_battle_loop.py` 连跑 3 场、战斗循环 8 次 OCR 次数 = 0（全颜色扫描） |
| 主循环 | 通 | `test_cpu_offline.py` 7 个场景；进 battle 会清 `clicked_cells`；软命中要连续 2 帧同页才动手 |
| 窗口尺寸对齐 | 通 | `--no-resize` 可关；尺寸不对时指纹层整片失效（实测 431x788 只剩 23/60） |
| 不花钱护栏 | 通 | `test_price_guard.py` 21 项；三道判据（价格文字 / 按钮下方裸数字 / 带内紫宝石像素），真机付费帧离线回放必拒（`scratch\scripts\test_chest_paid.py` 11/11） |

### 2026-09-03（晚）动作层也改成点色：大厅 / 结算 / 开箱**整轮零 OCR**

用户诉求原话：「识别成功以后记得在脚本中用点色来识别，OCR 准确率太低而且速度太慢」。
点色指纹定页面早已 100% 命中（128 张语料 + 47 张真机留出帧），但**定完页之后 `act()` 里还在读字**：
大厅每帧一次 ROI OCR 369ms，结算 / 开箱每帧一次全图 OCR 675ms。这一轮把三页的动作层也换成数颜色 ——
判据、阈值、实测区间全部写进 `COLORPRINT.md` §13。

- `result`：结算页整屏只有**一个**亮紫色块 `0xCC56FF`，取它外接框中心就是 [继续] 落点。
  顺带修掉一个老 bug：激励视频盖脸那帧（`watch_124707`）OCR 会把广告文案读成按钮然后瞎点一次，现在 n=0 -> 本帧不动作。
- `chest_open`：底部按钮文字是全屏唯一白色大块，[点击领取奖励] 与 [点击关闭] 的中心**完全重合**，一次取色通吃；
  左上 [跳过] 白块只在动画期存在，拿它当状态位，旧版第三个 OCR 分支（找「跳过」二字）一并删掉。
- `lobby`：四张宝箱卡片的按钮**颜色构成**不同（[开启] 纯金 / [[AD]加速] 金按钮旁贴蓝票券 / [点击解锁] 深底白字 / 空槽没按钮），
  数「金色被挡住多少」就能分四态，只点 `o`/`u`，[[AD]] 一律不点；[玩家对战] 改成认那块金色按钮 ——
  旧版靠 OCR 读「玩家对战」，**33 帧语料里一次都没读出来过**，等于这个按钮机器人从来没点着。
- 三页都声明 `act_needs_ocr = False` => 主循环**干脆不为它们跑 OCR**（`ctx.f` 只剩图，`act()` 只准用 `ctx.f.img`）。
- 新增 `test_act_zero_ocr.py`：桩里把 `ScreenFeature.find/find_boxes/has/near` 和 `ctx.need_text()` 全改成抛异常，
  动作层只要伸手动文字就当场炸；同时断言 result 16 帧 / chest_open 6 帧 / lobby 15 帧的**逐帧落点表**。
- `test_cpu_offline.py` 跟着改成「大厅·战斗·结算·开箱全程 `ocr=False`」：现在 **21 帧只跑 2 次 OCR**（旧版每帧一次 = 21 次），
  两次都留在 `chest_info` 的价格护栏上。

速度：点色判据整张表 2.2ms，比一次大厅 ROI OCR 快约 **167 倍**，而且不会像 OCR 那样把「继续」读成「维续」。

### 2026-09-03（下午）定页面彻底改成「点色优先」

用户定案：**OCR 准确率太低而且速度太慢 —— 识别成功以后，脚本里一律用点色**。实测差距：
点色判完全表 **1.2~2.2 ms/帧**，全图 OCR **675 ms/帧**（约 300~500 倍）。三条改动：

1. **留出集审计**（`scratch/scripts/audit_holdout.py`）：只拿**没参与标定**的 47 帧真机图测。
   结果 battle 19 / lobby 20 / chest_info 5 / chest_open 1 / matching 1 / result 1
   **点色全中 100%、页面判定 100% 正确、零 OCR** —— 上一轮重标定确实修好了真机失效，
   而不是只在语料上自证（这条很重要：以前两次"假绿灯"都是 `verify` 过了真机废）。
2. **软命中层**（`pages/base.py`，详见 `COLORPRINT.md` §6.1）：真机战斗页满屏都在动，
   指纹 25 点里被动画遮住 1 点就会"不全中" -> 旧版整轮白退到全图 OCR + 文字猜页。
   现在「差 ≤1 点、参评指纹 ≥8 点、甩开第二名 ≥0.20」算**软命中，依然不跑 OCR**；
   主循环再要求**连续 2 帧同一页**才按它动手（头一帧只认页不出手）。
   参数实验（`scratch/scripts/soft_tune.py`，222 帧）：`exact` 205 / 差1点 205 / 差2点 205 ——
   软命中一个误判都没多，所以取最保守的「差 1 点」。
3. **零 OCR 回归**（`test_zero_ocr.py`）：128 语料 + 47 留出帧逐张走 `route_prints()`，
   有指纹的页必须 100% 点色定页、无指纹的帧必须**不被乱认**，扫完断言
   `rapidocr` / `paddle` / `vision` 至今没进 `sys.modules`。平均 1.2 ms/帧。

### 2026-09-03 真机实测后修的六类问题（用户在场实测，日志 `bot.log`）

1. **弹窗关闭键是图形，OCR 读不到** -> 新增 `pages/base.py: find_close_badge()`，按颜色找"红底白叉"徽章：
   红 mask `(r>185)&(g<105)&(b<105)&(r-max(g,b)>90)` + 12px 网格 BFS 连通域，红像素 550~950、
   外接框 30~60、框内白像素 >=60，多候选取**最靠右**。106 帧 0 误报，单帧 15~20ms。
   旧逻辑找不到 `X` 就点遮罩，每轮点同一个 `(270,860)`，月卡弹窗 8 轮关不掉（dry-run 复现）。
   接入 `vip_popup` / `chest_info` / `diamond_popup` 三处；实测命中 `(455,461)`/`(468,165)`/`(465,235)`。
2. **侧页（任务/商店）没有指纹 -> 挂机永久卡死** -> `unknown.act()` 加第 0 级逃逸：
   `is_back_arrow()` 量左下角 `(38,950,90,992)` 内青色像素 `(b>170)&(g>140)&(r<150)`，区间 150~1000，
   命中就点 `BACK_ARROW_POS=(63,970)` 返回。实测任务页 463 / 大厅·结算·宝箱面板 0 / 战场页 1860（超上限）。
3. **价格护栏**（`pages/chest_info.py: PRICE_RE`）：月卡弹窗的 `￥68` 在 `(278,788)`，
   和免费开箱按钮 `(278,785)` 只差 3px —— 弹窗一旦被误判成 `chest_info`，旧代码就替玩家花钱。
   现在按钮自身或邻域（±70/±60px）出现 `[￥¥]\d` / `\d+元` / 钻石 / 宝石 / 充值 就拒点改关面板。
   注：**整帧**的紫宝石颜色不能判价（实测色 `(222,62,246)` 在 77/89 帧里都出现，纯 UI 紫），
   但**按钮正下方 33px 窄带**干净：免费 9 帧带内紫点恒 0 / 付费帧 362 —— 所以第 6 条才敢加颜色判据。
4. **弹窗有动画，指纹不能标在动画区**：`vip_month` 旧指纹组在新帧只中 5/15，改标文字行 y538 后 2/2；
   `chest_info` 旧指纹是在"木箱"面板上标的，真机铁箱只中 9/15 -> `pick --label chest_info
   --region 20,130,530,1000 --cluster 40` 重标成单组 8/8（点位落在标题行 y166 + 普稀史传行 y454）。
5. **`battle` 旧指纹 15 个点也全在顶栏 y58~114**（和上面 `lobby` 同一个坑），语料 13 张数值相同 ->
   `verify` 的 13/13 是假绿灯：真机 6 帧实测只中 10/15，日志一直是 `battle ocr 0.90`。补拍
   `shots/battle_live_004258~004314` 6 帧后 `pick --label battle --region 0,130,552,1006 --cluster 40`
   重标成 2 形态（19/19 全中 / 异页误中 0 / margin 0.27 / 覆盖 13+6），最小 y=172 已离开顶栏。
6. **⚠ 机器人真的花掉过 30 紫宝石**（00:57 那轮，顶栏 `246/114/1037` -> `251/84/1042`）：宝箱
   **解锁后计时中**再点同一格，面板按钮变成 `开启` + "紫宝石图标 + 30"，OCR 只读得到裸数字 `30`
   （没有单位）-> 第 3 条的 `PRICE_RE` 一条都不命中，被当成免费按钮点了。上一轮"紫宝石 -29 是玩家
   手动"**结论作废**：那 -29 = 花 30 宝石开箱 + 到账 1 宝石，是同一个坑。现在补两道判据：
   `PRICE_BARE_RE`（按钮**下方**的纯数字 = 价格）+ `gem_cost_pixels()`（按钮正下方窄带内紫宝石像素
   >= 60）。真机付费帧离线回放已拒点（`scratch\scripts\test_chest_paid.py` 11/11），
   `test_price_guard.py` 扩到 21 项锁死。01:07 复跑：顶栏 `251/84/1042` -> `256/84/1047`，紫宝石 84 未动。

另外实测确认（省得再走弯路）：
- **大厅里宝箱转好后直接点格子 = 跳过信息面板直接开箱**（`lobby -> chest_open`），只有"点击解锁"态才会进 `chest_info`。
- **解锁（免费启动倒计时）和开箱本身都不消耗顶栏资源**：00:42 那轮全程顶栏 `246/114/1037` 一字未变；开箱到账 +5/+5；01:07 复核同样只有 +5/+5。**唯一会花钱的是"计时中的格子被点成开启"，见第 6 条**。
- 战斗页顶栏那行 `Diamond` 是**对手的玩家昵称**（红方），不是货币，别拿它做判据。

### 2026-09-02 真机实测后修的三处（用户在场实测）

1. **`lobby` 指纹重标定**：旧指纹 15 个点全落在顶栏金币/钻石数字上，语料 21 张恰好数值相同 ->
   `verify` 70/70 是假绿灯，真机只剩 11/15、20 轮路由零命中。改用
   `pick --label lobby --region 0,130,552,1006` 重标（25/25 全中 / 异页误中 0 / margin 0.20），
   并把 4 张真机帧（`shots/live_20260902_a~d`）补进语料（70 -> 74）。
2. **窗口尺寸对齐**（`game_utils.set_window_size()` + `App.ensure_window_size()`）：真机原窗口 431x788
   下指纹只剩 23/60，钉回 552x1006 才 60/60。点击坐标不参与缩放换算，所以必须钉尺寸。
3. **OCR 同分 tie-break**（`pages/base.py: detect_ocr`）：大厅常驻"月卡"和 `vip_popup` 关键词同分 1.0，
   按注册顺序会误判成弹窗；现在并列时用点色部分命中率拆伙（缩放帧实测 lobby 0.80~0.93 / vip 0.00）。

### 2026-08-31 修掉的真 bug

`ctx.clicked_cells` 只在 `auto_bot.py __init__` 建过一次，全项目没有一处清空，
而 `pages/battle.py` 用 `if (cx//16, cy//16) in ctx.clicked_cells: return False` 跳点过的格子；
格子 key 是固定窗口坐标、每场复用 -> 打第 2 场起整张棋盘被永久拉黑，战斗页不再动手。
现在进入 battle 页时 `clicked_cells.clear()` + `last_cell = 0`。
`test_battle_loop.py` 是这套行为的回归测试：把清空退化掉，它会红 3 项。

### 待办（按优先级）

1. ~~**`lobby` 不要点「计时中」的宝箱槽位**~~  **已于 2026-09-03 改成点色判据**：`chest_states()` 只看按钮行
   （y838..882）有没有金色/白字块，计时中的槽位那一行根本没有按钮 -> 判成 `.` -> 不点；
   残留：`.` 分不清「计时中」和「真空槽」，但两者**都不该点**，行为正确。付费面板的护栏仍留在 `chest_info`。
2. **补 `ad_popup` / `claim_popup` / `diamond_popup` 完整截图并标定指纹**（现在只有 OCR 关键词，
   是**仅剩的三条 OCR 判页**，最该干掉）。领奖页认不出时只能靠 `chest_open` 的点色按钮兜底。
   注：`chest_info` 动作层仍要 ROI OCR 认价格文字，那是**刻意保留的护栏**（见 `COLORPRINT.md` §12），不在此列。
3. **单帧形态没有跨帧验证**：`matching` 全部、`result` 第 4 形态、`vip_popup` 的 `vip_month`
   （详见 `COLORPRINT.md` §9-1），补图优先级 `sm_after` / `st_2`。
4. **`battle` 真机形态只补到 6 帧**（`shots/battle_live_*`）。换对手昵称/换矿型仍可能出现第三形态；
   `test_print_route.py` 第 [7] 项目前只硬卡 `lobby`，`battle` 靠 margin 0.27 自证，继续补帧更稳。
   （原第 1 项"battle 指纹全在顶栏"已于 2026-09-03 重标解决，见上面第 5 条。）

## 文件地图

| 路径 | 作用 |
|---|---|
| `auto_bot.py` | 主循环/接线：抓窗 -> `route()` -> `page.act()`；每轮 `ensure_window_size()` 对齐基准尺寸；含 CPU 降载、`--shots` 取证存帧 |
| `config.py` | 每页 ROI/scale/poll/ocr_gap；并暴露 `ROOT`、`SHOTS_DIR` |
| `game_utils.py` | Win32 抓窗口（PrintWindow，后台可用）、找窗口、PostMessage 点击、`set_window_size()`（把窗口钉回指纹基准 552x1006） |
| `vision.py` | OCR 封装（rapidocr + ROI 缩放），`ocr_config.yaml` 是它的模型配置 |
| `colorprint.py` | 点色指纹原语（移植自 `..\mxdzz\libs\app.py` 的颜色对比部分） |
| `pages/base.py` | `Page` 基类 + `match_print()` / `detect_ocr()` / `route()`，以及 `find_close_badge()` / `is_back_arrow()` / `is_countdown()` 三个按颜色判据 |
| `pages/*.py` | 11 个页面：7 个已标指纹（lobby/battle/result/chest_info/chest_open/vip_popup/matching），4 个只走 OCR 判页（ad_popup/claim_popup/diamond_popup/unknown）；`lobby`/`result`/`chest_open` 声明 `act_needs_ocr = False`，动作层也只数颜色 |
| `pages/unknown.py` | 兜底页：先试青色返回箭头逃逸（侧页卡死用）-> 再试探弹窗遮罩 -> 往 `shots/` 存 `stuck_*.png` |
| `test_*.py` | 离线回归：`test_print_route`(10 项/128 语料) `test_zero_ocr`(定页零 OCR) **`test_act_zero_ocr`(动作层零 OCR + 逐帧落点表)** `test_cpu_offline`(主循环 7 场景) `test_battle_loop`(连打 3 场) `test_price_guard`(21 项不花钱护栏) |
| `battle_scan.py` + `battle_templates.npz` | 战斗回合的颜色扫描（避免整帧 OCR，省 CPU） |
| `shots/` | 128 张标定语料（552x1006，含 2026-09-02/03 真机帧），`tools/pick_print.py` 的 `LABELS` 引用它（**不入库**） |
| `shots_live/` | 真机跑起来的取证帧（`peek_*` 只读探针 / `dbg_*` 主循环 `--shots`），**不入库** |
| `tools/` | `pick_print.py`(check/pick/verify) `print_stats.py` `set_low_cpu.ps1` + 逆向工具（il2cppdumper、wxapkg） |
| `capture/ dec/ game_src/ unity_data/` | 逆向资料：抓包、XYX 解密产物、wasm 解包、Unity 资源（**运行时不依赖，不入库**） |
| `scratch/` | 一次性脚本/中间产物归档，带 `MANIFEST.tsv` + `restore.py`（把归档搬回原位）+ `relocate.py`，**运行时不依赖** |
| `COLORPRINT.md` | 点色指纹那层的完整说明：怎么标定、怎么加新页、和 mxdzz 的差异 |
| `AUTOMATION_REPORT.md` | 逆向结论报告（API 路线为什么放弃、已破解到哪一步）（**不入库**） |

## 想加新页面 / 新指纹

看 `COLORPRINT.md` §5/§8。一句话：截图丢进 `shots/` -> 在 `tools/pick_print.py` 的 `LABELS` 登记
-> `pick --label <页名> --region 0,130,552,1006` 采指纹（**必须排掉顶栏的账号资源数字**，§9-6）
-> 贴进 `pages/<页名>.py` -> `verify` + `test_print_route.py` 复验。
**弹窗页必须注册在主页面前面**，`ALL_PAGES[-1]` 必须是 `unknown`。
