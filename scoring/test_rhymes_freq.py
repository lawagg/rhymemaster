#!/usr/bin/env python3
"""Поиск рифм с учётом частотности и дедупликацией."""
import json
import re
from pathlib import Path
from phonetic_scorer_v2 import score_phonemes, theoretical_max

BASE = Path.home() / "models"
INDEX = BASE / "phoneme_index_v2.json"
FREQ = BASE / "ru_50k.txt"

MIN_FREQ = 5


def load_frequencies():
    freq = {}
    with open(FREQ, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    freq[parts[0]] = int(parts[1])
                except ValueError:
                    continue
    return freq


def sound_key(phonemes):
    """Ключ: ударная гласная + 2 согласных после неё."""
    vowels = [p for p in phonemes if p["type"] == "vowel"]
    if not vowels:
        return None
    stressed_idx = next((i for i, p in enumerate(vowels) if p.get("stressed")), None)
    if stressed_idx is None:
        stressed_idx = 0
    key = [vowels[stressed_idx]["symbol"]]
    cons_after = 0
    for p in phonemes:
        if p["type"] == "consonant":
            pass
    stressed_phon_idx = None
    for i, p in enumerate(phonemes):
        if p["type"] == "vowel" and p.get("stressed"):
            stressed_phon_idx = i
            break
    if stressed_phon_idx is None:
        for i, p in enumerate(phonemes):
            if p["type"] == "vowel":
                stressed_phon_idx = i
                break
    if stressed_phon_idx is not None:
        for p in phonemes[stressed_phon_idx+1:]:
            if p["type"] == "consonant":
                key.append(p["symbol"])
                cons_after += 1
                if cons_after >= 2:
                    break
    return "".join(key)


def main():
    print("Загружаем индекс...")
    with open(INDEX, encoding="utf-8") as f:
        index = json.load(f)
    print(f"  {len(index)} записей")

    print("Загружаем частотный словарь...")
    freq = load_frequencies()
    print(f"  {len(freq)} слов")

    print()

    def find(query, topn=15):
        if query not in index:
            print(f"  {query!r} нет")
            return
        req_ph = index[query]["phonemes"]
        max_score = theoretical_max(req_ph, mode="A")
        req_syll = index[query]["syllables"]

        results = []
        for cand, entry in index.items():
            if cand == query:
                continue
            if not re.fullmatch(r"[а-яё]{4,20}", cand):
                continue
            if entry["syllables"] != req_syll:
                continue
            cand_freq = freq.get(cand, 0)
            if cand_freq < MIN_FREQ:
                continue
            score, details = score_phonemes(req_ph, entry["phonemes"], mode="A")
            if score is None:
                continue
            pct = min(score / max_score * 100, 100) if max_score else 0
            results.append({
                "word": cand,
                "score": score,
                "pct": pct,
                "ascii": entry["ascii"],
                "freq": cand_freq,
                "key": sound_key(entry["phonemes"]),
            })

        # Дедупликация: только точные омофоны (одинаковый ascii)
        best_by_ascii = {}
        for r in results:
            a = r["ascii"]
            if a not in best_by_ascii or r["freq"] > best_by_ascii[a]["freq"]:
                best_by_ascii[a] = r

        deduped = sorted(best_by_ascii.values(), key=lambda x: (-x["score"], -x["freq"]))

        print(f"=== {query} -> {index[query]['ascii']} ===")
        print(f"  Максимум: {max_score}")
        for r in deduped[:topn]:
            print(f"  {r['word']:<15} {r['ascii']:<22} {r['score']:>4} ({r['pct']:.0f}%) freq={r['freq']}")
        print()

    find("чилить")
    find("вайб")
    find("кринж")
    find("красивый")


if __name__ == "__main__":
    main()
