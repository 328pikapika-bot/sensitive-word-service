#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
敏感词库合并去重脚本 V1.1
从开源词库下载并合并到现有 sensitive_words.txt
来源:
  1. konsheng/Sensitive-lexicon (MIT License)
  2. houbb/sensitive-word-data (Apache 2.0 License)
"""

import os
import sys
import shutil
import urllib.request
import urllib.parse
from collections import OrderedDict

# ============================================================
# 配置
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_FILE = os.path.join(BASE_DIR, "sensitive_words.txt")
BACKUP_FILE = os.path.join(BASE_DIR, "sensitive_words.txt.bak")
OUTPUT_FILE = os.path.join(BASE_DIR, "sensitive_words.txt")  # 覆盖原文件
TEMP_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "sensitive_words_merge")

# konsheng/Sensitive-lexicon Vocabulary 目录 (17个文件)
KONSHENG_FILES = [
    "COVID-19词库.txt",
    "GFW补充词库.txt",
    "其他词库.txt",
    "反动词库.txt",
    "广告类型.txt",
    "政治类型.txt",
    "新思想启蒙.txt",
    "暴恐词库.txt",
    "民生词库.txt",
    "涉枪涉爆.txt",
    "网易前端过滤敏感词库.txt",
    "色情类型.txt",
    "色情词库.txt",
    "补充词库.txt",
    "贪腐词库.txt",
    "零时-Tencent.txt",
    "非法网址.txt",
]
KONSHENG_BASE = "https://raw.githubusercontent.com/konsheng/Sensitive-lexicon/main/Vocabulary/"

# houbb/sensitive-word-data
HOUBB_BASE = "https://raw.githubusercontent.com/houbb/sensitive-word-data/main/src/main/resources/"
HOUBB_FILES = {
    "sensitive_word_dict.txt": "normal",        # 每行一个词
    "sensitive_word_deny.txt": "normal",         # 每行一个词
    "sensitive_word_dict_en.txt": "normal",     # 英文词库, 每行一个词
    "sensitive_word_allow.txt": "whitelist",    # 白名单 (反向过滤)
    "sensitive_word_tags.txt": "tags",          # 格式: "词 tag1,tag2"
}


# ============================================================
# 下载函数
# ============================================================

def download_file(url, local_path):
    """下载文件到本地"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(local_path, "wb") as f:
                f.write(data)
        return True, len(data)
    except Exception as e:
        print(f"  [FAIL] {url}: {e}")
        return False, 0


