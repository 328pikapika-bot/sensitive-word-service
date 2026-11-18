#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理词库中的非敏感中性词 (第三轮)
处理剩余误报: 人大/政协会议系列、共产/马克思系列、法律程序词、教育考试词
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 第三轮: 剩余误报的非敏感中性词
NEUTRAL_WORDS_ROUND3 = {
    # ===== 人大/政协会议系列 (正常政治机构用语) =====
    '人大代表', '人民代表', '人民代表大会', '人大常委', '人大会议',
    '全国人大', '全国政协', '政协委员', '政协会议',

    # ===== 共产/马克思系列 (正常意识形态用语) =====
    '共产', '共产党', '共产党员', '马克思', '马克思主义', '列宁', '恩格斯',

    # ===== 法律程序词 (正常司法用语) =====
    '开庭', '休庭', '庭审', '审判长', '审判员', '书记员',

    # ===== 教育考试词 (正常教育用语) =====
    '考试', '高考', '中考', '公务员考试', '司法考试',

    # ===== 政务活动词 (正常政务用语) =====
    '建言', '献策', '提案', '议案', '建议', '意见',
    '视察', '调研', '考察', '慰问', '接见', '会见', '座谈',
}

# 读取原词库
with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

original_count = sum(1 for l in lines if l.strip())
removed = []
kept = []
for line in lines:
    w = line.strip()
    if not w:
        continue
    if w in NEUTRAL_WORDS_ROUND3:
        removed.append(w)
    else:
        kept.append(w)

# 写回 (UTF-8 no BOM, LF)
with open('sensitive_words.txt', 'w', encoding='utf-8', newline='\n') as f:
    for w in kept:
        f.write(w + '\n')

print(f'第三轮清理:')
print(f'  原词库数量: {original_count}')
print(f'  删除非敏感中性词: {len(removed)} 个')
print(f'  删除后词库数量: {len(kept)}')
print(f'\n=== 已删除的词 ({len(removed)} 个) ===')
for w in sorted(removed):
    print(f'  - {w}')

# 验证
with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    remaining = set(w.strip() for w in f if w.strip())
not_removed = [w for w in NEUTRAL_WORDS_ROUND3 if w in remaining]
print(f'\n=== 验证 ===')
if not_removed:
    print(f'  仍有 {len(not_removed)} 个词未删除: {not_removed}')
else:
    print(f'  全部 {len(NEUTRAL_WORDS_ROUND3)} 个词已成功删除')
