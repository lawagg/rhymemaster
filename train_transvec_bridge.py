import json
import numpy as np
from pathlib import Path
from gensim.models import Word2Vec, KeyedVectors
from transvec.transformers import TranslationWordVectorizer

BASE = Path.home() / "models"
W2V_PATH = BASE / "slang_word2vec_v3.model"
NAVEC_PATH = BASE / "navec_gensim.kv"
SYNONYMS = BASE / "slang_synonyms.json"

# Создаем фейковые объекты, которые имитируют старый gensim 3.x
class MockWV:
    def __init__(self, kv):
        self.kv = kv
        self.vocab = {k: i for i, k in enumerate(kv.index_to_key)}
        self.index_to_key = kv.index_to_key
        self.key_to_index = kv.key_to_index
        self.vector_size = kv.vector_size

    def __getitem__(self, key):
        return self.kv[key]

    def __contains__(self, key):
        return key in self.kv

    def get_vector(self, key):
        return self.kv[key]

class MockModel:
    def __init__(self, kv):
        self.wv = MockWV(kv)
        self.vector_size = kv.vector_size

    def __getitem__(self, key):
        return self.wv[key]

    def __contains__(self, key):
        return key in self.wv

    def get_vector(self, key):
        return self.wv.get_vector(key)

print("Загружаем модели (это может занять минуту)...", flush=True)
w2v = Word2Vec.load(str(W2V_PATH))
navec = KeyedVectors.load(str(NAVEC_PATH))

print(f"  W2V словарь: {len(w2v.wv.index_to_key)} слов")
print(f"  Navec словарь: {len(navec.index_to_key)} слов")

print("Формируем обучающие пары...", flush=True)
synonyms = json.load(open(SYNONYMS, encoding="utf-8"))
train_pairs = []

for slang_word, syn_str in synonyms.items():
    syn_word = syn_str.split()[0].lower() if syn_str else ""
    if slang_word in w2v.wv and syn_word in navec:
        train_pairs.append((slang_word, syn_word))

print(f"  Найдено валидных пар: {len(train_pairs)}")
if len(train_pairs) < 50:
    print("  ОШИБКА: Слишком мало пар для обучения. Прерываем.")
    exit(1)

print("Обучаем transvec (линейное преобразование)...", flush=True)

# Оборачиваем модели в наши фейковые классы
w2v_mock = MockModel(w2v.wv)
navec_mock = MockModel(navec)

bridge = TranslationWordVectorizer(w2v_mock, navec_mock)
bridge.fit(train_pairs)

print("Готово! Проверяем перевод пары слов:")
test_words = ["чиллить", "кринж", "пиздеть", "байтить"]
for tw in test_words:
    if tw in w2v.wv:
        translated_vec = bridge.transform([w2v.wv[tw]])[0]
        sims = navec.similar_by_vector(translated_vec, topn=5)
        print(f"  {tw} -> {[s[0] for s in sims]}")

bridge.save(str(BASE / "transvec_bridge.model"))
print("Мост сохранен в transvec_bridge.model")
