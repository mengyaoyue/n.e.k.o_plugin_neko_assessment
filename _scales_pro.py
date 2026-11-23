"""扩展题库（v1.1.0）：全部照搬公开/开放量表原题，中文为本插件自译。

来源与许可
----------
1. **大五人格 30 分面 120 题** —— IPIP-NEO-120（Johnson, 2014；题项来自 IPIP 公共领域题库）
   原始题项页：http://ipip.ori.org/30FacetNEO-PI-RItems.htm （本机以 archive.org 快照核对）
   许可：**IPIP 公共领域** —— ipip.ori.org 原文：
   "The items and scales are in the public domain, which means that one can copy, edit,
   translate, or use them for any purpose without asking permission and without paying a fee."
   30 个分面 × 4 条，反向题按原键值（每面 0~4 条反向）。

2. **性格优势 24 项 96 题** —— IPIP-VIA-R（Bluemke, Partsch, Saucier & Lechner, 2021）
   原始题项页：http://ipip.ori.org/IPIP-VIA-R_Key.html （同样以 archive.org 快照核对）
   许可：同为 IPIP 公共领域。24 个优势 × 4 条，每个优势固定「2 正 + 2 反」。

两套题都只做**自我了解**，不是诊断，也不是官方 MBTI / VIA 认证结果。
"""

from __future__ import annotations

# ── 通用选项组（与 _scales.py 同口径，这里独立定义避免循环导入）────
LIKERT_ACCURACY = [
    {"label": "非常不准确", "value": 1},
    {"label": "不太准确", "value": 2},
    {"label": "不好说", "value": 3},
    {"label": "比较准确", "value": 4},
    {"label": "非常准确", "value": 5},
]

AGREE_5 = [
    {"label": "很不同意", "value": 1},
    {"label": "不太同意", "value": 2},
    {"label": "一般", "value": 3},
    {"label": "比较同意", "value": 4},
    {"label": "非常同意", "value": 5},
]


def _rows(dim, facet, rows):
    """rows: [(中文条目, 是否反向)]；英文原句写在行尾注释里，便于逐条核对。"""
    out = []
    for text, rev in rows:
        item = {"text": text, "dim": dim, "reverse": bool(rev)}
        if facet:
            item["facet"] = facet
        out.append(item)
    return out


# ════════════════════════════════════════════════════════════
# ① IPIP-NEO-120：30 个分面 × 4 题（公共领域）
# ════════════════════════════════════════════════════════════
NEO_ITEMS = []
NEO_ITEMS += _rows("N", "N1", [
    ("我常为各种事情担心。", False),                       # Worry about things.
    ("我总往最坏处想。", False),                          # Fear for the worst.
    ("我害怕的东西很多。", False),                         # Am afraid of many things.
    ("我很容易紧张起来。", False),                         # Get stressed out easily.
])
NEO_ITEMS += _rows("N", "N2", [
    ("我容易发火。", False),                              # Get angry easily.
    ("我容易被惹烦。", False),                            # Get irritated easily.
    ("我会控制不住脾气。", False),                         # Lose my temper.
    ("我不太容易被惹毛。", True),                          # Am not easily annoyed.
])
NEO_ITEMS += _rows("N", "N3", [
    ("我常感到情绪低沉。", False),                         # Often feel blue.
    ("我不喜欢自己。", False),                            # Dislike myself.
    ("我常常心情很差、提不起劲。", False),                  # Am often down in the dumps.
    ("我对自己感到自在。", True),                          # Feel comfortable with myself.
])
NEO_ITEMS += _rows("N", "N4", [
    ("我很难主动接近别人。", False),                       # Find it difficult to approach others.
    ("我害怕别人把注意力放在我身上。", False),              # Am afraid to draw attention to myself.
    ("只有和熟人在一起我才自在。", False),                  # Only feel comfortable with friends.
    ("棘手的社交场合我也不太受影响。", True),                # Am not bothered by difficult social situations.
])
NEO_ITEMS += _rows("N", "N5", [
    ("我会忍不住放纵一阵（暴食、乱买、通宵这类）。", False),   # Go on binges.
    ("我很少放纵过头。", True),                            # Rarely overindulge.
    ("我很容易抵挡诱惑。", True),                          # Easily resist temptations.
    ("我能控制住自己的欲望。", True),                       # Am able to control my cravings.
])
NEO_ITEMS += _rows("N", "N6", [
    ("我很容易慌。", False),                              # Panic easily.
    ("事情一多我就招架不住。", False),                      # Become overwhelmed by events.
    ("我常有「应付不来」的感觉。", False),                  # Feel that I'm unable to deal with things.
    ("压力下我也能保持冷静。", True),                       # Remain calm under pressure.
])

