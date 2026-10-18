#!/usr/bin/env python3
"""Добавляет недостающие слова в phoneme_index_v2.json."""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
import re
import shutil
from pathlib import Path

BASE = Path.home() / "models"
INDEX = BASE / "phoneme_index_v2.json"
BACKUP = BASE / "phoneme_index_v2.json.bak"
WORK = Path("/mnt/c/Users/admin/Documents/rhymemaster_work")
FILES = [WORK / "to_add_v2_401.txt"]

from g2p import G2P
from ipa_to_ascii import IpaToAscii
from build_phoneme_index import (
    normalize, clean_ipa_string, parse_to_phonemes, build_entry, extract_parts
)


def main():
    print(f"Бэкап: {BACKUP}")
    if not BACKUP.exists():
        shutil.copy2(INDEX, BACKUP)
        print("  создан")
    else:
        print("  уже есть, не перезаписываю")

    print("Загружаем индекс...")
    with open(INDEX, encoding="utf-8") as f:
        index = json.load(f)
    print(f"  было: {len(index)}")

    words = []
    for fp in FILES:
        if not fp.exists():
            print(f"  нет файла: {fp}")
            continue
        with open(fp, encoding="utf-8") as f:
            for line in f:
                w = line.strip().lower()
                if w:
                    words.append(w)
    print(f"Слов к добавлению: {len(words)}")

    todo = [w for w in words if w not in index and normalize(w)]
    print(f"Уже в индексе: {len(words) - len(todo)}")
    print(f"К обработке: {len(todo)}")
    print()

    print("Загружаем G2P...")
    g2p = G2P()
    converter = IpaToAscii()
    print("G2P готов\n")

    BATCH = 50
    added, failed = 0, []
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        normalized = [normalize(w) for w in batch]
        prepared = [g2p.prepare_input(n) for n in normalized if n]
        if not prepared:
            failed.extend(batch)
            continue
        try:
            results = g2p.model._infer(prepared)
        except Exception as e:
            print(f"  ошибка батча {i}: {e}")
            failed.extend(batch)
            continue

        for j, raw in enumerate(results):
            if j >= len(batch):
                break
            word = batch[j]
            ipa, ipa_borders = extract_parts(raw)
            phonemes = parse_to_phonemes(converter, ipa_borders)
            if not phonemes:
                phonemes = parse_to_phonemes(converter, ipa)
            if not phonemes:
                failed.append(word)
                continue
            entry = build_entry(converter, phonemes, "word_supp")
            entry["ipa"] = clean_ipa_string(ipa)
            index[word] = entry
            added += 1

        print(f"  {min(i + BATCH, len(todo))}/{len(todo)} — добавлено: {added}")

    print(f"\nСохраняем {INDEX}...")
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    size_mb = INDEX.stat().st_size / 1024 / 1024
    print(f"  было: {len(index) - added}, стало: {len(index)}, размер: {size_mb:.0f} МБ")
    print(f"\n=== ИТОГ ===")
    print(f"добавлено: {added}")
    print(f"не удалось: {len(failed)}")
    if failed:
        print(f"  список: {failed}")

    print(f"\nВыборочная проверка:")
    for w in ["не", "ты", "он", "хмм", "нихера", "зацените"]:
        if w in words and w in index:
            print(f"  {w}: OK {index[w]['syllables']} слогов, ascii={index[w]['ascii']}")
        elif w in words:
            print(f"  {w}: НЕ добавлено")


if __name__ == "__main__":
    main()
