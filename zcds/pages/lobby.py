# -*- coding: utf-8 -*-
"""主页(lobby): 自动开宝箱 -> 开始玩家对战"""
import logging, re

from .base import Page, is_countdown

CHEST_SLOTS = [(109, 855), (220, 855), (331, 855), (441, 855)]
# ^ 2026-09-02 重标定: 旧值 (95,741)... 落在卡片顶边外(卡片实占 y738..879), 且 x 取自金币角标图标(偏左 14px),
#   真机 19 次点击全部落空. 现值 = 4 张卡片实测中心 x(109/220/331/441) + 操作按钮行 y=855(真机"开启"金色块 840..870)
CHEST_BAND = (695, 790)
# ---- 真机 2026-09-02 23:35 / 23:55 定案: 只看卡片底部那一行按钮文字 ----
#   [点击解锁] -> 槽上有宝箱, 点它**免费**开始开箱(顶栏 156/143/1002 点前点后完全不变)
#   [[AD] -30分钟] -> 正在倒计时, 点它=看广告加速(WATCH_ADS=False 时绝不点)
#   [开启](真机常被 OCR 读成"开咖") -> 倒计时结束, 宝箱可领, 点它开箱
#   空槽位/空精位 -> 槽上没宝箱, 且那一行**没有文字**(空槽位的文字在 y~811 的标题行)
# 已删除的陷阱: TIMER_RE=r'\d+\s*[分时秒]' 扫全卡带, 把角标 5分/10分/20分 当成剩余倒计时,
#   而那其实是"开箱所需时长"(语料 lobby_clean: 4 格同时有 5分@y741 和 点击解锁@y853)。
# 按钮行(真机 4 帧实测: 点击解锁 y853..862 / 开启 y858 / -30分钟 y861; 标题行 y810..826)
BTN_BAND = (838, 882)
# 按钮行出现这些字样 = 不是免费动作, 一律不点
SKIP_RE = re.compile('AD|ad|钻石|广告|看视频|\\d+\\s*[时分秒]|^\\d+$')


