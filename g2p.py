#!/usr/bin/env python3
"""Модуль G2P: текст → IPA-транскрипция через ru_g2p_ipa_bert_large."""
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import re
from pathlib import Path

MODEL_PATH = Path.home() / "models/ru_g2p_ipa_bert_large/ru_g2p.nemo"


class G2P:
    def __init__(self):
        from nemo.collections.nlp.models.text_normalization_as_tagging.thutmose_tagger import (
            ThutmoseTaggerModel,
        )
        print("Загружаем G2P модель...")
        self.model = ThutmoseTaggerModel.restore_from(str(MODEL_PATH))
        self.model.eval()
        print("G2P готов")

    @staticmethod
    def prepare_input(text: str) -> str:
        """
        Преобразует нормальный текст в формат модели:
        буквы через пробел, между словами _
        """
        text = text.lower().strip()
        text = re.sub(r"[^а-яё\s\-]", "", text)
        words = text.split()
        prepared = []
        for word in words:
            letters = " ".join(list(word))
            prepared.append(letters)
        return " _ ".join(prepared)

    @staticmethod
    def parse_ipa(raw: str) -> str:
        """
        Берёт первую колонку (IPA), убирает маркеры <DELETE>,
        схлопывает пробелы.
        """
        if not raw:
            return ""
        first = raw.split("\t")[0]
        first = first.replace("<DELETE>", " ")
        first = re.sub(r"\s+", " ", first).strip()
        return first

    def transcribe(self, text: str) -> str:
        """Главный метод: текст → IPA."""
        if not text.strip():
            return ""
        prepared = self.prepare_input(text)
        try:
            results = self.model._infer([prepared])
        except Exception as e:
            print(f"  ошибка инференса: {e}")
            return ""
        if not results:
            return ""
        return self.parse_ipa(results[0])

    def transcribe_words(self, text: str) -> list:
        """
        Возвращает список (слово, IPA), чтобы сохранить привязку.
        """
        text = text.lower().strip()
        text = re.sub(r"[^а-яё\s\-]", "", text)
        words = [w for w in text.split() if w]
        if not words:
            return []
        prepared_inputs = [" ".join(list(w)) for w in words]
        try:
            results = self.model._infer(prepared_inputs)
        except Exception as e:
            print(f"  ошибка инференса: {e}")
            return []
        output = []
        for word, raw in zip(words, results):
            output.append((word, self.parse_ipa(raw)))
        return output


if __name__ == "__main__":
    g2p = G2P()

    print("\n" + "=" * 60)
    print("ТЕСТ 1: отдельные слова")
    print("=" * 60)

    test_words = [
        "вайб", "кринж", "чилить", "хайп", "мем", "краш",
        "имба", "рофл", "жиза", "кринжовый", "вайбовый",
        "молчание", "атмосфера", "настроение",
    ]
    for word in test_words:
        ipa = g2p.transcribe(word)
        print(f"  {word:<15} → {ipa}")

    print("\n" + "=" * 60)
    print("ТЕСТ 2: фраза целиком")
    print("=" * 60)

    phrases = [
        "я словил вайб",
        "истины нет",
        "кринжовый момент",
        "чилить дома",
    ]
    for phrase in phrases:
        ipa = g2p.transcribe(phrase)
        print(f"  {phrase!r}")
        print(f"    → {ipa}")
        print()

    print("=" * 60)
    print("ТЕСТ 3: с разбивкой по словам")
    print("=" * 60)
    for word, ipa in g2p.transcribe_words("я словил вайб"):
        print(f"  {word} → {ipa}")