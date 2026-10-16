#!/usr/bin/env python3
"""Фонетический скоринг (раздел 2.2 ТЗ)."""
import json
from pathlib import Path


WEIGHTS = {
    "consonant_exact": 100,
    "consonant_variant": 100,
    "voiced_pair": 70,
    "sibilant_pair": 70,
    "special_pair": 60,
    "sonorant_match": 60,
    "close_variant": 50,
    "consonant_miss": -30,

    "press_multiplier": 1.5,
    "non_press_multiplier": 0.7,

    "vowel_match": 100,
    "vowel_mismatch_studio": -150,
    "stress_position_mismatch": -80,   # НОВОЕ: штраф за несовпадение позиции ударной

    "lcs_per_element": 15,
    "lcs_max": 60,
}


VOICED_PAIRS = {
    frozenset(["b", "p"]),
    frozenset(["d", "t"]),
    frozenset(["v", "f"]),
    frozenset(["g", "k"]),
}
SIBILANT_PAIRS = {frozenset(["z", "s"])}
SPECIAL_PAIRS = {
    frozenset(["ch", "sch"]),
    frozenset(["sh", "sch"]),
    frozenset(["zh", "sh"]),
    frozenset(["f", "h"]),
}
SONORANTS = {"r", "l", "m", "n"}

VARIANT_FAMILIES = [
    {"c", "ts", "ks", "ps", "bs", "rs", "ns", "zs", "ss", "hs", "fs", "vs", "ls", "ds", "ms", "gs"},
    {"c", "tz", "kz", "pz", "bz", "rz", "nz", "zz", "sz", "hz", "fz", "vz", "lz", "dz", "mz", "gz"},
]
VARIANT_FULL = VARIANT_FAMILIES[0]
VARIANT_CLOSE = VARIANT_FAMILIES[1]


def mark_press_consonants(phonemes):
    for i, ph in enumerate(phonemes):
        if ph.get("type") != "consonant":
            continue
        for j in range(i + 1, len(phonemes)):
            if phonemes[j].get("type") == "vowel":
                if phonemes[j].get("stressed"):
                    ph["press"] = True
                break
            if phonemes[j].get("type") == "consonant" and j > i + 2:
                break
    if phonemes and phonemes[0].get("type") == "consonant":
        phonemes[0]["press"] = True


def score_consonants(c1, c2):
    s1, s2 = c1["symbol"], c2["symbol"]
    if s1 == s2:
        return WEIGHTS["consonant_exact"]
    pair = frozenset([s1, s2])
    if pair in VOICED_PAIRS:
        return WEIGHTS["voiced_pair"]
    if pair in SIBILANT_PAIRS:
        return WEIGHTS["sibilant_pair"]
    if pair in SPECIAL_PAIRS:
        return WEIGHTS["special_pair"]
    if s1 in SONORANTS and s2 in SONORANTS:
        return WEIGHTS["sonorant_match"]
    if s1 in VARIANT_FULL and s2 in VARIANT_FULL:
        return WEIGHTS["consonant_variant"]
    if s1 in VARIANT_CLOSE and s2 in VARIANT_CLOSE:
        return WEIGHTS["close_variant"]
    return 0


ARTICULATION = {
    "b": "C", "p": "C", "d": "C", "t": "C", "g": "C", "k": "C",
    "f": "Щ", "v": "Щ", "s": "Щ", "z": "Щ", "sh": "Щ", "zh": "Щ", "h": "Щ",
    "c": "А", "ch": "А",
    "m": "Р", "n": "Р", "l": "Р", "r": "Р",
    "j": "Р",
}


def articulation_sequence(consonants):
    return [ARTICULATION[c["symbol"]] for c in consonants if c["symbol"] in ARTICULATION]


def lcs_length(a, b):
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]


def cluster_bonus(req_consonants, cand_consonants):
    req_seq = articulation_sequence(req_consonants)
    cand_seq = articulation_sequence(cand_consonants)
    if not req_seq:
        return 0
    lcs = lcs_length(req_seq, cand_seq)
    return min(lcs * WEIGHTS["lcs_per_element"], WEIGHTS["lcs_max"])


