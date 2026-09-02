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

## 离线验证（不用开游戏，只读 `shots/` 里已导出的 70 张截图）

> **`shots/` 语料不入 git**（70 张 / 23.35 MB，截图顶部带账号昵称）。
> 所以 clone 之后本节命令会因为找不到语料而报错：需要在游戏里自己采集截图，
> 在 `tools/pick_print.py` 的 `LABELS` 里登记后 `pick --label` 采指纹。定页逻辑本身不受影响。

```
python -X utf8 test_print_route.py            # 5 项断言 / 70 张语料：路由回归
python -X utf8 tools\pick_print.py check      # 语料与 LABELS 是否对得上
python -X utf8 tools\pick_print.py verify     # 点色指纹逐张判定，应 70/70 通过
python -X utf8 tools\print_stats.py --dry-run # 重算各页指纹统计，应与注释逐字一致
python -X utf8 test_cpu_offline.py             # 主循环离线集成测试（需要 rapidocr）
python -X utf8 test_battle_loop.py           # 连打 3 场：进战斗页必须清空已点格子
```

## 当前进度（2026-08-31 实测，全部离线复验）

| 层 | 状态 | 证据 |
|---|---|---|
| 抓窗 + 后台点击 | 通 | `game_utils.py` 纯 ctypes（PrintWindow / PostMessage），不需要 pywin32 |
| 点色指纹定页面 | 6/9 页 | `pick_print.py verify` 通过 70 / 不通过 0；`test_print_route.py` 5 项断言全过 |
| 页面动作 `act()` | 9/9 页都有 | 但 `claim_popup` / `diamond_popup` 只有 OCR 关键词（没语料标不了） |
| 战斗自动化 | 通 | `test_battle_loop.py` 连跑 3 场、战斗循环 8 次 OCR 次数 = 0（全颜色扫描） |
| 主循环 | 通，本轮修 1 个 bug | 见下 |

**本轮修掉的真 bug**：`ctx.clicked_cells` 只在 `auto_bot.py __init__` 建过一次，全项目没有一处清空，
而 `pages/battle.py` 用 `if (cx//16, cy//16) in ctx.clicked_cells: return False` 跳点过的格子；
格子 key 是固定窗口坐标、每场复用 -> 打第 2 场起整张棋盘被永久拉黑，战斗页不再动手。
现在进入 battle 页时 `clicked_cells.clear()` + `last_cell = 0`（`auto_bot.py` 159-163 行）。
`test_battle_loop.py` 是这套行为的回归测试：把清空退化掉，它会红 3 项。

### 待办（按优先级）

1. **补 `claim_popup` / `diamond_popup` 完整截图并标定指纹**。2026-08-24 那份真机日志末尾
   一直刷「`[转移] 预期{...claim_popup...} 实际->lobby` + `[主页] 宝箱就绪, 点槽位 (95,741)`」，
   就是开箱后的领奖页认不出来，只能退回大厅继续点同一个槽位。
2. **`lobby.act()` 的槽位不轮换**：`ready[0]` 永远是 `(95,741)`，点了没跳转也只会原地重试同一格，
   缺一个「这个槽位点过没反应 -> 换下一格」的机制。
3. **单帧形态没有跨帧验证**：`matching` 全部、`lobby` 第 3 形态、`battle` 第 3 形态、`result` 第 4 形态、
   `vip_popup` 的 `vip_month`（详见 `COLORPRINT.md` §9-1），补图优先级 `sm_after` / `st_2`。

> 注：`test_cpu_offline.py` 里「大厅帧2 期望 ocr=False」这行注释是旧的——进页面第一轮主循环会
> 刻意补一轮本页 ROI OCR（`auto_bot.py:165`），所以实测 `ocr=True` 属设计，不是回退失效。

## 文件地图

| 路径 | 作用 |
|---|---|
| `auto_bot.py` | 主循环/接线：抓窗 -> `route()` -> `page.act()`；含 CPU 降载（低优先级、OCR 节流） |
| `config.py` | 每页 ROI/scale/poll/ocr_gap；并暴露 `ROOT`、`SHOTS_DIR` |
| `game_utils.py` | Win32 抓窗口（PrintWindow，后台可用）、找窗口、PostMessage 点击 |
| `vision.py` | OCR 封装（rapidocr + ROI 缩放），`ocr_config.yaml` 是它的模型配置 |
| `colorprint.py` | 点色指纹原语（移植自 `..\mxdzz\libs\app.py` 的颜色对比部分） |
| `pages/base.py` | `Page` 基类 + `match_print()` / `detect_ocr()` / `route()` |
| `pages/*.py` | 9 个页面：6 个已标指纹（lobby/battle/result/chest_info/vip_popup/matching），3 个只走 OCR（claim_popup/diamond_popup/unknown） |
| `pages/unknown.py` | 兜底页：往 `shots/` 存 `stuck_*.png` + 试探弹窗遮罩 |
| `battle_scan.py` + `battle_templates.npz` | 战斗回合的颜色扫描（避免整帧 OCR，省 CPU） |
| `shots/` | 70 张标定语料（552x1006），`tools/pick_print.py` 的 `LABELS` 引用它（**不入库**） |
| `tools/` | `pick_print.py`(check/pick/verify) `print_stats.py` `set_low_cpu.ps1` + 逆向工具（il2cppdumper、wxapkg） |
| `capture/ dec/ game_src/ unity_data/` | 逆向资料：抓包、XYX 解密产物、wasm 解包、Unity 资源（**运行时不依赖，不入库**） |
| `scratch/` | 一次性脚本/中间产物归档（183 项），带 `MANIFEST.tsv` + `restore.py`（把归档搬回原位）+ `relocate.py`（把整个项目挪走），**运行时不依赖** |
| `COLORPRINT.md` | 点色指纹那层的完整说明：怎么标定、怎么加新页、和 mxdzz 的差异 |
| `AUTOMATION_REPORT.md` | 逆向结论报告（API 路线为什么放弃、已破解到哪一步）（**不入库**） |

## 想加新页面 / 新指纹

看 `COLORPRINT.md` §8。一句话：截图丢进 `shots/` -> 在 `tools/pick_print.py` 的 `LABELS` 登记
-> `pick --label <页名>` 采指纹 -> 贴进 `pages/<页名>.py` -> `verify` + `test_print_route.py` 复验。
**弹窗页必须注册在主页面前面**，`ALL_PAGES[-1]` 必须是 `unknown`。
