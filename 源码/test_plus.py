#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""敏感词检测Plus端到端测试"""
import sys, requests, time
sys.stdout.reconfigure(encoding='utf-8')
BASE = 'http://localhost:3399'

print('=' * 65)
print('  敏感词检测Plus 端到端测试 (方案A: ToolGood.Words)')
print('=' * 65)

ok = 0
fail = 0

# 测试1: 原引擎不受影响
print('\n--- 测试1: 原引擎标准检测 (确保未破坏) ---')
for expected, text in [
    ("傻B", "没脑子的傻B天天控评"),
    ("sb", "真是个sb"),
    ("傻逼", "一群没脑子的傻逼"),
    ("fuck", "what the fuck"),
]:
    resp = requests.post(f'{BASE}/api/sensitive_check', json={'content':text,'type':0}).json()
    found = resp['data'] or ''
    status = 'OK' if expected in found else 'MISS'
    print(f'  [{status}] {expected:8s} -> {found}')
    ok += 1 if status == 'OK' else 0
    fail += 0 if status == 'OK' else 1

# 测试2: Plus引擎标准检测
print('\n--- 测试2: Plus引擎标准检测 ---')
for expected, text in [
    ("傻B", "没脑子的傻B天天控评"),
    ("sb", "真是个sb"),
    ("傻逼", "一群没脑子的傻逼"),
    ("脑残", "脑残粉"),
]:
    resp = requests.post(f'{BASE}/api/sensitive_plus_check', json={'content':text,'type':0}).json()
    found = resp['data'] or ''
    status = 'OK' if expected in found else 'MISS'
    print(f'  [{status}] {expected:8s} -> {found}')
    ok += 1 if status == 'OK' else 0
    fail += 0 if status == 'OK' else 1

# 测试3: Plus引擎变体检测 (核心优势)
print('\n--- 测试3: Plus引擎变体检测 (核心优势) ---')
variants = [
    ("全角sb", "真是个ｓｂ", "sb"),           # U+FF53 s + U+FF42 b
    ("全角SB", "真是个ＳＢ", "SB"),           # U+FF33 S + U+FF22 B
    ("符号干扰", "真是个s b", "sb"),          # 空格干扰
    ("符号干扰2", "赌.博是违法的", "赌博"),    # 点号干扰
    ("繁体检测", "賭博是違法的", "赌博"),      # 繁体賭博
]
for label, text, expected_word in variants:
    resp = requests.post(f'{BASE}/api/sensitive_plus_check', json={'content':text,'type':0}).json()
    found = resp['data'] or ''
    status = 'OK' if expected_word.lower() in found.lower() else 'MISS'
    print(f'  [{status}] {label:12s} -> {found}')
    ok += 1 if status == 'OK' else 0
    fail += 0 if status == 'OK' else 1

# 测试4: 无误报
print('\n--- 测试4: 无误报检查 ---')
for word, text in [
    ("支持", "我支持这个方案"),
    ("安全", "安全第一"),
    ("系统", "系统升级"),
    ("国家", "中国国家"),
    ("人民", "人民法院"),
    ("北京", "北京市"),
]:
    resp = requests.post(f'{BASE}/api/sensitive_plus_check', json={'content':text,'type':0}).json()
    found = resp['data'] or ''
    status = 'OK' if word not in found else 'FALSE'
    print(f'  [{status}] {word}')
    ok += 1 if status == 'OK' else 0
    fail += 0 if status == 'OK' else 1

# 测试5: AJAX接口
print('\n--- 测试5: AJAX接口 ---')
resp = requests.post(f'{BASE}/sensitive_plus_check', json={'text':"这个傻B真的是个脑残"}).json()
if resp.get('found_words') and "傻B" in resp['found_words']:
    print(f'  [OK] AJAX正常, count={resp["count"]}')
    ok += 1
else:
    print(f'  [FAIL] AJAX异常: {resp}')
    fail += 1

# 测试6: 性能对比
print('\n--- 测试6: 性能对比 (20页含敏感词, 6万字) ---')
test_text = ("这个傻B真的是个脑残，天天在网上发垃圾内容，简直就是个sb。" * 2000)[:60000]
t0 = time.time()
requests.post(f'{BASE}/api/sensitive_check', json={'content':test_text,'type':0})
t_orig = time.time() - t0
t0 = time.time()
requests.post(f'{BASE}/api/sensitive_plus_check', json={'content':test_text,'type':0})
t_plus = time.time() - t0
print(f'  原引擎(AC+jieba):   {t_orig:.3f}s')
print(f'  Plus引擎(AC+归一化): {t_plus:.3f}s')
status = 'OK' if t_plus < 10 else 'WARN'
print(f'  [{status}]')
ok += 1 if t_plus < 10 else 0
fail += 0 if t_plus < 10 else 1

# 测试7: 50页纯文本性能
print('\n--- 测试7: 50页纯文本性能 (20万字) ---')
clean_text = ("这是一段普通的中文文本，用于测试敏感词检测系统的性能表现。" * 8000)[:200000]
t0 = time.time()
requests.post(f'{BASE}/api/sensitive_plus_check', json={'content':clean_text,'type':0})
t_clean = time.time() - t0
print(f'  Plus引擎耗时: {t_clean:.3f}s')
status = 'OK' if t_clean < 10 else 'WARN'
print(f'  [{status}]')
ok += 1 if t_clean < 10 else 0
fail += 0 if t_clean < 10 else 1

print(f'\n{"=" * 65}')
print(f'  总计: {ok} 通过, {fail} 失败')
print(f'{"=" * 65}')