def score_phonemes(req_phonemes, cand_phonemes, mode="A"):
    """
    mode: 'A' — простая форма (несовпадение ударной → дисквалификация)
          'B' — студия (несовпадение ударной → штраф)
    Возвращает (score, details) или (None, details) если дисквалифицирован.
    """
    details = {
        "vowel_score": 0,
        "stress_mismatch": 0,
        "consonant_score": 0,
        "cluster_bonus": 0,
        "miss_penalty": 0,
        "disqualified": False,
    }

    req = [dict(p) for p in req_phonemes]
    cand = [dict(p) for p in cand_phonemes]
    mark_press_consonants(req)
    mark_press_consonants(cand)

    req_vowels = [p for p in req if p["type"] == "vowel"]
    cand_vowels = [p for p in cand if p["type"] == "vowel"]

    # === 1. ГЛАСНЫЕ: сравнение типа на ударной позиции запроса ===
    req_stressed_idx = next((i for i, p in enumerate(req_vowels) if p.get("stressed")), None)
    cand_stressed_idx = next((i for i, p in enumerate(cand_vowels) if p.get("stressed")), None)

    # Если в запросе нет ударной (односложное) — считаем позицию 0
    if req_stressed_idx is None:
        req_stressed_idx = 0

    if req_vowels:
        if req_stressed_idx < len(cand_vowels):
            req_stressed = req_vowels[req_stressed_idx]
            cand_at_pos = cand_vowels[req_stressed_idx]
            if req_stressed["symbol"] == cand_at_pos["symbol"]:
                details["vowel_score"] = WEIGHTS["vowel_match"]
            else:
                if mode == "A":
                    details["disqualified"] = True
                    return None, details
                else:
                    details["vowel_score"] = WEIGHTS["vowel_mismatch_studio"]
        else:
            if mode == "A":
                details["disqualified"] = True
                return None, details
            else:
                details["vowel_score"] = WEIGHTS["vowel_mismatch_studio"]

    # === 2. НОВОЕ: ШТРАФ ЗА НЕСОВПАДЕНИЕ ПОЗИЦИЙ УДАРНЫХ ===
    # Если у кандидата ударная на другой позиции, чем у запроса
    if req_stressed_idx is not None and cand_stressed_idx is not None:
        if req_stressed_idx != cand_stressed_idx:
            details["stress_mismatch"] = WEIGHTS["stress_position_mismatch"]

    # === 3. СОГЛАСНЫЕ (аллитерация) ===
    req_cons = [p for p in req if p["type"] == "consonant"]
    cand_cons = [p for p in cand if p["type"] == "consonant"]

    con_score = 0
    used_cand = [False] * len(cand_cons)

    for rc in req_cons:
        best = 0
        best_idx = -1
        for i, cc in enumerate(cand_cons):
            if used_cand[i]:
                continue
            s = score_consonants(rc, cc)
            if s > best:
                best = s
                best_idx = i
        if best_idx >= 0 and best > 0:
            used_cand[best_idx] = True
            press = rc.get("press", False) or cand_cons[best_idx].get("press", False)
            mult = WEIGHTS["press_multiplier"] if press else WEIGHTS["non_press_multiplier"]
            con_score += int(best * mult)

    misses = abs(len(req_cons) - len(cand_cons))
    details["miss_penalty"] = misses * WEIGHTS["consonant_miss"]
    details["consonant_score"] = con_score

    # === 4. БОНУС ЗА КЛАСТЕР ===
    details["cluster_bonus"] = cluster_bonus(req_cons, cand_cons)

    # === ИТОГО ===
    total = (details["vowel_score"]
             + details["stress_mismatch"]
             + details["consonant_score"]
             + details["cluster_bonus"]
             + details["miss_penalty"])

    return total, details


def theoretical_max(req_phonemes):
    vowels = sum(1 for p in req_phonemes if p["type"] == "vowel")
    consonants = sum(1 for p in req_phonemes if p["type"] == "consonant")
    return vowels * WEIGHTS["vowel_match"] + consonants * WEIGHTS["consonant_exact"]


if __name__ == "__main__":
    INDEX = Path.home() / "models/phoneme_index_v2.json"
    with open(INDEX, encoding="utf-8") as f:
        index = json.load(f)

    print(f"Индекс загружен: {len(index)} записей\n")

    def test(req, cand_list):
        if req not in index:
            print(f"  {req!r} нет в индексе")
            return
        req_ph = index[req]["phonemes"]
        print(f"=== Запрос: {req} ({index[req]['ascii']}) ===")
        print(f"  Теоретический максимум: {theoretical_max(req_ph)}")
        results = []
        for cand in cand_list:
            if cand not in index:
                continue
            cand_ph = index[cand]["phonemes"]
            score, details = score_phonemes(req_ph, cand_ph, mode="A")
            if score is None:
                continue
            max_score = theoretical_max(req_ph)
            pct = (score / max_score * 100) if max_score else 0
            results.append((cand, score, pct, index[cand]["ascii"]))
        results.sort(key=lambda x: -x[1])
        for cand, score, pct, ascii_s in results[:10]:
            print(f"  {cand:<20} {ascii_s:<25} балл={score:>5} ({pct:.0f}%)")
        print()

    test("чилить", ["пилить", "делить", "белить", "пылить", "шалить"])
    test("вайб", ["хайп", "лайк", "край", "тип"])
    test("кринж", ["шприц", "принц", "принт"])
