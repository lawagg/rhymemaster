#!/usr/bin/env python3
"""IPA → ASCII маппинг по таблице из ТЗ 1.1."""
import re
from pathlib import Path


VOWELS = {
    "a": "a",
    "e": "e",
    "i": "i",
    "o": "o",
    "u": "u",
    "ɨ": "y",
    "ɪ": "i",
    "ə": "a",
    "ɐ": "a",
    "æ": "a",
    "ʉ": "u",
    "ɵ": "o",
    "ɛ": "e",
    "ʊ": "u",
    "ʌ": "a",
}

CONSONANTS = {
    "b": "b",
    "p": "p",
    "d": "d",
    "t": "t",
    "ɡ": "g",
    "g": "g",
    "k": "k",
    "f": "f",
    "v": "v",
    "s": "s",
    "z": "z",
    "ʂ": "sh",
    "ʐ": "zh",
    "m": "m",
    "n": "n",
    "l": "l",
    "ɫ": "l",
    "r": "r",
    "x": "h",
    "t~s": "c",
    "t~ɕ": "ch",
    "ɕ:": "sch",
    "ɕ": "sch",
    "j": "j",
    "ʑ": "zh",
    "ç": "h",
}

SOFT_MARK = "ʲ"
STRESS_MARK = "'"


class IpaToAscii:
    def __init__(self):
        self.vowels = dict(sorted(VOWELS.items(), key=lambda x: -len(x[0])))
        self.consonants = dict(sorted(CONSONANTS.items(), key=lambda x: -len(x[0])))

    def _tokenize(self, ipa_string: str) -> list:
        s = ipa_string.strip()
        tokens = []
        i = 0
        while i < len(s):
            if s[i] == " ":
                tokens.append({"raw": " ", "type": "space"})
                i += 1
                continue
            if s[i] == STRESS_MARK:
                tokens.append({"raw": STRESS_MARK, "type": "stress"})
                i += 1
                continue
            if s[i] == SOFT_MARK:
                tokens.append({"raw": SOFT_MARK, "type": "soft"})
                i += 1
                continue
            if s[i:i+3] in ("t~s", "t~ɕ"):
                tokens.append({"raw": s[i:i+3], "type": "symbol"})
                i += 3
                continue
            if s[i:i+2] == "ɕ:":
                tokens.append({"raw": "ɕ:", "type": "symbol"})
                i += 2
                continue
            tokens.append({"raw": s[i], "type": "symbol"})
            i += 1
        return tokens

    def parse_ipa(self, ipa_string: str) -> list:
        if not ipa_string:
            return []
        tokens = self._tokenize(ipa_string)
        phonemes = []
        pending_stressed = False

        for tok in tokens:
            if tok["type"] == "space":
                continue
            if tok["type"] == "stress":
                pending_stressed = True
                continue
            if tok["type"] == "soft":
                if phonemes and phonemes[-1]["type"] == "consonant":
                    phonemes[-1]["soft"] = True
                continue

            raw = tok["raw"]
            if raw in self.vowels:
                phonemes.append({
                    "type": "vowel",
                    "symbol": self.vowels[raw],
                    "stressed": pending_stressed,
                    "soft": False,
                })
                pending_stressed = False
            elif raw in self.consonants:
                phonemes.append({
                    "type": "consonant",
                    "symbol": self.consonants[raw],
                    "stressed": False,
                    "soft": False,
                })
            else:
                phonemes.append({
                    "type": "unknown",
                    "symbol": raw,
                    "stressed": False,
                    "soft": False,
                })

        processed = []
        i = 0
        while i < len(phonemes):
            cur = phonemes[i]
            if (cur["type"] == "consonant" and cur["symbol"] == "j"
                    and i + 1 < len(phonemes) and phonemes[i+1]["type"] == "vowel"):
                nxt = phonemes[i+1]
                processed.append({
                    "type": "vowel",
                    "symbol": nxt["symbol"],
                    "stressed": nxt["stressed"],
                    "soft": True,
                })
                i += 2
            else:
                processed.append(cur)
                i += 1

        return processed

    def to_ascii_string(self, phonemes: list, mark_soft: bool = False) -> str:
        out = []
        for ph in phonemes:
            s = ph["symbol"]
            if ph["stressed"]:
                s = "'" + s
            if mark_soft and ph["soft"] and ph["type"] == "consonant":
                s = s + "ʲ"
            out.append(s)
        return " ".join(out)


if __name__ == "__main__":
    import os
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    from g2p import G2P

    g2p = G2P()
    converter = IpaToAscii()

    test_words = [
        "вайб", "кринж", "чилить", "хайп", "мем",
        "имба", "молчание", "атмосфера", "настроение",
    ]

    print("\n" + "=" * 70)
    print("IPA → ASCII (по ТЗ 1.1)")
    print("=" * 70)

    for word in test_words:
        ipa = g2p.transcribe(word)
        phonemes = converter.parse_ipa(ipa)
        ascii_clean = converter.to_ascii_string(phonemes, mark_soft=False)
        ascii_marked = converter.to_ascii_string(phonemes, mark_soft=True)
        print(f"\n  {word}")
        print(f"    IPA:           {ipa}")
        print(f"    ASCII (чисто): {ascii_clean}")
        print(f"    ASCII (soft):  {ascii_marked}")
        print(f"    фонемы:")
        for ph in phonemes:
            flags = []
            if ph["stressed"]:
                flags.append("stressed")
            if ph["soft"]:
                flags.append("soft")
            flag_str = " [" + ", ".join(flags) + "]" if flags else ""
            print(f"      {ph['type']:<10} {ph['symbol']!r:<6}{flag_str}")