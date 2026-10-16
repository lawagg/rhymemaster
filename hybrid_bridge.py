#!/usr/bin/env python3
"""Гибридный семантический мост: Navec + W2V + FastText + ручные карты."""
import json
import re
from pathlib import Path
from collections import defaultdict
from gensim.models import KeyedVectors, Word2Vec, FastText

BASE = Path.home() / "models"

WEIGHTS = {
    "navec": 2.0,
    "w2v": 1.2,
    "fasttext": 0.5,
}

AGREEMENT_BONUS = {
    1: 1.0,
    2: 1.5,
    3: 2.0,
}

NAVEC_PENALTY = 0.7


class HybridBridge:
    def __init__(self):
        print("Загружаем словарь сленга...")
        with open(BASE / "slang_datasets/unified_slang_clean.json", "r", encoding="utf-8") as f:
            self.semantic = json.load(f)
        print(f"  слов: {len(self.semantic):,}")

        print("Загружаем Navec...")
        self.navec = KeyedVectors.load(str(BASE / "navec_gensim.kv"))

        print("Загружаем Word2Vec v3...")
        self.w2v = Word2Vec.load(str(BASE / "slang_word2vec_v3.model")).wv

        print("Загружаем FastText...")
        self.ft = FastText.load(str(BASE / "slang_fasttext.model")).wv

        self.meta_words = set("""
            означает означало означать обозначает обозначало обозначение
            сокращение сокращения сокращением слово слова словом
            значение значения значением говорят говорить значит
            английского английский английском русском русский русском
            перевод перевода используется используются использовать
            называется называют пример например
        """.split())

        self.stop = set("""
            это что как или для оно она они был была было быть есть очень так всё все
            который которая которое того этого том чем что-то что-нибудь такое такие
            может можно нужно надо только даже ещё уже всегда никогда совсем
            ведь понятно почему нет данном некое
        """.split())

        self.manual = {}
        manual_path = BASE / "manual_bridges.json"
        if manual_path.exists():
            with open(manual_path, encoding="utf-8") as f:
                self.manual = json.load(f)
            print(f"  ручных карт: {len(self.manual)}")

    def _extract_definition_words(self, defn):
        defn = re.sub(r'\([^)]*\)', ' ', defn)
        defn = re.sub(r'\[[^\]]*\]', ' ', defn)
        defn = defn.replace('"', ' ').replace('«', ' ').replace('»', ' ')
        defn = re.split(r'\d', defn)[0]
        for marker in ['что значит', 'Что значит', 'кто такой', 'кто такая', 'Например', 'например']:
            if marker in defn:
                defn = defn.split(marker)[0]
        for sep in ['. ', '! ', '? ', ';', '\n']:
            if sep in defn:
                defn = defn.split(sep)[0]
                break
        defn = re.sub(r'[-—:]+', ' ', defn)
        words = re.findall(r'[а-яё]{5,}', defn.lower())
        words = [w for w in words if w not in self.stop and w not in self.meta_words]
        seen = set()
        result = []
        for w in words:
            if w not in seen:
                seen.add(w)
                result.append(w)
        return result

    def _navec_layer(self, word, topn=30):
        if word not in self.semantic:
            return []
        defn = self.semantic[word].get("definition", "")
        defn_words = self._extract_definition_words(defn)
        defn_in_navec = [w for w in defn_words if w in self.navec]
        if not defn_in_navec:
            return []
        scores = defaultdict(float)
        for w in defn_in_navec[:5]:
            try:
                for sim_word, score in self.navec.most_similar(w, topn=8):
                    if sim_word in defn_in_navec:
                        continue
                    scores[sim_word] = max(scores[sim_word], score)
            except KeyError:
                continue
        result = sorted(scores.items(), key=lambda x: -x[1])[:topn]
        return result

    def _w2v_layer(self, word, topn=30):
        if word not in self.w2v:
            return []
        try:
            return self.w2v.most_similar(word, topn=topn)
        except KeyError:
            return []

    def _fasttext_layer(self, word, topn=30):
        try:
            return self.ft.most_similar(word, topn=topn)
        except KeyError:
            return []

    def get_neighbors(self, word, topn=15):
        word = word.lower().strip()

        if word in self.manual:
            synonyms = self.manual[word]
            result = [(w, 1.0 - i * 0.05) for i, w in enumerate(synonyms[:topn])]
            votes = {w: 3 for w in synonyms[:topn]}
            return result, "manual", votes

        navec_raw = self._navec_layer(word, topn=30)
        w2v_raw = self._w2v_layer(word, topn=30)
        ft_raw = self._fasttext_layer(word, topn=30)

        navec_scores = dict(navec_raw)
        w2v_scores = dict(w2v_raw)
        ft_scores = dict(ft_raw)

        votes = defaultdict(int)
        for layer in [navec_scores, w2v_scores, ft_scores]:
            for w in layer:
                votes[w] += 1

        combined = defaultdict(float)
        for w, s in navec_scores.items():
            combined[w] += s * WEIGHTS["navec"]
        for w, s in w2v_scores.items():
            combined[w] += s * WEIGHTS["w2v"]
        for w, s in ft_scores.items():
            combined[w] += s * WEIGHTS["fasttext"]

        for w in combined:
            v = votes[w]
            combined[w] *= AGREEMENT_BONUS.get(v, 1.0)
            if w not in self.navec:
                combined[w] *= NAVEC_PENALTY

        combined.pop(word, None)
        result = sorted(combined.items(), key=lambda x: -x[1])[:topn]

        sources = []
        if navec_scores:
            sources.append("Navec")
        if w2v_scores:
            sources.append("W2V")
        if ft_scores:
            sources.append("FastText")

        return result, "+".join(sources) if sources else "none", votes


if __name__ == "__main__":
    bridge = HybridBridge()
    print("\n" + "=" * 70)

    test_words = [
        "вайб", "кринж", "флекс", "чилить", "ризз", "краш",
        "хайп", "мем", "жиза", "токсик", "имба", "рофл",
        "агриться", "буллинг", "зашквар", "душнила", "хейтить",
    ]

    for word in test_words:
        neighbors, source, votes = bridge.get_neighbors(word)
        print(f"\n{word}  [{source}]")
        if not neighbors:
            print("  нет соседей")
            continue
        for w, s in neighbors[:10]:
            v = votes.get(w, 0)
            mark = "★" * v if v else ""
            print(f"  {w} ({s:.3f}) {mark}")