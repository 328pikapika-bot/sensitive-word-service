#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理词库: 第七轮
1. 删除1-3位纯数字 (24, 89等无意义短数字)
2. 删除非敏感2字母英文词 (da, ma, ur等)
3. 删除常见日常用词 (价格, 联系, 没有等)
"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

# 1-3位纯数字 - 无意义, 不应作为敏感词
SHORT_DIGITS = {'24', '89', '64', '65', '250', '386', '500', '509', '535', '189'}

# 2字母英文非敏感词 (da=达, ma=妈/吗, ur=你的, xi=习等拼音首字母, 这些太常见)
# 保留: sb, SB, av, AV, sm, SM, QQ, qq, JB, jb 等已知敏感缩写
NON_SENSITIVE_EN2 = {'da', 'ma', 'ur', 'gm', 'sf', 'wg', 'xi', 'Cs', 'cS'}

# 常见日常用词 - 在正常文本中频繁出现, 不应作为敏感词
COMMON_DAILY = {
    '价格', '联系', '没有', '联系方式', '手机',
    '出售', '收购', '转让', '求购',
    '电话', '地址', '姓名', '邮箱',
}

WORDS_TO_REMOVE = SHORT_DIGITS | NON_SENSITIVE_EN2 | COMMON_DAILY

with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

original_count = sum(1 for l in lines if l.strip())
removed = []
kept = []
for line in lines:
    w = line.strip()
    if not w:
        continue
    if w in WORDS_TO_REMOVE:
        removed.append(w)
    else:
        kept.append(w)

with open('sensitive_words.txt', 'w', encoding='utf-8', newline='\n') as f:
    for w in kept:
        f.write(w + '\n')

print(f'第七轮清理:')
print(f'  原词库: {original_count}')
print(f'  删除: {len(removed)} 个')
print(f'  删除后: {len(kept)}')
print(f'\n=== 已删除 ===')
for w in sorted(removed):
    print(f'  - {w}')
