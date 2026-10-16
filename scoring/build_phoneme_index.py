#!/usr/bin/env python3
"""Пре-компьютинг фонем для корпуса. Запуск: python build_phoneme_index.py"""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
import re
from pathlib import Path

BASE = Path.home() / "models"
OUT = BASE / "phoneme_index.json"
PROGRESS = BASE / "phoneme_index_progress.json"

from g2p import G2P
from ipa_to_ascii import IpaToAscii


def load_json(path):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize(text):
    text = text.lower().strip()
    text = re.sub(r"[^а-яё\s\-]", "", text)
    return text


def clean_ipa_string(ipa):
    """Убирает <DELETE> и лишние символы из IPA-строки."""
    if not ipa:
        return ""
    ipa = ipa.replace("<DELETE>", " ")
    ipa = re.sub(r"[<>]", " ", ipa)
    return ipa.strip()


def parse_to_phonemes(converter, ipa_str):
    """Парсит IPA-строку в чистые фонемы (только vowel/consonant)."""
    ipa_str = clean_ipa_string(ipa_str)
    phonemes = converter.parse_ipa(ipa_str)
    clean = []
    for ph in phonemes:
        t = ph.get("type", "")
        if t not in ("vowel", "consonant"):
            continue
        clean.append({
            "type": t,
            "symbol": ph.get("symbol", ""),
            "stressed": bool(ph.get("stressed", False)),
            "soft": bool(ph.get("soft", False)),
        })
    return clean


def build_entry(converter, phonemes, kind, group=""):
    """Собирает запись индекса из списка фонем."""
    ascii_str = converter.to_ascii_string(phonemes, mark_soft=False)
    return {
        "kind": kind,
        "phonemes": phonemes,
        "syllables": sum(1 for p in phonemes if p["type"] == "vowel"),
        "ascii": ascii_str,
        "group": group,
    }


def save_progress(index, done_words, done_phrases):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump({
            "words_done": done_words,
            "phrases_done": done_phrases,
            "index_size": len(index),
        }, f, ensure_ascii=False)


def extract_parts(raw):
    """Из сырого вывода модели достаёт IPA-строку."""
    parts = raw.split("\t")
    ipa = parts[0] if len(parts) > 0 else ""
    ipa_borders = parts[2] if len(parts) > 2 else ""
    return ipa, ipa_borders


def main():
    print("Загружаем G2P модель...")
    g2p = G2P()
    converter = IpaToAscii()
    print("G2P готов\n")

    index = {}

    # === 1. Слова сленга ===
    slang = load_json(BASE / "slang_datasets/unified_slang_clean.json")
    print(f"Слов сленга: {len(slang)}")
    words_list = list(slang.keys())

    BATCH = 50
    for i in range(0, len(words_list), BATCH):
        batch = words_list[i:i + BATCH]
        normalized = [normalize(w) for w in batch]
        prepared = [g2p.prepare_input(n) for n in normalized if n]
        if not prepared:
            continue
        try:
            results = g2p.model._infer(prepared)
        except Exception as e:
            print(f"  ошибка батча {i}: {e}")
            continue

        for j, raw in enumerate(results):
            if j >= len(batch):
                break
            word = batch[j].lower().strip()
            ipa, ipa_borders = extract_parts(raw)
            phonemes = parse_to_phonemes(converter, ipa_borders)
            if not phonemes:
                phonemes = parse_to_phonemes(converter, ipa)
            entry = build_entry(converter, phonemes, "word",
                                group=slang[word].get("group", ""))
            entry["ipa"] = clean_ipa_string(ipa)
            index[word] = entry

        if i % 1000 == 0 and i > 0:
            print(f"  слов: {i}/{len(words_list)}")
            save_progress(index, i, 0)

    print(f"  слов обработано: {len(index)}")
    save_progress(index, len(words_list), 0)

    # === 2. Фразы orator ===
    phrase_sources = [
        ("krylatye", BASE / "slang_datasets/orator/orator_ready.json"),
        ("poslovicy", BASE / "slang_datasets/orator/poslovicy.json"),
        ("aforizmy", BASE / "slang_datasets/orator/aforizmy.json"),
    ]

    for kind, path in phrase_sources:
        data = load_json(path)
        if not data:
            continue

        flat = []
        for key, val in data.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and 3 < len(item) < 300:
                        flat.append(item)
            elif isinstance(val, str):
                if 3 < len(val) < 300:
                    flat.append(val)

        print(f"\n{kind}: {len(flat)} фраз")

        for i in range(0, len(flat), BATCH):
            batch = flat[i:i + BATCH]
            for text in batch:
                key = normalize(text)
                if not key or key in index:
                    continue
                prepared = g2p.prepare_input(text)
                if not prepared:
                    continue
                try:
                    results = g2p.model._infer([prepared])
                except Exception:
                    continue
                if not results:
                    continue
                ipa, ipa_borders = extract_parts(results[0])
                phonemes = parse_to_phonemes(converter, ipa_borders)
                if not phonemes:
                    phonemes = parse_to_phonemes(converter, ipa)
                entry = build_entry(converter, phonemes, kind)
                entry["ipa"] = clean_ipa_string(ipa)
                index[key] = entry

            if i % 1000 == 0 and i > 0:
                print(f"  {kind}: {i}/{len(flat)}")
                save_progress(index, len(words_list), i)

    print(f"\n=== ИТОГ ===")
    print(f"Всего записей в индексе: {len(index)}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    if PROGRESS.exists():
        PROGRESS.unlink()

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"Сохранено: {OUT}")
    print(f"Размер: {size_mb:.1f} МБ")


if __name__ == "__main__":
    main()
