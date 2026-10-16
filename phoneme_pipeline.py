#!/usr/bin/env python3
"""Полный фонетический пайплайн (метод Брика, ТЗ 1.2)."""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import re
from pathlib import Path

from g2p import G2P
from ipa_to_ascii import IpaToAscii


class PhonemePipeline:
    def __init__(self):
        print("Загружаем G2P...")
        self.g2p = G2P()
        self.converter = IpaToAscii()
        print("Готово")

    @staticmethod
    def normalize_text(text: str) -> list:
        """Разбивает текст на слова, чистит."""
        text = text.lower().strip()
        text = re.sub(r"[^а-яё\s\-]", "", text)
        return [w for w in text.split() if w]

    @staticmethod
    def prepare_input(words: list) -> str:
        """Буквы через пробел, между словами _ (формат модели)."""
        return " _ ".join(" ".join(list(w)) for w in words)

    @staticmethod
    def parse_infer_result(raw: str) -> dict:
        """
        Разбирает ответ модели. Формат (5 полей через \\t):
        1. IPA-транскрипция (без _)
        2. Исходный текст (буквы через пробел, с _ между словами)
        3. IPA с _ между словами  ← это ключ для word_index
        4. IPA с _ (дубликат, иногда с <DELETE>)
        5. Маркеры PLAIN/<DELETE>
        """
        parts = raw.split("\t")
        return {
            "ipa_plain": parts[0] if len(parts) > 0 else "",
            "source": parts[1] if len(parts) > 1 else "",
            "ipa_with_borders": parts[2] if len(parts) > 2 else "",
            "ipa_with_borders_v2": parts[3] if len(parts) > 3 else "",
            "markers": parts[4] if len(parts) > 4 else "",
        }

    @staticmethod
    def split_ipa_by_words(ipa_with_borders: str) -> list:
        """
        Разбивает IPA-поток по _ на группы фонем.
        'ɪ sʲ tʲ ɪ n ɨ _ nʲ e t' → [['ɪ','sʲ','tʲ','ɪ','n','ɨ'], ['nʲ','e','t']]
        """
        groups = []
        for chunk in ipa_with_borders.split("_"):
            tokens = [t.strip() for t in chunk.strip().split() if t.strip()]
            tokens = [t for t in tokens if t != "<DELETE>"]
            if tokens:
                groups.append(tokens)
        return groups

    def process(self, text: str) -> dict:
        """
        Полный пайплайн:
        1. Разбить текст на слова
        2. Подать в G2P всю фразу с _ (метод Брика)
        3. Разобрать ответ, извлечь IPA и границы слов
        4. Присвоить каждой фонеме word_index
        5. Конвертировать IPA → ASCII с флагами
        """
        words = self.normalize_text(text)
        if not words:
            return {
                "text": text, "words": [], "phonemes": [],
                "word_boundaries": [], "ipa_per_word": [],
                "ascii_string": "", "syllable_count": 0,
            }

        prepared = self.prepare_input(words)
        results = self.g2p.model._infer([prepared])
        if not results:
            return {"text": text, "words": words, "phonemes": [],
                    "word_boundaries": [], "ipa_per_word": [],
                    "ascii_string": "", "syllable_count": 0}

        parsed = self.parse_infer_result(results[0])

        groups = self.split_ipa_by_words(parsed["ipa_with_borders"])

        all_phonemes = []
        word_boundaries = []
        ipa_per_word = []

        for word_idx, (word, group) in enumerate(zip(words, groups)):
            group_ipa = " ".join(group)
            phonemes = self.converter.parse_ipa(group_ipa)

            word_boundaries.append({
                "word": word,
                "word_index": word_idx,
                "start": len(all_phonemes),
                "length": len(phonemes),
            })
            ipa_per_word.append((word, group_ipa))

            for ph in phonemes:
                ph_copy = dict(ph)
                ph_copy["word_index"] = word_idx
                all_phonemes.append(ph_copy)

        ascii_string = self.converter.to_ascii_string(all_phonemes, mark_soft=False)
        syllable_count = sum(1 for ph in all_phonemes if ph["type"] == "vowel")

        return {
            "text": text,
            "words": words,
            "phonemes": all_phonemes,
            "word_boundaries": word_boundaries,
            "ipa_per_word": ipa_per_word,
            "ascii_string": ascii_string,
            "syllable_count": syllable_count,
            "raw_ipa_with_borders": parsed["ipa_with_borders"],
            "raw_source": parsed["source"],
        }

    def restore_text(self, phonemes: list) -> str:
        """Восстановление текста по word_index (для Панели В)."""
        if not phonemes:
            return ""
        words = {}
        for ph in phonemes:
            wi = ph.get("word_index", 0)
            words.setdefault(wi, []).append(ph["symbol"])
        return " ".join("".join(words[wi]) for wi in sorted(words.keys()))


if __name__ == "__main__":
    pipeline = PhonemePipeline()

    test_phrases = [
        "вайб",
        "кринж",
        "я словил вайб",
        "истины нет",
        "кринжовый момент",
        "чилить дома",
    ]

    for phrase in test_phrases:
        result = pipeline.process(phrase)
        print("\n" + "=" * 70)
        print(f"ТЕКСТ: {phrase!r}")
        print("=" * 70)
        print(f"  Слов: {len(result['words'])}")
        print(f"  Всего фонем: {len(result['phonemes'])}")
        print(f"  Слогов: {result['syllable_count']}")
        print(f"  IPA (с границами _): {result['raw_ipa_with_borders']!r}")
        print()
        print(f"  IPA по словам:")
        for w, ipa in result["ipa_per_word"]:
            print(f"    {w:<15} → {ipa}")
        print()
        print(f"  Границы слов:")
        for b in result["word_boundaries"]:
            print(f"    [{b['start']}:{b['start']+b['length']}] "
                  f"word_index={b['word_index']} {b['word']!r}")
        print()
        print(f"  Фонемы:")
        for i, ph in enumerate(result["phonemes"]):
            flags = []
            if ph["stressed"]:
                flags.append("S")
            if ph["soft"]:
                flags.append("soft")
            flag_str = " [" + ",".join(flags) + "]" if flags else ""
            print(f"    [{i:>2}] w{ph['word_index']} {ph['type']:<10} "
                  f"{ph['symbol']!r:<6}{flag_str}")
        print()
        print(f"  ASCII: {result['ascii_string']}")