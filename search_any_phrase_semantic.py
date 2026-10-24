import json
import re
import numpy as np
from pathlib import Path
import silero_stress
from ruphon import RUPhon
from ipa_to_ascii import IpaToAscii
from test_phrase_rhymes import phrase_info, score_phrase_match

BASE = Path.home() / "models"
INDEX = BASE / "phrases_index.jsonl"
VECTORS = BASE / "phrases_vectors.json" # ВОЗВРАЩАЕМ СТАРЫЕ ВЕКТОРЫ (СИНОНИМЫ)

print("Загружаем модели...", flush=True)
accentor = silero_stress.load_accentor()
phonemizer = RUPhon().load("small", workdir="./models", device="CPU")
conv = IpaToAscii()

print("Загружаем базу и векторы (синонимы)...", flush=True)
index = {}
with open(INDEX, encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        index.update(d)

phrase_vectors = json.load(open(VECTORS, encoding="utf-8"))
print(f"  База: {len(index)} фраз, Векторы: {len(phrase_vectors)}\n", flush=True)

def clean_phrase(text):
    text = re.sub(r'[-–—]', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def phonemize_word(word):
    stressed = accentor(word)
    if not stressed: stressed = word
    ipa = phonemizer.phonemize(stressed, put_stress=True, stress_symbol="'")
    phon = conv.parse_ipa(ipa)
    clean_ph = [p for p in phon if p.get('type') in ('vowel', 'consonant')]
    vowels = [p for p in clean_ph if p['type'] == 'vowel']
    if not any(v.get('stressed') for v in vowels) and vowels:
        vowels[-1]['stressed'] = True
    return clean_ph

def cosine_sim(v1, v2):
    v1 = np.array(v1)
    v2 = np.array(v2)
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0: return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))

def search_phrase(query_text, topn=10):
    phrase = clean_phrase(query_text)
    words = phrase.split()
    if not words: return
        
    query_phonemes = []
    for w in words:
        query_phonemes.extend(phonemize_word(w))
        
    q_info = phrase_info(query_phonemes)
    if not q_info: return

    q_vec = phrase_vectors.get(query_text)
    
    print(f"=== {query_text} -> {conv.to_ascii_string(query_phonemes, mark_soft=False)} ===")
    
    results = []
    for cand, entry in index.items():
        if cand == query_text: continue 
        
        c_info = phrase_info(entry["phonemes"])
        if not c_info: continue
        
        res, reason = score_phrase_match(q_info, c_info)
        if res is None: continue
        
        total, pct = res
        
        # Семантический фильтр на синонимах
        sem_sim = None
        if q_vec:
            c_vec = phrase_vectors.get(cand)
            if c_vec:
                sem_sim = cosine_sim(q_vec, c_vec)
                if sem_sim < 0.40: # Порог 0.40
                    continue
                    
        results.append((cand, total, pct, entry["ascii"], sem_sim))
        
    results.sort(key=lambda x: -x[1])
    
    if not results:
        print("  Ничего не найдено (или всё отсеяно семантикой).\n")
        return
        
    for c, s, p, a, sem in results[:topn]:
        sem_str = f" [sem: {sem:.2f}]" if sem is not None else ""
        print(f"  {c:<30} {a:<25} {s:>4} ({p:.0f}%){sem_str}")
    print()

search_phrase("бить баклуши")
search_phrase("собаку съесть")
search_phrase("рубить сплеча")
