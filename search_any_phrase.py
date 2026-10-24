import json
import re
from pathlib import Path
import silero_stress
from ruphon import RUPhon
from ipa_to_ascii import IpaToAscii

# Импортируем функции скоринга из нашего основного движка
from test_phrase_rhymes import phrase_info, score_phrase_match

BASE = Path.home() / "models"
INDEX = BASE / "phrases_index.jsonl"

print("Загружаем модели...", flush=True)
accentor = silero_stress.load_accentor()
phonemizer = RUPhon().load("small", workdir="./models", device="CPU")
conv = IpaToAscii()
print("Загружаем базу фраз...", flush=True)

index = {}
with open(INDEX, encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        index.update(d)
print(f"  База загружена: {len(index)} фраз.\n", flush=True)

def clean_phrase(line):
    line = line.split('|')[0].strip()
    line = re.sub(r'[-–—]', ' ', line)
    line = re.sub(r'[^\w\s]', '', line)
    line = re.sub(r'\s+', ' ', line).strip()
    return line

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

def search_phrase(query_text, topn=10):
    phrase = clean_phrase(query_text)
    words = phrase.split()
    
    if not words:
        print("Пустой запрос.")
        return
        
    # 1. Генерируем фонемы для запроса на лету
    query_phonemes = []
    for w in words:
        query_phonemes.extend(phonemize_word(w))
        
    q_info = phrase_info(query_phonemes)
    if not q_info:
        print(f"В запросе '{query_text}' нет ударения.")
        return
        
    print(f"=== {query_text} -> {conv.to_ascii_string(query_phonemes, mark_soft=False)} ===")
    
    # 2. Ищем по базе
    results = []
    for cand, entry in index.items():
        c_info = phrase_info(entry["phonemes"])
        if not c_info: continue
        
        res, reason = score_phrase_match(q_info, c_info)
        if res is None: continue
        
        total, pct = res
        results.append((cand, total, pct, entry["ascii"]))
        
    results.sort(key=lambda x: -x[1])
    
    if not results:
        print("  Ничего не найдено.")
        return
        
    for c, s, p, a in results[:topn]:
        print(f"  {c:<30} {a:<25} {s:>4} ({p:.0f}%)")
    print()

# Тестируем на твоих примерах
search_phrase("были глубже")
search_phrase("ходи сюда")