NEO_ITEMS += _rows("E", "E1", [
    ("我很容易交到朋友。", False),                         # Make friends easily.
    ("我在人多的场合很自在。", False),                      # Feel comfortable around people.
    ("我尽量避免和人打交道。", True),                       # Avoid contacts with others.
    ("我和别人保持距离。", True),                          # Keep others at a distance.
])
NEO_ITEMS += _rows("E", "E2", [
    ("我喜欢热闹的大聚会。", False),                       # Love large parties.
    ("在聚会上我会和很多不同的人聊天。", False),            # Talk to a lot of different people at parties.
    ("我更愿意一个人待着。", True),                        # Prefer to be alone.
    ("我会避开人群。", True),                              # Avoid crowds.
])
NEO_ITEMS += _rows("E", "E3", [
    ("我习惯把事情揽过来牵头。", False),                    # Take charge.
    ("我倾向于带着大家走。", False),                       # Try to lead others.
    ("我喜欢把事情抓在自己手里。", False),                  # Take control of things.
    ("我习惯等别人先出头。", True),                        # Wait for others to lead the way.
])
NEO_ITEMS += _rows("E", "E4", [
    ("我总是很忙。", False),                              # Am always busy.
    ("我一直在动，停不下来。", False),                      # Am always on the go.
    ("空闲时间我也安排很多事。", False),                    # Do a lot in my spare time.
    ("我喜欢慢慢来、别赶。", True),                        # Like to take it easy.
])
NEO_ITEMS += _rows("E", "E5", [
    ("我喜欢刺激。", False),                              # Love excitement.
    ("我会主动去找冒险。", False),                         # Seek adventure.
    ("我享受那种不顾后果的痛快。", False),                  # Enjoy being reckless.
    ("我会做出很疯很野的事。", False),                     # Act wild and crazy.
])
NEO_ITEMS += _rows("E", "E6", [
    ("我的快乐会感染别人。", False),                       # Radiate joy.
    ("我玩得很尽兴。", False),                            # Have a lot of fun.
    ("我热爱生活。", False),                              # Love life.
    ("我总能看到生活里亮的那一面。", False),                # Look at the bright side of life.
])

NEO_ITEMS += _rows("O", "O1", [
    ("我的想象很鲜活。", False),                          # Have a vivid imagination.
    ("我喜欢让思绪飞到很远的地方。", False),                # Enjoy wild flights of fantasy.
    ("我爱做白日梦。", False),                            # Love to daydream.
    ("我喜欢沉浸在思考里。", False),                       # Like to get lost in thought.
])
NEO_ITEMS += _rows("O", "O2", [
    ("我相信艺术是重要的。", False),                       # Believe in the importance of art.
    ("我能看到别人没注意到的美。", False),                  # See beauty in things that others might not notice.
    ("我不喜欢诗。", True),                               # Do not like poetry.
    ("我不爱去美术馆。", True),                           # Do not enjoy going to art museums.
])
NEO_ITEMS += _rows("O", "O3", [
    ("我的情绪来得很强烈。", False),                       # Experience my emotions intensely.
    ("我能感受到别人的情绪。", False),                     # Feel others' emotions.
    ("我很少注意到自己的情绪反应。", True),                 # Rarely notice my emotional reactions.
    ("我不太理解那些情绪化的人。", True),                   # Don't understand people who get emotional.
])
NEO_ITEMS += _rows("O", "O4", [
    ("比起一成不变，我喜欢变化。", False),                  # Prefer variety to routine.
    ("我更愿意待在熟悉的东西里。", True),                   # Prefer to stick with things that I know.
    ("我不喜欢变动。", True),                             # Dislike changes.
    ("我依恋习惯的做法。", True),                          # Am attached to conventional ways.
])
NEO_ITEMS += _rows("O", "O5", [
    ("我喜欢读有难度的东西。", False),                     # Love to read challenging material.
    ("我避开哲学式的讨论。", True),                        # Avoid philosophical discussions.
    ("抽象的概念我理解起来吃力。", True),                   # Have difficulty understanding abstract ideas.
    ("我对理论讨论没兴趣。", True),                        # Am not interested in theoretical discussions.
])
NEO_ITEMS += _rows("O", "O6", [
    ("投票时我倾向更开放的一方。", False),                  # Tend to vote for liberal political candidates.
    ("我认为对错没有绝对标准。", False),                    # Believe that there is no absolute right and wrong.
    ("投票时我倾向更保守的一方。", True),                   # Tend to vote for conservative political candidates.
    ("我认为对犯罪该强硬。", True),                        # Believe that we should be tough on crime.
])

