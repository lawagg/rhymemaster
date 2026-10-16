#!/usr/bin/env python3
"""Модуль расстановки ударений через RUAccent + конвертация в формат G2P."""
import re
from pathlib import Path

STOP_ACCENT = {
    "от", "до", "на", "в", "с", "к", "по", "за", "из", "у", "о", "об",
    "и", "а", "но", "да", "не", "ни", "же", "ли", "бы", "то", "как",
    "что", "чем", "кто", "где", "когда", "или", "при", "для", "без",
    "над", "под", "про", "через", "между", "перед",
}


class Accent:
    def __init__(self):
        from ruaccent import RUAccent
        print("Загружаем RUAccent...")
        self.accent = RUAccent()
        self.accent.load(omograph_model_size='turbo3.1', use_dictionary=True)
        print("RUAccent готов")

    @staticmethod
    def plus_to_diacritic(text: str) -> str:
        """
        Конвертирует формат '+гласная' в 'гласная+́' (U+0301).
        Пример: 'атмосф+ера' → 'атмосфе́ра'
        """
        result = []
        i = 0
        while i < len(text):
            if text[i] == '+' and i + 1 < len(text):
                next_char = text[i + 1]
                result.append(next_char)
                result.append('\u0301')
                i += 2
            else:
                result.append(text[i])
                i += 1
        return "".join(result)

    @staticmethod
    def filter_stopwords(text: str) -> str:
        """Убирает ударения у служебных слов (коротких предлогов/союзов)."""
        words = text.split()
        result = []
        for w in words:
            clean = re.sub(r"\+", "", w).lower()
            if clean in STOP_ACCENT:
                result.append(re.sub(r"\+", "", w))
            else:
                result.append(w)
        return " ".join(result)

    def process(self, text: str, output_format: str = "diacritic") -> str:
        """
        Расставляет ударения.
        output_format: 'plus' (как RUAccent) или 'diacritic' (для G2P)
        """
        if not text.strip():
            return ""
        result = self.accent.process_all(text)
        result = self.filter_stopwords(result)
        if output_format == "diacritic":
            result = self.plus_to_diacritic(result)
        return result

    def process_words(self, text: str, output_format: str = "diacritic") -> list:
        """Возвращает список (слово, ударённое слово)."""
        text = text.strip()
        if not text:
            return []
        words = text.split()
        output = []
        for w in words:
            accented = self.accent.process_all(w)
            accented = self.filter_stopwords(accented)
            if output_format == "diacritic":
                accented = self.plus_to_diacritic(accented)
            output.append((w, accented))
        return output


if __name__ == "__main__":
    acc = Accent()

    print("\n" + "=" * 60)
    print("ТЕСТ 1: конвертация + → диакритика")
    print("=" * 60)
    tests = [
        "атмосф+ера",
        "+имба",
        "ч+илить",
        "зам+ок",
        "з+амок",
    ]
    for t in tests:
        diacritic = Accent.plus_to_diacritic(t)
        print(f"  {t!r} → {diacritic!r}")

    print("\n" + "=" * 60)
    print("ТЕСТ 2: фильтр служебных слов")
    print("=" * 60)
    tests = [
        "мук+а +от разл+уки",
        "+истины н+ет",
        "я слов+ил вайб",
    ]
    for t in tests:
        filtered = Accent.filter_stopwords(t)
        diacritic = Accent.plus_to_diacritic(filtered)
        print(f"  {t!r}")
        print(f"    после фильтра: {filtered!r}")
        print(f"    диакритика: {diacritic!r}")
        print()

    print("\n" + "=" * 60)
    print("ТЕСТ 3: полный process")
    print("=" * 60)
    phrases = [
        "истины нет",
        "я словил вайб",
        "кринжовый момент",
        "чилить дома",
        "на двери висит замок",
        "старинный замок на горе",
    ]
    for p in phrases:
        plus = acc.process(p, output_format="plus")
        diacr = acc.process(p, output_format="diacritic")
        print(f"  {p!r}")
        print(f"    плюс:      {plus!r}")
        print(f"    диакритика: {diacr!r}")
        print()