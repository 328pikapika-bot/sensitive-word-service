#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理词库中的非敏感中性词 (第五轮)
处理: 政党职务/政治概念/地域用语
注意: 保留"独裁"等批评性政治词汇(仍作为敏感词)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

NEUTRAL_WORDS_ROUND5 = {
    # 政党职务/组织 (正常政治用语)
    '党主席', '执政党', '执政',
    # 政党派系
    '民主党派',
    # 政治概念 (正常政治学用语)
    '民主', '人权',
    # 地域用语 (正常地理称谓)
    '大陆',
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
    if w in NEUTRAL_WORDS_ROUND5:
        removed.append(w)
    else:
        kept.append(w)

with open('sensitive_words.txt', 'w', encoding='utf-8', newline='\n') as f:
    for w in kept:
        f.write(w + '\n')

print(f'第五轮清理:')
print(f'  原词库数量: {original_count}')
print(f'  删除: {len(removed)} 个')
print(f'  删除后: {len(kept)}')
print(f'\n=== 已删除 ===')
for w in sorted(removed):
    print(f'  - {w}')

with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    remaining = set(w.strip() for w in f if w.strip())
not_removed = [w for w in NEUTRAL_WORDS_ROUND5 if w in remaining]
print(f'\n=== 验证 ===')
print(f'  {"全部删除成功" if not not_removed else f"未删除: {not_removed}"}')
