#!/usr/bin/env python3
"""Тест: поиск рифм к слову на полном индексе."""
import json
from pathlib import Path
from phonetic_scorer import score_phonemes, theoretical_max


INDEX = Path.home() / "models/phoneme_index_v2.json"

print("Загружаем индекс (396 МБ, ~30 сек)...")
with open(INDEX, encoding="utf-8") as f:
    index = json.load(f)
print(f"Загружено: {len(index)} записей\n")


def find_rhymes(query, topn=15):
    if query not in index:
        print(f"  {query!r} НЕТ в индексе")
        return

    req_entry = index[query]
    req_ph = req_entry["phonemes"]
    max_score = theoretical_max(req_ph)

    print(f"=== {query} → {req_entry['ascii']} ({req_entry['syllables']} слогов) ===")
    print(f"  Максимум: {max_score}")

    results = []
    for cand, entry in index.items():
        if cand == query:
            continue
        if entry.get("kind") == "word_navec" and not cand.isalpha():
            continue
        if entry["syllables"] != req_entry["syllables"]:
            continue
        cand_ph = entry["phonemes"]
        score, details = score_phonemes(req_ph, cand_ph, mode="A")
        if score is None or score <= 0:
            continue
        pct = score / max_score * 100 if max_score else 0
        results.append((cand, score, pct, entry["ascii"]))

    results.sort(key=lambda x: -x[1])
    for cand, score, pct, ascii_s in results[:topn]:
        print(f"  {cand:<15} {ascii_s:<25} {score:>5} ({pct:.0f}%)")
    print()


for word in ["чилить", "вайб", "кринж", "пилить", "красивый", "думать"]:
    find_rhymes(word)