NEO_ITEMS += _rows("A", "A1", [
    ("我信任别人。", False),                              # Trust others.
    ("我相信别人是好意。", False),                         # Believe that others have good intentions.
    ("别人说的话我倾向于相信。", False),                    # Trust what people say.
    ("我对人有戒心。", True),                             # Distrust people.
])
NEO_ITEMS += _rows("A", "A2", [
    ("我会为了自己的目的利用别人。", True),                 # Use others for my own ends.
    ("为了往上走，我会走捷径、不那么老实。", True),          # Cheat to get ahead.
    ("我会占别人便宜。", True),                           # Take advantage of others.
    ("我会阻挠别人的计划。", True),                        # Obstruct others' plans.
])
NEO_ITEMS += _rows("A", "A3", [
    ("我在意别人。", False),                              # Am concerned about others.
    ("我很愿意帮人。", False),                            # Love to help others.
    ("我对别人的感受无所谓。", True),                      # Am indifferent to the feelings of others.
    ("我不愿意为别人花时间。", True),                      # Take no time for others.
])
NEO_ITEMS += _rows("A", "A4", [
    ("我喜欢吵一场痛快的架。", True),                       # Love a good fight.
    ("我会冲人大吼。", True),                             # Yell at people.
    ("我会挖苦、贬低别人。", True),                        # Insult people.
    ("我会找机会报复。", True),                           # Get back at others.
])
NEO_ITEMS += _rows("A", "A5", [
    ("我觉得自己比别人强。", True),                        # Believe that I am better than others.
    ("我对自己评价很高。", True),                          # Think highly of myself.
    ("我很看得起自己。", True),                            # Have a high opinion of myself.
    ("我会夸自己的优点。", True),                          # Boast about my virtues.
])
NEO_ITEMS += _rows("A", "A6", [
    ("我同情无家可归的人。", False),                       # Sympathize with the homeless.
    ("对处境比我差的人，我会心软。", False),                # Feel sympathy for those who are worse off than myself.
    ("别人的问题我不关心。", True),                        # Am not interested in other people's problems.
    ("我尽量不去想那些困苦的人。", True),                   # Try not to think about the needy.
])

NEO_ITEMS += _rows("C", "C1", [
    ("我总能把事情顺利完成。", False),                     # Complete tasks successfully.
    ("我做事做得比别人好。", False),                       # Excel in what I do.
    ("我处理任务很顺手。", False),                         # Handle tasks smoothly.
    ("我知道怎么把事办成。", False),                       # Know how to get things done.
])
NEO_ITEMS += _rows("C", "C2", [
    ("我喜欢把东西收拾整齐。", False),                     # Like to tidy up.
    ("我常忘了把东西放回原位。", True),                     # Often forget to put things back in their proper place.
    ("我房间常是乱的。", True),                           # Leave a mess in my room.
    ("我的东西到处乱放。", True),                          # Leave my belongings around.
])
NEO_ITEMS += _rows("C", "C3", [
    ("我守承诺。", False),                                # Keep my promises.
    ("我说真话。", False),                                # Tell the truth.
    ("我会违反规则。", True),                             # Break rules.
    ("我会食言。", True),                                 # Break my promises.
])
NEO_ITEMS += _rows("C", "C4", [
    ("我做的常超出别人对我的要求。", False),                # Do more than what's expected of me.
    ("我很拼。", False),                                  # Work hard.
    ("我在工作上投入的时间精力很少。", True),               # Put little time and effort into my work.
    ("我做事只做到刚好过关。", True),                      # Do just enough work to get by.
])
NEO_ITEMS += _rows("C", "C5", [
    ("我总是做好准备。", False),                          # Am always prepared.
    ("我定的计划会执行下去。", False),                      # Carry out my plans.
    ("我会浪费时间。", True),                             # Waste my time.
    ("我很难开始动手。", True),                           # Have difficulty starting tasks.
])
NEO_ITEMS += _rows("C", "C6", [
    ("我不多想就一头扎进去。", True),                       # Jump into things without thinking.
    ("我做决定很草率。", True),                           # Make rash decisions.
    ("我做事很急。", True),                               # Rush into things.
    ("我先做再想。", True),                               # Act without thinking.
])

