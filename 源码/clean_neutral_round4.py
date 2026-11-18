#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理词库中的非敏感中性词 (第四轮)
处理剩余: 代表大会、政党名称、考试片段等
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

NEUTRAL_WORDS_ROUND4 = {
    # 政治会议通用词
    '代表大会',
    # 考试相关片段 (公务员考试已删, 但残留片段)
    '务员考试',
    # 政党名称 (正常政治讨论用语)
    '国民党', '民主党', '民进党', '产党',
    # 共产党相关残留
    '共产党员',
}

with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

original_count = sum(1 for l in lines if l.strip())
removed = []
kept = []
for line in lines:
    w = line.strip()
    if not w:
        continue
    if w in NEUTRAL_WORDS_ROUND4:
        removed.append(w)
    else:
        kept.append(w)

with open('sensitive_words.txt', 'w', encoding='utf-8', newline='\n') as f:
    for w in kept:
        f.write(w + '\n')

print(f'第四轮清理:')
print(f'  原词库数量: {original_count}')
print(f'  删除: {len(removed)} 个')
print(f'  删除后: {len(kept)}')
print(f'\n=== 已删除 ===')
for w in sorted(removed):
    print(f'  - {w}')

with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    remaining = set(w.strip() for w in f if w.strip())
not_removed = [w for w in NEUTRAL_WORDS_ROUND4 if w in remaining]
print(f'\n=== 验证 ===')
print(f'  {"全部删除成功" if not not_removed else f"未删除: {not_removed}"}')
