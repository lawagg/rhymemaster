import json
import numpy as np
from pathlib import Path
from gensim.models import KeyedVectors

BASE = Path.home() / "models"
NAVEC = BASE / "navec_gensim.kv"
VECTORS = BASE / "slang_vectors.json"

print("Загружаем Navec...", flush=True)
navec = KeyedVectors.load(str(NAVEC))

print("Загружаем векторы сленга...", flush=True)
slang_vectors = json.load(open(VECTORS, encoding="utf-8"))

print(f"  Векторов сленга: {len(slang_vectors)}\n")

test_words = ["кринж", "пиздеть", "чиллить", "байтить", "абитура", "краш"]

for word in test_words:
    if word in slang_vectors:
        # ИСПРАВЛЕНО: превращаем список в numpy array
        vec = np.array(slang_vectors[word])
        # Ищем 5 ближайших слов из Navec
        sims = navec.similar_by_vector(vec, topn=5)
        print(f"{word}:")
        for sim_word, score in sims:
            print(f"  -> {sim_word} ({score:.2f})")
        print()
    else:
        print(f"{word}: НЕТ ВЕКТОРА\n")