# 30 个分面：key / 中文名 / 所属大维度 / 一句话说明
NEO_FACETS = [
    {"key": "N1", "name": "焦虑", "dim": "N", "desc": "担心与紧张出现的频率"},
    {"key": "N2", "name": "愤怒", "dim": "N", "desc": "被激怒的门槛有多低"},
    {"key": "N3", "name": "抑郁", "dim": "N", "desc": "低落情绪有多深、多频繁"},
    {"key": "N4", "name": "自我意识", "dim": "N", "desc": "被注视时的不适程度"},
    {"key": "N5", "name": "放纵", "dim": "N", "desc": "对冲动的抵抗力"},
    {"key": "N6", "name": "压力脆弱", "dim": "N", "desc": "压力下会不会散架"},
    {"key": "E1", "name": "友善", "dim": "E", "desc": "主动亲近别人的倾向"},
    {"key": "E2", "name": "合群", "dim": "E", "desc": "在人群里获得的能量"},
    {"key": "E3", "name": "果断", "dim": "E", "desc": "愿不愿意站出来主导"},
    {"key": "E4", "name": "活跃", "dim": "E", "desc": "行动与节奏的快慢"},
    {"key": "E5", "name": "追求刺激", "dim": "E", "desc": "对高唤醒体验的胃口"},
    {"key": "E6", "name": "开朗", "dim": "E", "desc": "正向情绪的外放程度"},
    {"key": "O1", "name": "想象力", "dim": "O", "desc": "内在画面有多丰富"},
    {"key": "O2", "name": "艺术兴趣", "dim": "O", "desc": "对美的敏感与需求"},
    {"key": "O3", "name": "情感丰富", "dim": "O", "desc": "情绪体验的强度"},
    {"key": "O4", "name": "尝新", "dim": "O", "desc": "对变化与陌生经验的接受度"},
    {"key": "O5", "name": "思辨", "dim": "O", "desc": "对抽象与理论的兴趣"},
    {"key": "O6", "name": "观念开放", "dim": "O", "desc": "对多元观点的容忍度"},
    {"key": "A1", "name": "信任", "dim": "A", "desc": "对他人动机的默认预期"},
    {"key": "A2", "name": "坦诚", "dim": "A", "desc": "守规则、不算计的程度"},
    {"key": "A3", "name": "利他", "dim": "A", "desc": "愿不愿意主动付出"},
    {"key": "A4", "name": "合作", "dim": "A", "desc": "冲突里的姿态"},
    {"key": "A5", "name": "谦逊", "dim": "A", "desc": "自我评价的分寸"},
    {"key": "A6", "name": "同情", "dim": "A", "desc": "对弱势处境的反应"},
    {"key": "C1", "name": "自我效能", "dim": "C", "desc": "对自己办得成的确信"},
    {"key": "C2", "name": "条理", "dim": "C", "desc": "环境与流程的秩序感"},
    {"key": "C3", "name": "尽责", "dim": "C", "desc": "对承诺与规则的态度"},
    {"key": "C4", "name": "追求成就", "dim": "C", "desc": "往上推的那股劲"},
    {"key": "C5", "name": "自律", "dim": "C", "desc": "开始并坚持的力气"},
    {"key": "C6", "name": "谨慎", "dim": "C", "desc": "决策前的停顿"},
]

NEO_DIMS = [
    {"key": "N", "name": "情绪敏感性", "low": "情绪平稳", "high": "容易起伏",
     "tip": "警报系统灵不灵。高不是坏事，只是需要更多恢复时间。"},
    {"key": "E", "name": "外向性", "low": "偏内敛", "high": "偏外放",
     "tip": "能量朝外还是朝内。中间地带最拥挤，不必往两头靠。"},
    {"key": "O", "name": "开放性", "low": "务实", "high": "爱探索",
     "tip": "对新想法、新体验的胃口。"},
    {"key": "A", "name": "宜人性", "low": "较自我", "high": "很体贴",
     "tip": "合作与信任的倾向。太高容易被消耗，太低容易被孤立。"},
    {"key": "C", "name": "尽责性", "low": "随性", "high": "很有条理",
     "tip": "自律与收尾能力，是做事结果最稳定的预测项。"},
]


