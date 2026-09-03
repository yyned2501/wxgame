# -*- coding: utf-8 -*-
"""主页(lobby): 自动开宝箱 -> 开始玩家对战"""
import logging

from .base import (CHEST_BLOCK_ALL, Page, chest_slot_key, color_button,
                     color_pixels)

CHEST_SLOTS = [(109, 855), (220, 855), (331, 855), (441, 855)]
# ^ 2026-09-02 重标定: 旧值 (95,741)... 落在卡片顶边外(卡片实占 y738..879), 且 x 取自金币角标图标(偏左 14px),
#   真机 19 次点击全部落空. 现值 = 4 张卡片实测中心 x(109/220/331/441) + 操作按钮行 y=855(真机[开启]金色块 840..870)
CHEST_BAND = (695, 790)
# ^ 卡片[标题带](宝箱名/时长角标那一行). 判据本身不用它, 它只被 test_print_route.py [8] 拿去断言
#   [点色指纹不许罩住角标行] —— 角标颜色随宝箱档位变, 罩进去就成假指纹。

# ---- 动作层点色(2026-09-03 定案: 零 OCR) --------------------------------
# 四张宝箱卡片的操作按钮长得几乎一样, 但颜色构成完全不同, 数颜色比读字稳得多:
#   [开启]    = 整块纯金, 左边没东西挡   -> 按钮框黄 1235~1241, 左半黄 380~400
#   [[AD]加速] = 金按钮左边贴了张蓝票券图标 -> 按钮框黄  789~818, 左半黄只剩 123~133
#   [点击解锁] = 深色底白字(点它[免费]开箱) -> 按钮框黄 0, 白 143~176
#   空槽位     = 那一行没有按钮            -> 全 0
# 上面是 33 帧 lobby 语料 x 4 槽 = 132 个观测的实测区间, 逐帧与 OCR 真值核对过
# (复核脚本 scratch/scripts/slot_truth2.py, 输出 scratch/o_truth2.txt; 改阈值后重跑它即回归)。
# 阈值取法: 黄 >=500 才算有金按钮(实测 789 vs 0); 左半黄 >=250 判[开启](实测 380 vs 123);
#   白 >=120 判[点击解锁](实测 143~176, 而[开启]/[[AD]]按钮自带的白描边只有 70~100, 120 留安全边际)。
# 票券图标色 AAE4FF/6FC2F2/223F6B 与金色不搭, 所以只数金色就能把[开启]和[[AD]]分开。
# 注意 [[AD]] 那一格点下去 = 看激励视频加速, WATCH_ADS=False 时一律不点。
CHEST_BTN_COLOR = 0xFDCA33
CHEST_WHITE = 0xFFFFFF
CHEST_BTN_BAND = (838, 882)     # 按钮行 y 范围(标题行在 y810..826, 不许混进来)
CHEST_BTN_HALF = 45             # 卡片宽 ~111, 半宽 45 足够且不串邻列
CHEST_YELLOW_MIN = 500
CHEST_OPEN_LEFT_MIN = 250
CHEST_UNLOCK_WHITE_MIN = 120
# [玩家对战]按钮: 也是同一套金色。外接框中心 = 落点, 所以取样框必须**只罩住按钮本体**:
#   按钮本体实测恒定占 abs x93..268 / y651..700(n=6405~6539), 框左边界开到 x=88 就够了。
# 坑(真机 2026-09-03 10:01 那批 lobby_live1002xx 共 10 帧): 框左边界原来开到 x=60, 于是**按钮左边那张
#   英雄立绘**的橙黄部件也进了 mask(abs x65..78 一小片一小片, 随账号/活动出现), 外接框被拽成
#   x65..268 -> 中心从 (180,675) 漂到 (166,670), 差 14px。立绘位置不可预测, 这种漂移就是"下次点空"的前兆。
#   (落点当时还在按钮内, 没造成误点, 但判据已经不稳 —— 真机日志里 165/167/180 三种落点就是这么来的)
# 逐列profile(shots/lobby_live100100 vs shots/lobby_clean): 碎块最远到 x=78, 按钮从 x=93 开始,
#   中间 15px 空隙 -> x0 取 88(离按钮左边 5px、离立绘 10px)。
# 复跑 shots/+shots_live/ 全部 596 张: 黄块 >=3000px 的 118 张**全部**中心 (180,675)、n=6405~6539, 0 离群,
#   落点与人工核对过的真值表逐字一致(所以 test_act_zero_ocr / test_chest_livelock 的表都不用改)。
PVP_BOX = (88, 640, 290, 720)
PVP_COLOR = 0xFDCA33
PVP_MIN_PX = 3000


