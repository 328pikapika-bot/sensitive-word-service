#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理词库中的非敏感中性词 (第一轮 + 第二轮合并)
这些是正常政治/法律/社会用语,在正常文本中频繁出现,不应作为敏感词
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 明确需要删除的非敏感中性词 (正常政治/法律/社会常用术语)
# 这些词在任何正常新闻/公文/教育内容中都会大量出现
NEUTRAL_WORDS_TO_REMOVE = {
    # ===== 第一轮: 国家/政权/社会相关中性词 =====
    '国家安全', '国家主席', '国家领导人', '国家机密', '国务院',
    '社会主义', '社会保障',
    '核心价值观', '环境保护', '文化', '文明',
    '总理', '省长',
    '军事',
    '人民',

    # ===== 第二轮: 政治职务/身份 =====
    '领导人', '干部', '代表', '公务员', '警察', '律师',

    # ===== 第二轮: 法律术语/机构 =====
    '犯罪', '起诉', '逮捕', '法院', '法庭', '检察院',
    '人大', '政协', '党代会', '党中央',

    # ===== 第二轮: 意识形态中性词 =====
    '主义', '中国特色', '共产主义', '资本主义',

    # ===== 第二轮: 常用动词/名词 =====
    '进行', '完成', '灾区',

    # ===== 第二轮: 民族称谓 =====
    '中华',
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
    if w in NEUTRAL_WORDS_TO_REMOVE:
        removed.append(w)
    else:
        kept.append(w)

# 写回 (UTF-8 no BOM, LF)
with open('sensitive_words.txt', 'w', encoding='utf-8', newline='\n') as f:
    for w in kept:
        f.write(w + '\n')

print(f'原词库数量: {original_count}')
print(f'删除非敏感中性词: {len(removed)} 个')
print(f'删除后词库数量: {len(kept)}')
print(f'\n=== 已删除的词 ({len(removed)} 个) ===')
for w in sorted(removed):
    print(f'  - {w}')

# 验证: 检查是否真的删除了
with open('sensitive_words.txt', 'r', encoding='utf-8') as f:
    remaining = set(w.strip() for w in f if w.strip())
print(f'\n=== 验证删除结果 ===')
not_removed = []
for w in NEUTRAL_WORDS_TO_REMOVE:
    if w in remaining:
        not_removed.append(w)
        print(f'  {w}: 仍存在(错误!)')
if not not_removed:
    print(f'  全部 {len(NEUTRAL_WORDS_TO_REMOVE)} 个词已成功删除')