# ════════════════════════════════════════════════════════════
# ② IPIP-VIA-R：24 个性格优势 × 4 题（公共领域）
# ════════════════════════════════════════════════════════════
VIA_ITEMS = []
VIA_ITEMS += _rows("APP", None, [
    ("我觉得活在一个有美的世界里很重要。", False),          # Feel it's important to live in a world of beauty.
    ("看到美的东西，我会有很深的触动。", False),            # Experience deep emotions when I see beautiful things.
    ("我很少注意到身边的自然之美。", True),                 # Am rarely aware of the natural beauty in the environment.
    ("别人提起之前，我注意不到美。", True),                 # Fail to notice beauty until others comment on it.
])
VIA_ITEMS += _rows("CAP", None, [
    ("我知道生命里有人像在乎自己一样在乎我。", False),       # Know that there are people in my life who care as much for me as for themselves.
    ("我能把爱说出口、给出去。", False),                     # Can express love to someone else.
    ("我不容易把感受分享给别人。", True),                   # Do not easily share my feelings with others.
    ("我很难接受别人给的爱。", True),                       # Have difficulty accepting love from anyone.
])
VIA_ITEMS += _rows("CIT", None, [
    ("我是个非常忠诚的人。", False),                        # Am an extremely loyal person.
    ("我会支持队友和同伴。", False),                        # Support my teammates or fellow group members.
    ("我不擅长在团队里合作。", True),                       # Am not good at working with a group.
    ("我什么都想一个人做。", True),                         # Prefer to do everything alone.
])
VIA_ITEMS += _rows("CUR", None, [
    ("很多不同的活动都能让我兴奋。", False),                # Am excited by many different activities.
    ("任何处境里我都能找到有意思的地方。", False),           # Can find something of interest in any situation.
    ("我对世界没那么多好奇。", True),                       # Am not all that curious about the world.
    ("我兴趣很少。", True),                                # Have few interests.
])
VIA_ITEMS += _rows("EQU", None, [
    ("我平等对待所有人。", False),                          # Treat all people equally.
    ("我认为每个人的权利同样重要。", False),                 # Believe that everyone's rights are equally important.
    ("我会占别人便宜。", True),                            # Take advantage of others.
    ("不喜欢谁，我就会对他另眼相看。", True),                # Treat others differently if I don't like them.
])
VIA_ITEMS += _rows("FOR", None, [
    ("别人对我不好时，我会试着理解着回应。", False),          # Try to respond with understanding when someone treats me badly.
    ("我愿意给别人重新开始的机会。", False),                # Allow others to make a fresh start.
    ("我会记仇。", True),                                  # Hold grudges.
    ("我很难原谅别人。", True),                            # Find it hard to forgive others.
])
VIA_ITEMS += _rows("GRA", None, [
    ("对在乎我的人，我会说出感谢。", False),                 # Express my thanks to those who care about me.
    ("我是个很懂感恩的人。", False),                        # Am an extremely grateful person.
    ("我对别人没有感恩。", True),                          # Feel no gratitude to others.
    ("生活里值得感谢的事很少。", True),                      # Find few things in my life to be grateful for.
])
VIA_ITEMS += _rows("HOP", None, [
    ("别人觉得糟的事，我能看到好的那一面。", False),          # Can find the positive in what seems negative to others.
    ("遇到难处我也仍抱有希望。", False),                    # Remain hopeful despite challenges.
    ("我总预期最坏的结果。", True),                        # Expect the worst.
    ("我常去想那些其实不太会发生的坏结果。", True),           # Often think about the possibility of negative outcomes that are not likely to occur.
])
VIA_ITEMS += _rows("HUM", None, [
    ("我会用笑让别人那一天亮起来。", False),                 # Use laughter to brighten the days of others.
    ("再闷的处境我也保留幽默感。", False),                   # Keep my sense of humor even in gloomy situations.
    ("我并不是以幽默出名的人。", True),                     # Am not known for my sense of humor.
    ("和我在一起不怎么好玩。", True),                       # Am not fun to be with.
])
VIA_ITEMS += _rows("IND", None, [
    ("事情没做完我不会撂下。", False),                       # Don't quit a task before it is finished.
    ("有阻碍我也要把事做完。", False),                      # Finish things despite obstacles in the way.
    ("我开了头的事常做不完。", True),                       # Don't finish what I start.
    ("我容易放弃。", True),                                # Give up easily.
])
VIA_ITEMS += _rows("INT", None, [
    ("别人放心把秘密交给我。", False),                      # Am trusted to keep secrets.
    ("我守承诺。", False),                                 # Keep my promises.
    ("为了脱身我会说谎。", True),                          # Lie to get myself out of trouble.
    ("我会辜负信任我的人。", True),                         # Cheat on people who have trusted me.
])
VIA_ITEMS += _rows("JUD", None, [
    ("我会权衡利弊。", False),                             # Weigh the pro's and the con's.
    ("朋友看重我的判断力。", False),                        # Am valued by my friends for my good judgment.
    ("我不太会批判性地把事情想透。", True),                  # Don't tend to think things through critically.
    ("做决定时我不去考虑其他可能。", True),                  # Don't think about different possibilities when making decisions.
])
VIA_ITEMS += _rows("KIN", None, [
    ("再忙我也会帮朋友。", False),                          # Am never too busy to help a friend.
    ("我会特意去把低落的人哄起来。", False),                 # Go out of my way to cheer up people who appear down.
    ("别人跟我讲他的问题，我会不耐烦。", True),              # Get impatient when others talk to me about their problems.
    ("只有别人对我好，我才对他好。", True),                  # Am only kind to others if they have been kind to me.
])
VIA_ITEMS += _rows("LEA", None, [
    ("我擅长让大家配合得好。", False),                      # Am good at helping people work well together.
    ("别人说我是个有力量又公平的领头人。", False),            # Am told that I am a strong but fair leader.
    ("我很难让别人一起合作。", True),                       # Have difficulty getting others to work together.
    ("我不擅长带一个团队。", True),                         # Am not good at taking charge of a group.
])
VIA_ITEMS += _rows("LOV", None, [
    ("我是真的会一辈子学下去的人。", False),                 # Am a true life-long learner.
    ("学到新东西我会很兴奋。", False),                      # Am thrilled when I learn something new.
    ("我不喜欢学新东西。", True),                          # Don't like to learn new things.
    ("我不会为了好玩去读非虚构。", True),                    # Don't read nonfiction books for fun.
])
VIA_ITEMS += _rows("MOD", None, [
    ("我不吹自己的成绩。", False),                          # Don't brag about my accomplishments.
    ("没人会用「傲慢」形容我。", False),                     # Would never be described as arrogant.
    ("我喜欢在人群里显眼。", True),                         # Like to stand out in a crowd.
    ("我喜欢谈自己。", True),                              # Like to talk about myself.
])
VIA_ITEMS += _rows("ORI", None, [
    ("我能想出新的做法。", False),                          # Come up with new ways to do things.
    ("我想东西有自己的原创性。", False),                     # Am an original thinker.
    ("别人不觉得我有新点子。", True),                       # Am not considered to have new and different ideas.
    ("我没有特别想做出原创东西的冲动。", True),              # Have no special urge to do something original.
])
VIA_ITEMS += _rows("PER", None, [
    ("我对生活有成熟的看法。", False),                      # Have a mature view on life.
    ("别人认为我有智慧。", False),                          # Am considered to be a wise person.
    ("我不太分得清什么才是真正重要的。", True),              # Am not good at figuring out what really matters.
    ("很少有人来向我请教。", True),                         # Am rarely consulted for advice by others.
])
VIA_ITEMS += _rows("PRU", None, [
    ("我认为宁可稳妥，也别事后后悔。", False),               # Believe it is always better to be safe than sorry
    ("我做选择很谨慎。", False),                            # Make careful choices.
    ("我常常没想清后果就先做。", True),                      # Act before thinking through the consequences.
    ("我喜欢冒险。", True),                                # Like taking risks.
])
VIA_ITEMS += _rows("SEL", None, [
    ("我是个自律到近乎严格的人。", False),                   # Am a highly disciplined person.
    ("明知长期有害的东西，哪怕当下舒服我也会放掉。", False),   # Forego things that are bad for me in the long run...
    ("我会被「买买买」「吃吃吃」的冲动带走。", True),          # Let myself be taken over by urges to spend or eat too much.
    ("我会向冲动让步。", True),                            # Give in to my urges.
])
VIA_ITEMS += _rows("SOC", None, [
    ("我很能察觉别人此刻的感受。", False),                   # Am good at sensing what others are feeling.
    ("我知道说什么能让人舒服。", False),                     # Know what to say to make people feel good.
    ("到了陌生的社交场合我不知道怎么应对。", True),           # Don't know how to handle myself in a new social situation.
    ("我常猜不准别人会怎么反应。", True),                    # Have trouble guessing how others will react.
])
VIA_ITEMS += _rows("SPI", None, [
    ("我是个有精神性/灵性的人。", False),                    # Am a spiritual person.
    ("我相信每个人都有活着的意义。", False),                 # Believe that each person has a purpose in life.
    ("我觉得生活没有意义。", True),                         # Feel that life has no meaning.
    ("我不相信有更高的力量或神。", True),                    # Do not believe in a universal power or a God.
])
VIA_ITEMS += _rows("VAL", None, [
    ("面对强烈的反对，我常常还是会站出来。", False),          # Have taken frequent stands in the face of strong opposition.
    ("不受欢迎的观点我也照说。", False),                     # Don't hesitate to express an unpopular opinion.
    ("我不会为我的信念挺身而出。", True),                    # Do not stand up for my beliefs.
    ("可能带来坏结果时，我不会把真心话说出来。", True),        # Don't speak my mind freely when there might be negative results.
])
VIA_ITEMS += _rows("ZES", None, [
    ("醒来时我会对这一天可能发生的事感到兴奋。", False),      # Awaken with a sense of excitement about the day's possibilities.
    ("我期待每一个新的日子。", False),                      # Look forward to each new day.
    ("别人会形容我爱抱怨、脾气差。", True),                  # Am described as grumpy.
    ("我没什么精力。", True),                              # Don't have much energy.
])

