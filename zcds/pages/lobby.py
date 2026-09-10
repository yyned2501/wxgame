# -*- coding: utf-8 -*-
"""主页(lobby): 自动开宝箱 -> 开始玩家对战"""
import logging

from config import WATCH_ADS
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
#   [点击解锁] = 深色底白字               -> 按钮框黄 0, 白 143~176
#   空槽位     = 那一行没有按钮            -> 全 0
# 上面是 33 帧 lobby 语料 x 4 槽 = 132 个观测的实测区间, 逐帧与 OCR 真值核对过
# (复核脚本 scratch/scripts/slot_truth2.py, 输出 scratch/o_truth2.txt; 改阈值后重跑它即回归)。
# 阈值取法: 黄 >=500 才算有金按钮(实测 789 vs 0); 左半黄 >=250 判[开启](实测 380 vs 123);
#   白 >=120 判[点击解锁](实测 143~176, 而[开启]/[[AD]]按钮自带的白描边只有 70~100, 120 留安全边际)。
# 票券图标色 AAE4FF/6FC2F2/223F6B 与金色不搭, 所以只数金色就能把[开启]和[[AD]]分开。
# 注意 [[AD]] 那一格点下去 = 看激励视频给这一格减 30 分钟冷却。
#   旧版(≤2026-09-04)**刻意不点**: 点下去之后是什么面板从未采集过, 而广告额度一天只有 8 次。
#   2026-09-05 用户定案「如果可以看广告得奖励, 优先看广告」-> a 格接入看广告窗口(见 act 第 0 步),
#   无填充时广告窗口 4~6s 自己撒手, 面板/弹窗由既有出口处理; 节流 AD_ACCEL_GAP 防刷。
AD_ACCEL_GAP = 120.0    # 秒; 两次点 a 格的最小间隔(与结算页 CLAIM_GAP 同口径: 连点必撞"稍后再试")
CHEST_BTN_COLOR = 0xFDCA33
CHEST_WHITE = 0xFFFFFF
CHEST_BTN_BAND = (838, 882)     # 按钮行 y 范围(标题行在 y810..826, 不许混进来)
CHEST_BTN_HALF = 45             # 卡片宽 ~111, 半宽 45 足够且不串邻列
CHEST_YELLOW_MIN = 500
CHEST_OPEN_LEFT_MIN = 250
CHEST_UNLOCK_WHITE_MIN = 120
# ---- 卡片右上角的红色感叹号徽章 = "这一格现在能白嫖" (2026-09-03 晚真机第 21 轮定案) ----
# 坑(真机第 20 轮 12 次白跑): 卡片底部白字[点击解锁]其实对应**两种面板** ——
#   免费 [解锁 🕐50分] = 往这一格放一个宝箱并启动 50 分钟倒计时;
#   付费 [开启 💎120]  = 花 120 紫宝石立刻开。
# 两种卡片长得一模一样(同一张宝箱图 + 同样的白字 + 同样的"50分/1时"时长角标), 白字判据分不开,
# 于是旧版把白字一律当免费 -> 每次进面板都被 chest_info 的宝石像素判成付费(实测 366) 再拉黑 300s,
# **一次都没解锁成功过** —— 这就是"该点宝箱却没点"。
# 判据: 只有"此刻能免费操作"的格子才在卡片右上角画红角标 ❗(实测 x=槽中心+36..+52 / y735..748, ~16x14)。
# 语料 149 帧 x 4 槽 = **596 个观测**, 逐槽数 (cx+34,730,cx+58,756) 里的红像素(degree=60 容差):
#   '.' 空槽        n=288  恒 0
#   'a' [[AD]加速]  n= 45  恒 0
#   'p' 点击解锁(无角标) n= 53  恒 0   <- 只能花宝石
#   'o' [开启]      n= 76  120~128    <- 免费可开, 当然带角标
#   'U' 点击解锁(带角标) n=134  120~128   <- 免费解锁
#   => (0,60) 区间内**一个骑墙值都没有**, 阈值取 60, 两边各留 2 倍余量。
# 🔴 degree 必须 60 不能沿用默认 90: colorprint.tolerance(90)=13 太窄, 同一格只数到 48~55(<60 会全判付费);
#    tolerance(60)=51 才罩得住徽章的抗锯齿边 -> 120~128. 容差窄到把自己判死的典型坑。
# 交叉验证: 把 chest_info 面板帧按时间戳配到它前面最近(<=60s)的一张 lobby 帧, 比"面板免费/付费"与
#   "大厅有没有 o/U 格" -> 免费 9 个时间戳 / 付费 34 个, **0 反例**(test_chest_unlock.py [3] 锁死)。
# 真机第 21 轮首命中: 19:33:36 `.oUU` -> 点 o 格开箱 -> 19:33:45 `..UU` -> 点 U 格,
#   面板打出"点色命中免费按钮 (275,795) 带内宝石像素 **0**" = 第一次真机证明 U 真的免费。
# 🔴 角标是**状态**不是格子属性: 19:06 `.UUU`(角标 127/120/121) 到 19:14 同样的位置已是 `..pp`(全 0),
#    用掉/时间推进都会让 U 退回 p -> 每帧现量, 绝不缓存"某格免费"。
CHEST_BADGE_COLOR = 0xFF3B3B
CHEST_BADGE_DEGREE = 60
CHEST_BADGE_MIN = 60
CHEST_BADGE_OFF = (34, 730, 58, 756)   # 相对槽中心 x 的取样框, 见上面的实测范围
# ---- 一格免费都没有时, 要不要试探点一下 p 格? (2026-09-03 晚, 用户口径: 看到[点击解锁]就点宝箱) ----
# 用户截图(19:03:27 的宝箱行)按窗口坐标解码实测 = .UUU(角标 127/120/120, 第4格角标被裁在图外),
#   那一帧本来就是当前判据会点的形态; 但 20:54 真机 lobby 实测三帧都是 appp(角标全 0) ->
#   于是出现[底下明明写着点击解锁, 脚本却只去打对战] —— 用户要求改成这种时候也点宝箱。
# 判据侧的已知事实(见上面角标注释 + scratch/scripts/chestinfo_gemscan.py):
#   chest_info 面板 70 帧按[按钮带内紫宝石像素]二分 = 0(免费 23 帧) / 362(付费 47 帧), 没有骑墙值;
#   面板里只有那一颗黄按钮(付费面板实拍 scratch/shots_probe/panel_paid.png 也没有第二个免费入口),
#   而 chest_info.act() 必须[带内宝石像素 < GEM_MIN] 才肯点, 否则只点右上角 X 关闭并拉黑该格 300s。
# 所以试探点 p 是零风险的: 免费 -> 真的白嫖一次解锁; 付费 -> 关面板走人, 一克拉宝石都不会花。
#   它同时补齐目前缺的直接证据 —— 语料里从来没有一张从 p 格点进去的面板帧。
# 边界: 只试探 p。.(空槽) 一律不点; a(=[[AD]加速]) 自 2026-09-05 用户定案后走**广告优先**分支
#   (act 第 0 步, 见 AD_ACCEL_GAP), 不再属于试探路径 —— 试探分支永远碰不到 a。
CHEST_PROBE_P = False   # 2026-09-08 用户定案: 「别用钻石开宝箱」—— 一格免费都没有时也不试探 p 格
CHEST_PROBE_GAP = 25.0   # 秒; 试探点击节流(已无效, 留作占位)
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

    @staticmethod
    def badge_pixels(img, cx):
        """卡片右上角红感叹号徽章的像素数(0 = 这一格此刻没有免费动作)"""
        bx0, by0, bx1, by1 = CHEST_BADGE_OFF
        return color_pixels(img, (cx + bx0, by0, cx + bx1, by1),
                            CHEST_BADGE_COLOR, degree=CHEST_BADGE_DEGREE)

    def chest_states(self, img):
        """逐槽点色判状态 -> 4 字符码:
        o=[开启] U=[点击解锁]且带红角标(点它免费) p=[点击解锁]但无角标(只能花宝石)
        a=[[AD]加速] g=绿色[开启 200💎] 立即开(花钻石, 用户 2026-09-08 定案不点)
        . =空槽 —— 角标判据见 CHEST_BADGE_OFF 上方注释"""
        out = []
        for cx, _cy in CHEST_SLOTS:
            btn, left = self._slot_boxes(cx)
            if color_pixels(img, btn, CHEST_BTN_COLOR) >= CHEST_YELLOW_MIN:
                out.append('o' if color_pixels(img, left, CHEST_BTN_COLOR) >= CHEST_OPEN_LEFT_MIN else 'a')
            elif self._green_button_pixels(img, cx) >= 60:
                out.append('g')   # 2026-09-08 用户定案: 绿底[开启 200💎] 立即开 = 别用钻石开
            elif color_pixels(img, btn, CHEST_WHITE) >= CHEST_UNLOCK_WHITE_MIN:
                out.append('U' if self.badge_pixels(img, cx) >= CHEST_BADGE_MIN else 'p')
            else:
                out.append('.')
        return ''.join(out)

    @staticmethod
    def _green_button_pixels(img, cx):
        """绿色[立即开箱]按钮像素数. 实测 2026-09-08 槽 2 (cx=220): 按钮框内 R<200 G>150 B<150 G>R+30 数 >=60."""
        import numpy as np
        y0, y1 = CHEST_BTN_BAND
        region = np.asarray(img.convert('RGB').crop((cx - CHEST_BTN_HALF, y0, cx + CHEST_BTN_HALF, y1)), dtype=int)
        if region.ndim != 3 or region.size == 0:
            return 0
        r, g, b = region[..., 0], region[..., 1], region[..., 2]
        return int(((r < 200) & (g > 150) & (b < 150) & (g > r + 30)).sum())

    def _ready_chests(self, img, st=None):
        """可点的宝箱槽位(左->右): 只有 o=[开启] 和 U=[点击解锁]带红角标 才是免费动作。
        p(解锁要宝石) / a([[AD]加速, 点它=看视频) / .(空槽) 一律不点。判据见 chest_states()
        st 传现成的状态码就不重复量像素(chest_states 每帧要 8~12 次 color_pixels, act 里别量两遍)"""
        if st is None:
            st = self.chest_states(img)
        return [slot for slot, code in zip(CHEST_SLOTS, st) if code in 'oU']

    # 轮换游标(真机教训: 旧版死点 ready[0], 那一格若点了没跳转就永远卡在同一坐标)
    _chest_i = 0
    _chest_p_i = 0        # 试探 p 格的轮换游标(同理, 别死点同一格)
    _chest_ad_i = 0       # a 格(看广告加速)的轮换游标

    def act(self, ctx):
        img = ctx.f.img      # act_needs_ocr=False => ctx.f 只有图没有文字框, 别用 ctx.f.find()
        st = self.chest_states(img)
        # 0) 广告优先(用户 2026-09-05 定案「如果可以看广告得奖励, 优先看广告」):
        #    有 [[AD]-30分钟加速] 格 -> 抢前台 -> 点它 -> start_ad_watch 接管(期间不定页/零 OCR/零点击)。
        #    无填充时广告窗口自己撒手交回路由; 120s 节流; 该格判过付费拉黑期不碰。
        if WATCH_ADS and not ctx.is_blocked(CHEST_BLOCK_ALL):
            ad_slots = [s for s, code in zip(CHEST_SLOTS, st)
                        if code == 'a' and not ctx.is_blocked(chest_slot_key(s))]
            if ad_slots and not ctx.acted('chest_ad', gap=AD_ACCEL_GAP):
                i = self._chest_ad_i % len(ad_slots)
                sx, sy = ad_slots[i]
                self._chest_ad_i = i + 1
                logging.info(f'[主页] 宝箱状态 {st} 有[AD]加速格 -> 优先看广告, 点第 {i + 1} 格 ({sx},{sy})')
                fg = getattr(ctx, 'ensure_foreground', None)
                if fg:
                    fg('大厅宝箱[AD]加速')
                ctx.click(sx, sy)
                ctx.start_ad_watch('大厅宝箱[AD]加速')
                return True
        # 1) 开宝箱(纯点色五档码 o/U/p/a/. 见 chest_states):
        #    有免费格(o=[开启] / U=[点击解锁]且带红角标) -> 优先点它, 顺序不变
        #    一格免费都没有 -> 按用户口径**试探点 p 格**(白字[点击解锁]), 由 chest_info 面板的
        #      "按钮带内紫宝石像素"硬闸决定点还是关: 付费只关面板 + 拉黑该格 CHEST_PAID_BLOCK 秒,
        #      全程不可能花宝石(见 CHEST_PROBE_P 上方证据)。a 格已由第 0 步广告优先分支接管。
        #    再叠一层拉黑: 那一格颜色不变 -> 大厅反复点 -> 反复关面板, 真机 03:54 6 秒一圈刷了 16 次
        ready = self._ready_chests(img, st)
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
        elif CHEST_PROBE_P and not ready and not ctx.is_blocked(CHEST_BLOCK_ALL):
            # 无免费格 -> 试探点一格 p(用户口径), 免费/付费交给面板的宝石像素硬闸, 见 CHEST_PROBE_P
            probes = [s for s, code in zip(CHEST_SLOTS, st)
                      if code == 'p' and not ctx.is_blocked(chest_slot_key(s))]
            if probes and not ctx.acted('chest_probe', gap=CHEST_PROBE_GAP):
                i = self._chest_p_i % len(probes)
                sx, sy = probes[i]
                self._chest_p_i = i + 1
                ctx.chest_target = chest_slot_key((sx, sy))
                logging.info(f'[主页] 宝箱状态 {st} 无免费格 -> 试探点 p 格 ({sx},{sy})'
                             f' (免费/付费由面板宝石像素判定)')
                ctx.click(sx, sy)
                return True
        # 2) 玩家对战: 认那块金色按钮的外接框中心(旧版要 OCR 读[玩家对战], 读不到就永远不点)
        pos = color_button(img, PVP_BOX, PVP_COLOR, min_px=PVP_MIN_PX)
        if pos is not None and not ctx.acted('pvp_click'):
            logging.info(f'[主页] 点色命中玩家对战 {pos}')
            ctx.click(*pos)
            return True
        return False