def download_all():
    """下载所有开源词库文件"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    stats = {}

    # 下载 konsheng 文件
    print("=" * 60)
    print("[1/2] 下载 konsheng/Sensitive-lexicon (MIT License)")
    print("=" * 60)
    konsheng_dir = os.path.join(TEMP_DIR, "konsheng")
    os.makedirs(konsheng_dir, exist_ok=True)
    stats["konsheng"] = {}

    for filename in KONSHENG_FILES:
        # URL 编码中文文件名
        encoded = urllib.parse.quote(filename)
        url = KONSHENG_BASE + encoded
        local_path = os.path.join(konsheng_dir, filename)
        print(f"  下载: {filename} ...", end=" ")
        ok, size = download_file(url, local_path)
        if ok:
            # 统计行数
            with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                lines = sum(1 for line in f if line.strip())
            stats["konsheng"][filename] = {"size": size, "lines": lines}
            print(f"OK ({size:,} bytes, {lines:,} lines)")
        else:
            stats["konsheng"][filename] = {"size": 0, "lines": 0}

    # 下载 houbb 文件
    print()
    print("=" * 60)
    print("[2/2] 下载 houbb/sensitive-word-data (Apache 2.0 License)")
    print("=" * 60)
    houbb_dir = os.path.join(TEMP_DIR, "houbb")
    os.makedirs(houbb_dir, exist_ok=True)
    stats["houbb"] = {}

    for filename, file_type in HOUBB_FILES.items():
        url = HOUBB_BASE + filename
        local_path = os.path.join(houbb_dir, filename)
        print(f"  下载: {filename} ({file_type}) ...", end=" ")
        ok, size = download_file(url, local_path)
        if ok:
            with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                lines = sum(1 for line in f if line.strip())
            stats["houbb"][filename] = {"size": size, "lines": lines, "type": file_type}
            print(f"OK ({size:,} bytes, {lines:,} lines)")
        else:
            stats["houbb"][filename] = {"size": 0, "lines": 0, "type": file_type}

    return stats


# ============================================================
# 合并去重
# ============================================================

def load_words_normal(filepath):
    """普通格式: 每行一个词"""
    words = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            word = line.strip()
            if word:
                words.append(word)
    return words


def load_words_tags(filepath):
    """tags 格式: '词 tag1,tag2' -> 只取词部分"""
    words = []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 按空格分割, 取第一个字段
            parts = line.split(None, 1)  # split on whitespace, max 1 split
            if parts:
                word = parts[0].strip()
                if word:
                    words.append(word)
    return words


def merge_words(download_stats):
    """合并所有词库, 去重"""
    print()
    print("=" * 60)
    print("合并去重")
    print("=" * 60)

    # 使用 OrderedDict 保持插入顺序 (Python 3.7+ dict 也保持顺序)
    all_words = OrderedDict()
    source_stats = {}

    # 1. 加载原始词库
    print(f"\n[基础] 读取现有词库: {ORIGINAL_FILE}")
    original_words = load_words_normal(ORIGINAL_FILE)
    for w in original_words:
        if w not in all_words:
            all_words[w] = "original"
    source_stats["original"] = {"new": len(original_words), "total": len(all_words)}
    print(f"  原始词库: {len(original_words):,} 词")

    # 2. 加载 konsheng 文件
    konsheng_dir = os.path.join(TEMP_DIR, "konsheng")
    konsheng_new = 0
    for filename in KONSHENG_FILES:
        filepath = os.path.join(konsheng_dir, filename)
        if not os.path.exists(filepath):
            continue
        words = load_words_normal(filepath)
        file_new = 0
        for w in words:
            if w not in all_words:
                all_words[w] = f"konsheng/{filename}"
                file_new += 1
                konsheng_new += 1
        if file_new > 0:
            print(f"  [konsheng] {filename}: +{file_new:,} 新词")
    source_stats["konsheng"] = {"new": konsheng_new, "total": len(all_words)}
    print(f"  konsheng 小计: +{konsheng_new:,} 新词")

    # 3. 加载 houbb 文件
    houbb_dir = os.path.join(TEMP_DIR, "houbb")
    houbb_new = 0
    houbb_tags_new = 0
    for filename, file_type in HOUBB_FILES.items():
        filepath = os.path.join(houbb_dir, filename)
        if not os.path.exists(filepath):
            continue

        if file_type == "whitelist":
            # 白名单单独处理, 不加入 all_words
            continue
        elif file_type == "tags":
            words = load_words_tags(filepath)
        else:
            words = load_words_normal(filepath)

        file_new = 0
        for w in words:
            if w not in all_words:
                all_words[w] = f"houbb/{filename}"
                file_new += 1
                houbb_new += 1
                if file_type == "tags":
                    houbb_tags_new += 1
        if file_new > 0:
            print(f"  [houbb] {filename} ({file_type}): +{file_new:,} 新词")
    source_stats["houbb"] = {"new": houbb_new, "total": len(all_words)}
    print(f"  houbb 小计: +{houbb_new:,} 新词 (其中 tags 提取: +{houbb_tags_new:,})")

    # 4. 白名单过滤
    whitelist_path = os.path.join(houbb_dir, "sensitive_word_allow.txt")
    whitelist_removed = 0
    if os.path.exists(whitelist_path):
        whitelist_words = load_words_normal(whitelist_path)
        whitelist_set = set(whitelist_words)
        print(f"\n[白名单] 读取 houbb allow 词库: {len(whitelist_words):,} 词")
        before = len(all_words)
        # 从 all_words 中删除白名单中的词
        to_remove = [w for w in all_words if w in whitelist_set]
        for w in to_remove:
            del all_words[w]
            whitelist_removed += 1
        print(f"  白名单过滤: 移除 {whitelist_removed:,} 词")
        source_stats["whitelist"] = {"removed": whitelist_removed, "total": len(all_words)}
    else:
        print("\n[白名单] 未找到, 跳过")

    # 5. 最终统计
    final_count = len(all_words)
    total_new = final_count - len(original_words)
    print()
    print("=" * 60)
    print("合并结果")
    print("=" * 60)
    print(f"  原始词库:   {len(original_words):>10,} 词")
    print(f"  konsheng新增: {konsheng_new:>10,} 词")
    print(f"  houbb新增:    {houbb_new:>10,} 词")
    print(f"  白名单移除:   {whitelist_removed:>10,} 词")
    print(f"  ─────────────────────────")
    print(f"  最终总计:   {final_count:>10,} 词 (净增 {total_new:,})")

    return list(all_words.keys()), source_stats


# ============================================================
# 写入文件
# ============================================================

def write_output(words):
    """写入合并后的文件 (UTF-8 无 BOM, Unix 换行符)"""
    print()
    print("=" * 60)
    print(f"写入文件: {OUTPUT_FILE}")
    print("=" * 60)

    # 写入: UTF-8 无 BOM, Unix 换行符 (\n)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        for word in words:
            f.write(word + "\n")

    # 验证写入
    file_size = os.path.getsize(OUTPUT_FILE)
    with open(OUTPUT_FILE, "rb") as f:
        first_bytes = f.read(3)
    has_bom = first_bytes == b"\xef\xbb\xbf"

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        line_count = sum(1 for line in f if line.strip())

    print(f"  文件大小:   {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    print(f"  总行数:     {line_count:,}")
    print(f"  编码:       UTF-8 {'有BOM [FAIL]' if has_bom else '无BOM [OK]'}")

    # 检查换行符
    with open(OUTPUT_FILE, "rb") as f:
        content = f.read()
    has_crlf = b"\r\n" in content
    print(f"  换行符:     {'CRLF [FAIL]' if has_crlf else 'LF (Unix) [OK]'}")

    # 检查重复
    word_set = set()
    dup_count = 0
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w in word_set:
                dup_count += 1
            else:
                word_set.add(w)
    print(f"  重复词:     {dup_count} {'[FAIL]' if dup_count > 0 else '[OK]'}")

    return line_count, dup_count, has_bom, has_crlf


# ============================================================
# 备份
# ============================================================

def backup_original():
    """备份原始文件"""
    if os.path.exists(ORIGINAL_FILE):
        shutil.copy2(ORIGINAL_FILE, BACKUP_FILE)
        print(f"[备份] {ORIGINAL_FILE} -> {BACKUP_FILE}")
    else:
        print(f"[警告] 原始文件不存在: {ORIGINAL_FILE}")


# ============================================================
# 主函数
# ============================================================

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        敏感词库合并去重工具 V1.1                         ║")
    print("║        开源来源: konsheng + houbb                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # 1. 下载
    download_stats = download_all()

    # 2. 备份
    print()
    print("=" * 60)
    print("备份原始文件")
    print("=" * 60)
    backup_original()

    # 3. 合并去重
    merged_words, merge_stats = merge_words(download_stats)

    # 4. 写入
    line_count, dup_count, has_bom, has_crlf = write_output(merged_words)

    # 5. 最终报告
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    ✅ 合并完成                           ║")
    print(f"║  最终词数: {line_count:>10,}                              ║")
    print(f"║  重复词:   {dup_count:>10}                                ║")
    print(f"║  编码:     {'UTF-8 BOM ❌' if has_bom else 'UTF-8 ✅'}                              ║")
    print(f"║  换行符:   {'CRLF ❌' if has_crlf else 'LF ✅'}                                ║")
    print("╚══════════════════════════════════════════════════════════╝")

    return 0


if __name__ == "__main__":
    sys.exit(main())