VIA_DIMS = [
    {"key": "APP", "name": "审美与卓越", "tip": "能被美、被高水平的表达打动"},
    {"key": "CAP", "name": "爱的能力", "tip": "能给爱，也能接住爱"},
    {"key": "CIT", "name": "团队与忠诚", "tip": "对集体和同伴的忠诚"},
    {"key": "CUR", "name": "好奇", "tip": "对世界保持兴趣"},
    {"key": "EQU", "name": "公平", "tip": "一视同仁，不因好恶偏心"},
    {"key": "FOR", "name": "宽恕", "tip": "能放下，不反刍"},
    {"key": "GRA", "name": "感恩", "tip": "能看见别人给过什么"},
    {"key": "HOP", "name": "希望与乐观", "tip": "相信事情会变好"},
    {"key": "HUM", "name": "幽默", "tip": "能让气氛轻下来"},
    {"key": "IND", "name": "勤奋与坚持", "tip": "开了头就会做完"},
    {"key": "INT", "name": "诚信", "tip": "说到做到，不占暗处的便宜"},
    {"key": "JUD", "name": "判断力", "tip": "会权衡，不被第一反应带走"},
    {"key": "KIN", "name": "善良与慷慨", "tip": "愿意为别人多走一步"},
    {"key": "LEA", "name": "领导力", "tip": "能把人组织起来"},
    {"key": "LOV", "name": "热爱学习", "tip": "学新东西本身就让你愉快"},
    {"key": "MOD", "name": "谦逊", "tip": "不靠抬高自己换位置"},
    {"key": "ORI", "name": "创造力", "tip": "能想出不一样的做法"},
    {"key": "PER", "name": "洞察与智慧", "tip": "看得清什么才重要"},
    {"key": "PRU", "name": "审慎", "tip": "做决定前会停一下"},
    {"key": "SEL", "name": "自我调节", "tip": "能管住当下的冲动"},
    {"key": "SOC", "name": "社交与情商", "tip": "读得懂人，也接得住场"},
    {"key": "SPI", "name": "灵性", "tip": "相信有比日常更大的东西"},
    {"key": "VAL", "name": "勇气", "tip": "怕也还是会站出来"},
    {"key": "ZES", "name": "热情与活力", "tip": "对新的一天有期待"},
]


