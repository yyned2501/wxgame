# -*- coding: utf-8 -*-
r"""开箱死循环回归: 面板判出"要花钱"之后, 大厅必须改去点[玩家对战]

真机 2026-09-03 03:54 (bot.log + shots_live/dbg_019..042):
  大厅第 1 格 = [点击解锁](白字) -> 点 -> 面板"按钮带内宝石像素 362 = 要花钱" -> 关面板
  -> 回大厅, 那一格颜色一模一样, 还是"可开" -> 再点 -> 再关 ... 6 秒一圈, 连刷 16 圈,
  一局都没打到, 而且每圈都白跑一次面板判据。
修法(pages/base.py chest_slot_key + App.block/is_blocked + lobby/chest_info 两处 act):
  面板判付费 -> 把**那一格**拉黑 CHEST_PAID_BLOCK 秒 -> 大厅过滤掉拉黑的格子 ->
  没格可点就正常走[玩家对战]; 到期后再探一次(宝箱会随时间转免费)。

ctx 用的是**线上真的 App**(block/is_blocked/acted 全走实现, 不另写一套语义),
dry_run=True 所以 click 只打日志不会真点窗口; 帧全部来自 shots/ 语料,
免费/付费由文件名钉死(_paid_ = 要花钱, 4 张都人眼核对过)。
用法(项目根目录): python -X utf8 test_chest_livelock.py     # 退出码 0 = 全通过
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

from PIL import Image                                       # noqa: E402

import pick_print as pp                                     # noqa: E402
from auto_bot import App                                    # noqa: E402
from pages.base import (CHEST_BLOCK_ALL, CHEST_PAID_BLOCK,  # noqa: E402
                        chest_slot_key, color_button)
from pages.chest_info import ChestInfoPage                  # noqa: E402
from pages.lobby import (CHEST_SLOTS, PVP_BOX, PVP_COLOR,   # noqa: E402
                         PVP_MIN_PX, LobbyPage)

FAILS = []


def check(cond, msg, detail=''):
    print('%-4s %-52s -> %s' % (cond, msg, detail))
    if not cond:
        FAILS.append(msg + ' | ' + detail)


class Ctx(App):
    """真的 App 当 ctx, 只多记一份"本轮点击"供断言"""

    def click(self, x, y):
        self.clicks.append((int(x), int(y)))
        App.click(self, x, y)


def frame(nm):
    """语料名 -> PIL 图(统一缩到指纹基准尺寸)"""
    p = pp.img_path(nm)
    assert p, '语料帧缺失: %s' % nm
    im = Image.open(p).convert('RGB')
    return im.resize(pp.REF) if im.size != pp.REF else im


def new_ctx():
    c = Ctx(dry_run=True, low_cpu=False, resize=False)
    c.clicks = []
    return c


def nxt(c, img):
    """模拟"新的一轮": 换帧 + 清节流表(拉黑表不清 —— 它本来就是跨轮生效的)"""
    from vision import ScreenFeature
    c.f = ScreenFeature(img=img, boxes=[], joined='')
    c.last_action = {}
    c.clicks = []
    return c


def on_btn(pt):
    x0, y0, x1, y1 = ChestInfoPage.BTN_BOX
    return x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1


FREE_PANEL = 'shots/chest_info_live031152'          # 免费面板(带内宝石像素 0)
PAID_PANEL = 'shots/chest_info_paid_035442'         # 要花钱的面板(带内宝石像素 362)
ONE_SLOT = 'shots/lobby_live004222'                 # '.u..' 只有第 2 格可点
FOUR_SLOTS = 'shots/lobby_clean'                    # 'uuuu'  四格全可点
SLOT2 = CHEST_SLOTS[1]                              # (220, 855)


def main():
    lp, ci = LobbyPage(), ChestInfoPage()
    PVP = color_button(frame(ONE_SLOT), PVP_BOX, PVP_COLOR, PVP_MIN_PX)
    check(PVP == (180, 675), '大厅[玩家对战]按钮落点', str(PVP))

    print('[1] 大厅点下去时, 必须把"点的是哪一格"交给面板(ctx.chest_target)')
    c = new_ctx()
    nxt(c, frame(ONE_SLOT))
    lp.act(c)
    want = chest_slot_key(SLOT2)
    check(c.clicks == [SLOT2], '大厅点第 2 格 (%d,%d)' % SLOT2, str(c.clicks))
    check(c.chest_target == want, 'chest_target 交接正确', repr(c.chest_target))

    print('')
    print('[2] 面板判付费 -> 只点关闭 + 把那一格拉黑')
    nxt(c, frame(PAID_PANEL))
    ci.act(c)
    check(c.clicks and not any(on_btn(p) for p in c.clicks),
          '付费面板一次都没点按钮', str(c.clicks))
    check(c.is_blocked(want), '第 2 格进入拉黑期', want)
    left = c.blocked[want] - time.time()
    check(0 < left <= CHEST_PAID_BLOCK, '拉黑时长 = CHEST_PAID_BLOCK(%ds)' % CHEST_PAID_BLOCK,
          '剩余 %.0fs' % left)
    check(c.chest_target is None, '交接 key 用完即清(防下一格冒领)', repr(c.chest_target))

    print('')
    print('[3] 免费面板不许拉黑(否则把免费宝箱也封了)')
    c2 = new_ctx()
    nxt(c2, frame(FOUR_SLOTS))
    lp.act(c2)
    key0 = c2.chest_target
    nxt(c2, frame(FREE_PANEL))
    ci.act(c2)
    check(any(on_btn(p) for p in c2.clicks), '免费面板点中黄按钮', str(c2.clicks))
    check(not c2.is_blocked(key0), '免费 -> 不拉黑', repr(key0))

    print('')
    print('[4] 拉黑期内重跑大厅: 不再点那一格, 改点[玩家对战]')
    for i in range(6):
        nxt(c, frame(ONE_SLOT))
        lp.act(c)
        check(c.clicks == [PVP], '第 %d 次重跑大厅 -> 点对战' % (i + 1), str(c.clicks))
        if c.clicks != [PVP]:
            break

    print('')
    print('[5] 只拉黑出问题那一格, 别的免费格照点(不过度封杀)')
    c3 = new_ctx()
    nxt(c3, frame(FOUR_SLOTS))
    lp.act(c3)
    bad = c3.chest_target
    nxt(c3, frame(PAID_PANEL))
    ci.act(c3)
    nxt(c3, frame(FOUR_SLOTS))
    lp.act(c3)
    other = [s for s in CHEST_SLOTS if chest_slot_key(s) != bad]
    check(c3.clicks and c3.clicks[0] in other, '改点别的可点格(不是被拉黑那格)',
          '%s 拉黑=%s' % (c3.clicks, bad))

    print('')
    print('[6] 复现真机死循环: 交替喂 大厅帧/付费面板帧 20 圈')
    c4 = new_ctx()
    n_chest = n_pvp = n_paid_btn = 0
    for _ in range(20):
        nxt(c4, frame(ONE_SLOT))
        lp.act(c4)
        if c4.clicks and c4.clicks[0] in CHEST_SLOTS:
            n_chest += 1
            nxt(c4, frame(PAID_PANEL))
            ci.act(c4)
            n_paid_btn += sum(1 for p in c4.clicks if on_btn(p))
        elif c4.clicks == [PVP]:
            n_pvp += 1
    check(n_paid_btn == 0, '20 圈一次都没点付费按钮(花钱护栏)', str(n_paid_btn))
    check(n_chest == 1, '20 圈只点过一次开箱(修之前实测 16 次)', 'n_chest=%d' % n_chest)
    check(n_pvp >= 15, '其余轮次都在打对战', 'n_pvp=%d' % n_pvp)

    print('')
    print('[7] 拉黑到期后必须回头再试(宝箱会随时间转免费, 不能永久拉黑)')
    c.blocked[want] = time.time() - 1                 # 模拟 5 分钟已过
    nxt(c, frame(ONE_SLOT))
    lp.act(c)
    check(c.clicks == [SLOT2], '到期后重新点第 2 格', str(c.clicks))

    print('')
    print('[8] 说不清是哪一格时(用户手动开的面板)退化成拉黑整行 CHEST_BLOCK_ALL')
    c5 = new_ctx()
    c5.chest_target = None
    nxt(c5, frame(PAID_PANEL))
    ci.act(c5)
    check(c5.is_blocked(CHEST_BLOCK_ALL), '整行拉黑', str(sorted(c5.blocked)))
    nxt(c5, frame(FOUR_SLOTS))
    lp.act(c5)
    check(c5.clicks == [PVP], '四格全可点也先去打对战', str(c5.clicks))

    print('')
    if FAILS:
        print('不通过 %d 项:' % len(FAILS))
        for m in FAILS:
            print('  - ' + m)
        return 1
    print('全部通过 (付费宝箱格拉黑 -> 大厅改打对战; 免费格、到期重试、整行拉黑都符合预期)')
    return 0


if __name__ == '__main__':
    sys.exit(main())