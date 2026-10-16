#!/usr/bin/env python3
"""Поиск рифм v5: словари + корневой фильтр + дедуп форм + Navec off."""
import json
import re
from pathlib import Path

try:
    import pymorphy3
except ImportError:
    print("Нет pymorphy3. Установи: pip install pymorphy3")
    raise

from phonetic_scorer_v2 import score_phonemes

BASE = Path.home() / "models"
INDEX = BASE / "phoneme_index_v2.json"
FREQ_COMMON = BASE / "ru_50k.txt"
SLANG_FILE = BASE / "slang_datasets/unified_slang_clean.json"
STOPWORDS_FILE = BASE / "stopwords_names.txt"

# === Флаги словарей ===
USE_COMMON = True        # ru_50k.txt
USE_SLANG = True         # сленг без мата
USE_PROFANITY = False    # группа "мат"
USE_NAVEC_EXT = False    # Navec-пласт (500k слов, много имён и шума)

# === Флаги фильтрации ===
SKIP_SAME_LEMMA = True   # одна лемма — стоп (ТЗ 2.4)
SKIP_SAME_ROOT = True    # общий корень (первые 4 символа леммы)
APPLY_STOPWORDS = True   # стоп-лист имён/мусора
DEDUP_BY_LEMMA = True    # в выдаче одна форма на лемму

SLANG_DEFAULT_FREQ = 50
PROFANITY_DEFAULT_FREQ = 10
ROOT_LEN = 4


def load_common():
    freq = {}
    with open(FREQ_COMMON, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    freq[parts[0]] = int(parts[1])
                except ValueError:
                    continue
    return freq


def load_slang_and_profanity():
    slang, profanity = set(), set()
    with open(SLANG_FILE, encoding="utf-8") as f:
        data = json.load(f)
    for w, v in data.items():
        w_low = w.lower()
        if v.get("group") == "мат":
            profanity.add(w_low)
        else:
            slang.add(w_low)
    return slang, profanity


def load_stopwords():
    words = set()
    if not STOPWORDS_FILE.exists():
        return words
    with open(STOPWORDS_FILE, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w and not w.startswith("#"):
                words.add(w)
    return words


def build_vocabulary(common, slang, profanity):
    vocab = {}
    if USE_COMMON:
        for w, f in common.items():
            vocab[w] = f
    if USE_SLANG:
        for w in slang:
            vocab.setdefault(w, SLANG_DEFAULT_FREQ)
    if USE_PROFANITY:
        for w in profanity:
            vocab.setdefault(w, PROFANITY_DEFAULT_FREQ)
    return vocab


def main():
    print("Загружаем индекс...")
    with open(INDEX, encoding="utf-8") as f:
        index = json.load(f)
    print(f"  {len(index)} записей")

    print("Загружаем словари...")
    common = load_common()
    slang, profanity = load_slang_and_profanity()
    vocab = build_vocabulary(common, slang, profanity)
    stopwords = load_stopwords()

    morph = pymorphy3.MorphAnalyzer()
    lemma_cache = {}
    def lemma(word):
        if word in lemma_cache:
            return lemma_cache[word]
        try:
            r = morph.parse(word)[0].normal_form
        except Exception:
            r = word
        lemma_cache[word] = r
        return r

    def root(word):
        return lemma(word)[:ROOT_LEN]

    print(f"  ru_50k:                    {len(common)}")
    print(f"  сленг (без мата):          {len(slang)}")
    print(f"  мат:                       {len(profanity)}")
    print(f"  стоп-лист:                 {len(stopwords)}")
    print(f"  словарь валидных слов:     {len(vocab)}")
    print(f"  флаги: common={USE_COMMON} slang={USE_SLANG} "
          f"profanity={USE_PROFANITY} navec_ext={USE_NAVEC_EXT}")
    print(f"         skip_lemma={SKIP_SAME_LEMMA} skip_root={SKIP_SAME_ROOT} "
          f"stopwords={APPLY_STOPWORDS} dedup_lemma={DEDUP_BY_LEMMA}")
    print()

    def find(query, topn=15):
        if query not in index:
            print(f"  {query!r} нет в индексе")
            return
        req_ph = index[query]["phonemes"]
        max_score, _ = score_phonemes(req_ph, req_ph, mode="A")
        req_syll = index[query]["syllables"]
        req_lemma = lemma(query)
        req_root = req_lemma[:ROOT_LEN]

        results = []
        for cand, entry in index.items():
            if cand == query:
                continue
            if not re.fullmatch(r"[а-яё]{4,20}", cand):
                continue
            if entry["syllables"] != req_syll:
                continue
            if not USE_NAVEC_EXT and entry.get("kind") == "word_navec":
                continue
            if cand not in vocab:
                continue
            if APPLY_STOPWORDS and cand in stopwords:
                continue
            cand_lemma = lemma(cand)
            if SKIP_SAME_LEMMA and cand_lemma == req_lemma:
                continue
            if SKIP_SAME_ROOT and cand_lemma[:ROOT_LEN] == req_root:
                continue
            score, details = score_phonemes(req_ph, entry["phonemes"], mode="A")
            if score is None:
                continue
            pct = min(score / max_score * 100, 100) if max_score else 0
            results.append({
                "word": cand, "score": score, "pct": pct,
                "ascii": entry["ascii"], "freq": vocab[cand],
                "lemma": cand_lemma,
            })

        # Дедуп по ascii
        best_by_ascii = {}
        for r in results:
            a = r["ascii"]
            if a not in best_by_ascii or r["freq"] > best_by_ascii[a]["freq"]:
                best_by_ascii[a] = r
        stage1 = list(best_by_ascii.values())

        # Дедуп по лемме (одна форма на лемму)
        if DEDUP_BY_LEMMA:
            best_by_lemma = {}
            for r in stage1:
                l = r["lemma"]
                if l not in best_by_lemma or r["score"] > best_by_lemma[l]["score"]:
                    best_by_lemma[l] = r
            stage2 = list(best_by_lemma.values())
        else:
            stage2 = stage1

        deduped = sorted(stage2, key=lambda x: (-x["score"], -x["freq"]))

        print(f"=== {query} -> {index[query]['ascii']} ===")
        print(f"  Максимум: {max_score}  Кандидатов: {len(deduped)}")
        for r in deduped[:topn]:
            print(f"  {r['word']:<15} {r['ascii']:<22} {r['score']:>4} ({r['pct']:.0f}%) freq={r['freq']}")
        print()

    find("чилить")
    find("вайб")
    find("кринж")
    find("красивый")


if __name__ == "__main__":
    main()