# ════════════════════════════════════════════════════════════
# 量表定义
# ════════════════════════════════════════════════════════════
SCALES_PRO = [
    {
        "id": "big5f",
        "name": "大五人格 · 30 分面（IPIP-NEO-120）",
        "category": "人格",
        "minutes": 8,
        "kind": "dimension",
        "source": "IPIP-NEO-120（Johnson, 2014；IPIP 公共领域题库）｜中文为本插件自译",
        "license": "IPIP 公共领域（public domain），可自由复制、翻译、使用",
        "public_domain": True,
        "tags": ["30 分面", "120 题", "公共领域", "IPIP"],
        "intro": "同样五个大维度，再往下切成 30 个分面：不只说你是「高尽责」，还说高在条理、自律还是追求成就。",
        "options": LIKERT_ACCURACY,
        "dimensions": NEO_DIMS,
        "facets": NEO_FACETS,
        "items": NEO_ITEMS,
        "bank": NEO_ITEMS,
        "min_items": 60,
        "default_items": 120,
        "fixed": False,
        "method": "5 点计分（非常不准确 ~ 非常准确）。反向题先翻转再相加；大维度分 = 该维度下 6 个分面题目的合计，"
                  "百分比按该维度满分换算；分面分同理按 4 题满分换算。"
                  "题目取自 IPIP-NEO-120 原题（公共领域），中文为自译；百分比是量表内部相对强度，不是人群排名。",
    },
    {
        "id": "via",
        "name": "性格优势 24 项（IPIP-VIA-R）",
        "category": "优势",
        "minutes": 7,
        "kind": "dimension",
        "source": "IPIP-VIA-R（Bluemke 等, 2021；IPIP 公共领域题库）｜中文为本插件自译",
        "license": "IPIP 公共领域（public domain）",
        "public_domain": True,
        "tags": ["24 优势", "96 题", "公共领域", "优势识别"],
        "intro": "不问哪里有病，只问哪里最有力气：24 个性格优势里，你的前五名是哪几个。",
        "options": AGREE_5,
        "dimensions": VIA_DIMS,
        "items": VIA_ITEMS,
        "bank": VIA_ITEMS,
        "min_items": 48,
        "default_items": 96,
        "fixed": False,
        "method": "5 点同意度。每个优势 4 条（2 正 + 2 反），反向题翻转后相加，再按 4 题满分换算百分比。"
                  "题目取自 IPIP-VIA-R 原题（公共领域），中文为自译。"
                  "选做题数少于 96 时每个优势拿到的题数不等，分数会更抖——想比排名就答满 96 题。",
    },
]

# 结果配图（量表主色）
SCALE_ART_EXTRA = {
    "big5f": {"emoji": "🧬", "from": "#7f8ff7", "to": "#7fd0e8"},
    "via": {"emoji": "🌟", "from": "#f7c46f", "to": "#f79fc0"},
}