class LobbyPage(Page):
    name = 'lobby'
    next_pages = ('chest_open', 'matching', 'chest_info', 'claim_popup', 'ad_popup', 'vip_popup', 'diamond_popup')

    # 点色指纹: 由 tools/pick_print.py pick --label lobby --region 0,130,552,1006 自动标定(勿手改)
    # 候选区必须排除顶栏资源数字(y<130): 那些点的颜色随金币/钻石数值变化, 早先标定的 15 点全在顶栏, 换号即失效
    # 3 种形态 x 3 个十字单元(每单元 5 点, 共 15 判色点/形态), 任一形态全中即判为 lobby; 语料 28/28 全中 / 异页误中 0 / margin 0.20(异页最高只中 3/15 点) / 各形态覆盖 [28, 20, 7] 帧
    # 语料 25/25 全中 / 异页误中 0 / margin 0.20 / 各形态覆盖 [17, 4, 4] 帧
    prints = (
        (   # 形态: after_battle_btn/after_click/after_click2...
            [132, 194, 0xFFFFFF], [134, 194, 0x1059AC], [130, 194, 0xF5F5F5],
            [132, 196, 0xFFFFFF], [132, 192, 0xFBFBFB], [180, 194, 0xFFFFFF],
            [182, 194, 0xBFBFBF], [178, 194, 0x8C919B], [180, 196, 0xFFFFFF],
            [180, 192, 0xD6D6D6], [380, 638, 0xFFFFFF], [382, 638, 0xF6F1EF],
            [378, 638, 0xFAF7F6], [380, 640, 0xCFAFA1], [380, 636, 0xCDAB9B],
        ),
        (   # 形态: live_lobby/live_now2/lobby_clean/guide_live2
            [132, 194, 0xFFFFFF], [134, 194, 0x1059AC], [130, 194, 0xF5F5F5],
            [132, 196, 0xFFFFFF], [132, 192, 0xFBFBFB], [180, 194, 0xFFFFFF],
            [182, 194, 0xBFBFBF], [178, 194, 0x8C919B], [180, 196, 0xFFFFFF],
            [180, 192, 0xD6D6D6], [212, 266, 0xFFFFFF], [214, 266, 0x878795],
            [210, 266, 0x424362], [212, 268, 0xFFFFFF], [212, 264, 0x9B9BA7],
        ),
        (   # 形态: live_20260902_a/b/c/d (真机 2026-09-02 帧)
            [172, 194, 0xFFFFFF], [174, 194, 0xA9ACB5], [170, 194, 0xFFFFFF],
            [172, 196, 0xFFFFFF], [172, 192, 0x808C9B], [224, 194, 0xFFFFFF],
            [226, 194, 0xDEDEDE], [222, 194, 0xFFFFFF], [224, 196, 0x5E6F8F],
            [224, 192, 0x85909D], [492, 286, 0xFFFFFF], [494, 286, 0xD6D5D8],
            [490, 286, 0xD8D8DA], [492, 288, 0xD2D2D4], [492, 284, 0xF3F3F3],
        ),
    )

    def detect(self, f):
        return 1.0 if f.has('玩家对战') else 0.0

    def _ready_chests(self, f):
        """返回可点的宝箱槽位(左→右); 判据 = **卡片底部按钮行**(BTN_BAND)里的文字

        真机实测 2026-09-02 23:34~23:55(单点 click_at + 只读探针, 四帧连续取证):
          23:34 底部[点击解锁]  -> 点它**免费**开始开箱(顶栏 156/143/1002 点前点后不变)
          23:35 底部[[AD] -30分钟] -> 正在倒计时, 点它=看广告加速 -> 绝不点
          23:55 倒计时归零, 底部[开启] -> 宝箱可领(OCR 把"开启"读成了"开咖")
          空槽位的卡片: 按钮行**根本没有文字**("空槽位"三个字在 y~811 的标题行)
        所以这里用**排除式**: 按钮行有文字 且 不像广告/倒计时 => 就是那个免费按钮。
        不用正面匹配"解锁|开启", 因为 2 个字的按钮 OCR 很容易读错("开启"->"开咖"),
        正面匹配会把已经能领的宝箱漏掉(23:55 实测就是这样漏的)。
        旧版两处根因错误(真机反复点空/永远不开箱的真凶, 不是坐标错):
          1) TIMER_RE 扫全卡带, 把角标 5分/10分/20分(=开箱所需时长)当成剩余倒计时
             -> 4 个免费宝箱一律误判成"忙";
          2) 解锁后真倒计时 0时19分55秒 被 OCR 读成乱码 -> 判不出冷却, 反过来误报就绪。
        现在角标一律不参与判断(它在 BTN_BAND 之外)。无 OCR 框时返回 [](宁可不点)。
        """
        cols = {i: [] for i in range(len(CHEST_SLOTS))}
        for b in f.boxes:
            if not BTN_BAND[0] <= b.cy <= BTN_BAND[1]:
                continue
            for i, (sx, _sy) in enumerate(CHEST_SLOTS):
                if abs(b.cx - sx) < 45:      # 同列(卡片宽 ~111, 45 足够且不串邻列)
                    cols[i].append(b.text)
                    break
        ready = []
        for i, (sx, sy) in enumerate(CHEST_SLOTS):
            joined = ''.join(cols[i])
            if not joined:                    # 空槽位 / 没读到字 -> 不点
                continue
            if is_countdown(joined) or SKIP_RE.search(joined):
                continue                      # 广告加速 / 花钻石 -> 不点
            ready.append((sx, sy))            # 剩下的就是[点击解锁]/[开启]这类免费按钮
        return ready
    # 轮换游标(真机教训: 旧版死点 ready[0], 那一格若点了没跳转就永远卡在同一坐标)
    _chest_i = 0

    def act(self, ctx):
        f = ctx.f
        # 1) 开宝箱: 卡片底部写着[点击解锁]/[开启] = 免费可开(判据见 _ready_chests 真机实测)
        ready = self._ready_chests(f)
        if ready:
            i = self._chest_i % len(ready)
            sx, sy = ready[i]
            if not ctx.acted('chest_open'):
                self._chest_i = i + 1
                logging.info(f'[主页] 宝箱可开 {len(ready)} 格, 点第 {i + 1} 格 ({sx},{sy})')
                ctx.click(sx, sy)
                return True
        # 2) 玩家对战
        pts = f.find('玩家对战')
        if pts:
            if not ctx.acted('pvp_click'):
                logging.info(f'[主页] 点 玩家对战 {pts[0]}')
                ctx.click(*pts[0])
                return True
        return False