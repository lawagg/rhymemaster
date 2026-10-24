import json
import numpy as np
from pathlib import Path
from gensim.models import KeyedVectors

BASE = Path.home() / "models"
SYNONYMS = BASE / "slang_synonyms.json"
NAVEC = BASE / "navec_gensim.kv"
OUT = BASE / "slang_vectors.json"

print("Загружаем Navec...", flush=True)
navec = KeyedVectors.load(str(NAVEC))

print("Загружаем синонимы...", flush=True)
synonyms = json.load(open(SYNONYMS, encoding="utf-8"))

vectors = {}
missing = 0

for word, syn in synonyms.items():
    # Разбиваем синоним на слова (например, "быть профессионалом" -> ["быть", "профессионалом"])
    words = syn.lower().replace("-", " ").split()
    vecs = []
    for w in words:
        if w in navec:
            vecs.append(navec[w])
            
    if vecs:
        mean_vec = np.mean(vecs, axis=0).tolist()
        vectors[word] = mean_vec
    else:
        missing += 1

print(f"Создано векторов: {len(vectors)}")
print(f"Не найдено в Navec: {missing}")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(vectors, f)

print(f"Файл: {OUT}")
print(f"Размер: {OUT.stat().st_size / 1024 / 1024:.1f} МБ")