def dim_detail():
    """新量表的维度长文解读（结构同 _bank.DIM_DETAIL：high / low / advice）。"""
    return {
        "big5f": {
            "N": {
                "high": "情绪敏感度高：警报系统很灵，坏消息先到你身上。好处是你能提前感知风险、共情也更深；代价是需要更多恢复时间。",
                "low": "情绪敏感度低：大多数事压不垮你，别人慌你还能做事。代价是有时读不到关系里的暗流。",
                "advice": ["把「恢复时间」当正事排进日程，而不是等崩溃了再休息", "情绪上头时先写下三句话再回复任何人", "睡眠不足会把这一项直接推高，先修睡眠"],
            },
            "E": {
                "high": "外向性高：能量朝外，边说边想，人越多越来劲。注意别把「热闹」当成必须。",
                "low": "外向性低：能量朝内，先想后说，独处是充电不是逃避。别被「要开朗」的话推着走。",
                "advice": ["按能量而不是按场合安排社交", "给自己留一段不解释的独处时间", "把重要对话放到你能量高的时段"],
            },
            "O": {
                "high": "开放性高：对新想法新体验胃口好，容易先看到可能性。代价是收尾难。",
                "low": "开放性低：务实、信经验、不爱空转。代价是变化来的时候适应成本高。",
                "advice": ["新想法先做一个小实验再判断", "给探索设一个截止时间，避免开太多头", "把「不感兴趣」换成「先试十分钟」"],
            },
            "A": {
                "high": "宜人性高：默认信任、愿意配合，是团队里的黏合剂。代价是容易被消耗、难说不。",
                "low": "宜人性低：边界清楚、敢争，事情推进得快。代价是容易把人推远。",
                "advice": ["练习一句不解释的拒绝", "冲突里先说事实再说感受", "把「帮忙」设上限，别用透支换关系"],
            },
            "C": {
                "high": "尽责性高：计划、收尾、守承诺，是最能预测结果的一项。代价是容易对自己过严。",
                "low": "尽责性低：灵活、临场发挥强。代价是长期目标容易断线。",
                "advice": ["把目标拆到「今天能做完」的粒度", "用外部结构（闹钟、同伴）代替意志力", "完成比完美重要：先交初版"],
            },
        },
        "via": {
            "APP": {"high": "审美是你的充电口：一段音乐、一点光就能把你救回来。", "low": "美对你不算燃料，你更靠具体结果回血。", "advice": ["每周留一次「只为好看」的出门"]},
            "CAP": {"high": "你能给出爱，也接得住爱。", "low": "亲密让你紧张，慢一点也算正常。", "advice": ["对一个人说具体的感谢，而不是泛泛的「谢谢」"]},
            "CIT": {"high": "你对同伴忠诚，团队里有你在就稳。", "low": "你更相信个人而非集体。", "advice": ["把「我们」具体化成两三个人的名字"]},
            "CUR": {"high": "好奇心让你一直在长。", "low": "你更愿意深挖已知，而不是铺开。", "advice": ["每周给自己一个「不知道就先查一下」的机会"]},
            "EQU": {"high": "你按规则和道理待人，不太看关系亲疏。", "low": "你会按亲疏调整分寸。", "advice": ["在分配时间和注意力时，先问「谁更需要」"]},
            "FOR": {"high": "你能放下，不反复咀嚼。", "low": "你记得住伤害，这会保护你，也会耗你。", "advice": ["把「原谅」定义成不再为此付费，而不是和好"]},
            "GRA": {"high": "你能看见别人给过什么。", "low": "你更习惯自己扛。", "advice": ["睡前写下一件今天被善待的小事"]},
            "HOP": {"high": "你相信事情会变好，这让你能撑。", "low": "你先预设坏结果，好处是不容易被打懵。", "advice": ["把担心写成「如果…我就…」的具体预案"]},
            "HUM": {"high": "你能让气氛轻下来。", "low": "你更认真，不太靠玩笑解压。", "advice": ["给自己找一个不伤害任何人的解压出口"]},
            "IND": {"high": "开了头你就会做完。", "low": "你靠灵感启动，靠截止日收尾。", "advice": ["把大任务切成 15 分钟的第一块"]},
            "INT": {"high": "你说的和你做的一致。", "low": "你在方便和诚实之间会更灵活。", "advice": ["承诺前先看一眼日历再说好"]},
            "JUD": {"high": "你会权衡，不被第一反应带走。", "low": "你更信直觉和速度。", "advice": ["重要决定至少隔一晚"]},
            "KIN": {"high": "你愿意为别人多走一步。", "low": "你的善意是有条件的。", "advice": ["帮人前先确认自己有没有余量"]},
            "LEA": {"high": "你能把人组织起来。", "low": "你更适合做关键执行者。", "advice": ["开会前先写清「今天要定什么」"]},
            "LOV": {"high": "学习本身就是奖励。", "low": "你只为用得上而学。", "advice": ["挑一个「完全没用」的题目学两周"]},
            "MOD": {"high": "你不靠抬高自己换位置。", "low": "你愿意让人看见你的成绩。", "advice": ["把「我做得不错」和「我不错」分开说"]},
            "ORI": {"high": "你能想出不一样的做法。", "low": "你更擅长把现成方案做扎实。", "advice": ["每天留十分钟「不评判地乱想」"]},
            "PER": {"high": "你看得清什么才重要。", "low": "你更关注眼前具体的事。", "advice": ["每月问自己一次「这月在为什么付时间」"]},
            "PRU": {"high": "你做决定前会停一下。", "low": "你敢赌，也承担得住。", "advice": ["给冲动设一个 24 小时冷静期"]},
            "SEL": {"high": "你能管住当下的冲动。", "low": "你的自控靠环境和外部约束。", "advice": ["把诱惑从默认选项里移走，比靠意志力有效"]},
            "SOC": {"high": "你读得懂人，也接得住场。", "low": "你在人群里更慢热。", "advice": ["在陌生场合先找一个具体的人聊具体的事"]},
            "SPI": {"high": "你相信有比日常更大的东西。", "low": "你更信可验证的部分。", "advice": ["给自己留一段无目的的安静时间"]},
            "VAL": {"high": "怕也还是会站出来。", "low": "你会挑值得的仗再打。", "advice": ["把「不敢说」的话先写下来，再决定说不说"]},
            "ZES": {"high": "你对新的一天有期待。", "low": "你的能量需要主动补。", "advice": ["把一件期待的事排进这周，而不是等有空"]},
        },
    }
