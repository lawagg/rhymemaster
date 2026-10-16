#!/usr/bin/env python3
"""Фонетический скоринг v2 (ТЗ 2.2 + 2.2.1)."""
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

    "unstressed_vowel_bonus": 10,
    "unstressed_vowel_max": 30,

    "lcs_per_element": 15,
    "lcs_max": 60,
}


VOWEL_CLASS = {
    "i": "i", "y": "i",
    "a": "a",
    "o": "o",
    "u": "u",
    "e": "e",
}


def get_vowel_class(symbol):
    return VOWEL_CLASS.get(symbol, symbol)


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

VARIANT_FULL = {"c", "ts", "ks", "ps", "bs", "rs", "ns", "zs", "ss", "hs", "fs", "vs", "ls", "ds", "ms", "gs"}
VARIANT_CLOSE = {"c", "tz", "kz", "pz", "bz", "rz", "nz", "zz", "sz", "hz", "fz", "vz", "lz", "dz", "mz", "gz"}


def base_consonant_score(c1, c2):
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


def apply_press(c1, c2, base_score):
    p1 = c1.get("press", False)
    p2 = c2.get("press", False)
    if p1 and p2:
        return int(base_score * WEIGHTS["press_multiplier"])
    if p1 or p2:
        return int(base_score * 1.0)
    return int(base_score * WEIGHTS["non_press_multiplier"])


def mark_press_A(phonemes):
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


def mark_press(phonemes, mode="A"):
    for p in phonemes:
        p.pop("press", None)
    mark_press_A(phonemes)


def find_stress_position_from_end(vowels):
    idx_from_start = None
    for i, v in enumerate(vowels):
        if v.get("stressed"):
            idx_from_start = i
            break
    if idx_from_start is None:
        if len(vowels) == 1:
            return 1
        return None
    return len(vowels) - idx_from_start