class LobbyPage(Page):
    name = 'lobby'
    next_pages = ('chest_open', 'matching', 'chest_info', 'versus', 'claim_popup', 'ad_popup', 'vip_popup',
                  'diamond_popup', 'hero_level')

    # 点色指纹: 2026-09-03 10:20 重标(第三次), 命令见下
    #   python tools/pick_print.py pick --label lobby --region 200,900,352,992 \
    #          --cluster 9999 -n 6 --min-cross 4 --min-lum 60 --min-chroma 30 --min-sep 34
    #   复核: 本页全中 50/50 / 其他页误中 0 / margin 0.10
    #
    # 为什么标在[底部导航栏中间页签的高亮板]上 —— 三条教训叠出来的结论:
    #   1) 不许标在文字像素上(09-03 上午: 旧指纹标在用户名 User103635 的字面上,
    #      账号改名/升段后整片失效) -> 标定域先排除顶栏 y<130, 再靠地板把白字滤掉。
    #   2) 不许拿[被新手引导模态压暗]的帧当训练样本(09-03 09:00: 那 11 帧 lobby_live09*
    #      其实是改版大厅盖了一层 x0.3 的黑遮罩, 不是改版。混进来标出的指纹是纸糊的:
    #      靠 +-19 容差在近黑像素上蒙混, 换一张未压暗的新布局帧就只剩 0.75)。
    #      现在它们改名 lobby_dim_live*, 归在 GROUPS['lobby'] 里 -> verify 要求
    #      [大厅被压暗时仍然判成大厅](导航栏画在遮罩之上, 本来就该认出来)。
    #   3) 不许标在[会随活动轮换的美术]上(09-03 10:10: 全域标定挑中了右侧活动图标和
    #      左上骷髅头像, 看着 50/50 全中, 其实下次换活动就废) -> 把标定域钉死在导航栏
    #      中间那一格: 它是[页签选中态], 是页面身份本身, 不随版本/账号/活动变。
    # 新增的 4 张兄弟页签帧(商店/卡牌/城堡/排名, shots/other_live10100*)就是这一条的
    #   考官: 同一条导航栏, 高亮板在别的格子上 -> 中间这格必须是普通底色, 指纹不许中。
    # 1 种形态 x 4 个十字单元(每单元 5 点, 共 20 判色点/形态), 任一形态全中即判为 lobby; 语料 50/50 全中 / 异页误中 0 / margin 0.10(异页最高只中 2/20 点) / 各形态覆盖 [50] 帧
    prints = (
        (
            [328, 912, 0x65D4FA], [330, 912, 0x275266], [326, 912, 0x65D3F9],
            [328, 914, 0x9BDAFE], [328, 910, 0x65D3FA], [224, 912, 0x65D3F9],
            [226, 912, 0x65D3F9], [222, 912, 0x66D3F9], [224, 914, 0x9DD9FD],
            [224, 910, 0x65D3F9], [328, 988, 0x67C7FF], [330, 988, 0x305268],
            [326, 988, 0x65C7FF], [328, 990, 0x68C8FF], [328, 986, 0x66C7FF],
            [228, 988, 0x65C7FF], [230, 988, 0x65C7FF], [226, 988, 0x65C7FF],
            [228, 990, 0x67C8FF], [228, 986, 0x64C6FE],
        ),
    )

    act_needs_ocr = False   # 纯点色页: 主循环不为本页跑 OCR(定页仍优先看点色指纹, 与此无关)

    def detect(self, f):
        # 只有点色指纹全不中、回落到 OCR 判页时才会走到这里。
        # 注: 语料 33 帧里 OCR 一次都没读出[玩家对战]四个字(字体描边太细),
        #     旧版动作层正是靠 f.find('玩家对战') 点按钮, 所以它从来没点着过 —— 见 act()。
        return 1.0 if f.has('玩家对战') else 0.0

    @staticmethod
    def _slot_boxes(cx):
        """(整按钮框, 按钮左半框) —— 左半用来看有没有被蓝色票券图标挡住"""
        y0, y1 = CHEST_BTN_BAND
        return ((cx - CHEST_BTN_HALF, y0, cx + CHEST_BTN_HALF, y1), (cx - 34, 846, cx - 14, 874))

    def chest_states(self, img):
        """逐槽点色判状态 -> 4 字符码: o=[开启] u=[点击解锁] a=[[AD]加速] .=空槽"""
        out = []
        for cx, _cy in CHEST_SLOTS:
            btn, left = self._slot_boxes(cx)
            if color_pixels(img, btn, CHEST_BTN_COLOR) >= CHEST_YELLOW_MIN:
                out.append('o' if color_pixels(img, left, CHEST_BTN_COLOR) >= CHEST_OPEN_LEFT_MIN else 'a')
            elif color_pixels(img, btn, CHEST_WHITE) >= CHEST_UNLOCK_WHITE_MIN:
                out.append('u')
            else:
                out.append('.')
        return ''.join(out)

    def _ready_chests(self, img):
        """可点的宝箱槽位(左->右): o/u 是免费动作才点, a/. 一律不点。判据见 chest_states()"""
        st = self.chest_states(img)
        return [slot for slot, code in zip(CHEST_SLOTS, st) if code in 'ou']

    # 轮换游标(真机教训: 旧版死点 ready[0], 那一格若点了没跳转就永远卡在同一坐标)
    _chest_i = 0

    def act(self, ctx):
        img = ctx.f.img      # act_needs_ocr=False => ctx.f 只有图没有文字框, 别用 ctx.f.find()
        # 1) 开宝箱: 按钮是纯金[开启] 或 白字[点击解锁] = 免费动作才点
        #    再叠一层拉黑: 面板判出"这格要花钱"后 CHEST_PAID_BLOCK 秒内不再点它
        #    (真机 03:54: 那一格颜色不变 -> 大厅反复点 -> 反复关面板, 6 秒一圈刷了 16 次)
        st = self.chest_states(img)
        ready = self._ready_chests(img)
        # CHEST_BLOCK_ALL = 面板判过付费但说不清是哪一格(用户手动开的面板) -> 整行先别碰
        openable = ([] if ctx.is_blocked(CHEST_BLOCK_ALL)
                    else [s for s in ready if not ctx.is_blocked(chest_slot_key(s))])
        if ready and not openable:
            if not ctx.acted('chest_blocked_log', gap=60):
                logging.info(f'[主页] 宝箱状态 {st} {len(ready)} 格全在拉黑期(开箱要花钱) -> 跳过开箱去打对战')
        elif openable:
            i = self._chest_i % len(openable)
            sx, sy = openable[i]
            if not ctx.acted('chest_open'):
                self._chest_i = i + 1
                ctx.chest_target = chest_slot_key((sx, sy))
                logging.info(f'[主页] 宝箱状态 {st} 可开 {len(openable)} 格, 点第 {i + 1} 格 ({sx},{sy})')
                ctx.click(sx, sy)
                return True
        # 2) 玩家对战: 认那块金色按钮的外接框中心(旧版要 OCR 读[玩家对战], 读不到就永远不点)
        pos = color_button(img, PVP_BOX, PVP_COLOR, PVP_MIN_PX)
        if pos is not None and not ctx.acted('pvp_click'):
            logging.info(f'[主页] 点色命中玩家对战 {pos}')
            ctx.click(*pos)
            return True
        return False