def align_consonants(req_cons, cand_cons):
    m, n = len(req_cons), len(cand_cons)
    if m == 0 and n == 0:
        return 0
    NEG = -100000
    dp = [[NEG] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0
    for i in range(1, m + 1):
        dp[i][0] = dp[i - 1][0] + WEIGHTS["consonant_miss"]
    for j in range(1, n + 1):
        dp[0][j] = dp[0][j - 1] + WEIGHTS["consonant_miss"]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            base = base_consonant_score(req_cons[i - 1], cand_cons[j - 1])
            if base > 0:
                match = apply_press(req_cons[i - 1], cand_cons[j - 1], base)
            else:
                match = WEIGHTS["consonant_miss"]
            dp[i][j] = max(
                dp[i - 1][j - 1] + match,
                dp[i - 1][j] + WEIGHTS["consonant_miss"],
                dp[i][j - 1] + WEIGHTS["consonant_miss"],
            )
    return dp[m][n]


ARTICULATION = {
    "b": "C", "p": "C", "d": "C", "t": "C", "g": "C", "k": "C",
    "f": "Щ", "v": "Щ", "s": "Щ", "z": "Щ", "sh": "Щ", "zh": "Щ", "h": "Щ",
    "c": "А", "ch": "А",
    "m": "Р", "n": "Р", "l": "Р", "r": "Р",
    "j": "Р",
}


def articulation_sequence(consonants):
    seq = []
    for c in consonants:
        t = ARTICULATION.get(c["symbol"])
        if t:
            seq.append(t)
    return seq


def lcs_length(a, b):
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def cluster_bonus(req_cons, cand_cons):
    req_seq = articulation_sequence(req_cons)
    cand_seq = articulation_sequence(cand_cons)
    if not req_seq:
        return 0
    lcs = lcs_length(req_seq, cand_seq)
    return min(lcs * WEIGHTS["lcs_per_element"], WEIGHTS["lcs_max"])


def score_phonemes(req_phonemes, cand_phonemes, mode="A"):
    details = {"disqualified": False, "reason": None}

    req = [dict(p) for p in req_phonemes]
    cand = [dict(p) for p in cand_phonemes]
    mark_press(req, mode)
    mark_press(cand, mode)

    req_vowels = [p for p in req if p["type"] == "vowel"]
    cand_vowels = [p for p in cand if p["type"] == "vowel"]

    if not req_vowels or not cand_vowels:
        details["disqualified"] = True
        details["reason"] = "no_vowels"
        return None, details

    req_pos = find_stress_position_from_end(req_vowels)
    cand_pos = find_stress_position_from_end(cand_vowels)

    if req_pos is None or cand_pos is None:
        details["disqualified"] = True
        details["reason"] = "no_stress"
        return None, details

    if req_pos != cand_pos:
        details["disqualified"] = True
        details["reason"] = "stress_pos"
        return None, details

    req_str_v = None
    for v in req_vowels:
        if v.get("stressed"):
            req_str_v = v
            break
    if req_str_v is None:
        req_str_v = req_vowels[-req_pos] if req_pos <= len(req_vowels) else req_vowels[0]

    cand_str_v = None
    for v in cand_vowels:
        if v.get("stressed"):
            cand_str_v = v
            break
    if cand_str_v is None:
        cand_str_v = cand_vowels[-cand_pos] if cand_pos <= len(cand_vowels) else cand_vowels[0]

    if get_vowel_class(req_str_v["symbol"]) != get_vowel_class(cand_str_v["symbol"]):
        details["disqualified"] = True
        details["reason"] = "vowel_class"
        return None, details

    req_stressed_idx = req.index(req_str_v)
    cand_stressed_idx = cand.index(cand_str_v)

    req_after = [p for p in req[req_stressed_idx + 1:] if p["type"] == "consonant"]
    cand_after = [p for p in cand[cand_stressed_idx + 1:] if p["type"] == "consonant"]

    cons_score = align_consonants(req_after, cand_after)

    req_before = [p for p in req[:req_stressed_idx] if p["type"] == "consonant"]
    cand_before = [p for p in cand[:cand_stressed_idx] if p["type"] == "consonant"]

    before_w = 0.5 if mode == "B" else 1.0
    if req_before and cand_before:
        before_score = align_consonants(req_before, cand_before)
        cons_score += int(before_score * before_w)

    req_unstressed = [v["symbol"] for v in req_vowels if not v.get("stressed")]
    cand_unstressed = [v["symbol"] for v in cand_vowels if not v.get("stressed")]
    matches = 0
    for v in req_unstressed:
        if v in cand_unstressed:
            matches += 1
            cand_unstressed.remove(v)
    unstressed_bonus = min(matches * WEIGHTS["unstressed_vowel_bonus"], WEIGHTS["unstressed_vowel_max"])

    clust = cluster_bonus(req_after, cand_after)

    total = WEIGHTS["vowel_match"] + cons_score + unstressed_bonus + clust
    total = max(total, 0)

    details.update({
        "vowel_class_match": True,
        "stress_position_match": True,
        "consonant_score": cons_score,
        "unstressed_bonus": unstressed_bonus,
        "cluster_bonus": clust,
    })
    return total, details


def theoretical_max(req_phonemes, mode="A"):
    req = [dict(p) for p in req_phonemes]
    mark_press(req, mode)

    stressed_idx = None
    for i, p in enumerate(req):
        if p["type"] == "vowel" and p.get("stressed"):
            stressed_idx = i
            break
    if stressed_idx is None:
        for i, p in enumerate(req):
            if p["type"] == "vowel":
                stressed_idx = i
                break
    if stressed_idx is None:
        return 1

    cons_after = [p for p in req[stressed_idx + 1:] if p["type"] == "consonant"]

    total = WEIGHTS["vowel_match"]
    for c in cons_after:
        if c.get("press"):
            total += int(WEIGHTS["consonant_exact"] * WEIGHTS["press_multiplier"])
        else:
            total += int(WEIGHTS["consonant_exact"] * WEIGHTS["non_press_multiplier"])
    total += WEIGHTS["lcs_max"]
    total += WEIGHTS["unstressed_vowel_max"]
    return total


if __name__ == "__main__":
    INDEX = Path.home() / "models/phoneme_index_v2.json"
    print(f"Загружаем {INDEX}...")
    with open(INDEX, encoding="utf-8") as f:
        index = json.load(f)
    print(f"Загружено: {len(index)} записей\n")

    def test(req, mode="A"):
        if req not in index:
            print(f"  {req!r} нет в индексе")
            return
        req_ph = index[req]["phonemes"]
        max_score = theoretical_max(req_ph, mode=mode)
        print(f"=== {req} -> {index[req]['ascii']} [{mode}] ===")
        print(f"  Максимум: {max_score}")

        results = []
        for cand, entry in index.items():
            if cand == req:
                continue
            if not cand.isalpha():
                continue
            if len(cand) < 4:
                continue
            if entry.get("kind") == "word_navec" and cand[0].isupper():
                continue
            if entry["syllables"] != index[req]["syllables"]:
                continue
            score, details = score_phonemes(req_ph, entry["phonemes"], mode=mode)
            if score is None:
                continue
            pct = min(score / max_score * 100, 100) if max_score else 0
            results.append((cand, score, pct, entry["ascii"]))

        results.sort(key=lambda x: -x[1])
        for cand, score, pct, ascii_s in results[:12]:
            print(f"  {cand:<15} {ascii_s:<25} {score:>5} ({pct:.0f}%)")
        print()

    test("чилить", mode="A")
    test("вайб", mode="A")
    test("кринж", mode="A")
