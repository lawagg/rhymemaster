import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json
import time
from pathlib import Path
from ruphon import RUPhon
from ipa_to_ascii import IpaToAscii

BASE = Path.home() / "models"
ACCENTS = BASE / "accents.json"
OUT_JSONL = BASE / "phoneme_index_v3.jsonl"
PROGRESS = BASE / "index_v3_progress.json"

def main():
    print("Загружаем accents.json...")
    with open(ACCENTS, encoding="utf-8") as f:
        accents = json.load(f)

    done_words = set()
    if PROGRESS.exists():
        print("Загружаем прогресс...")
        with open(PROGRESS, encoding="utf-8") as f:
            done = json.load(f)
        done_words = set(done.keys())
        print(f"  уже обработано: {len(done_words)}")
        if not OUT_JSONL.exists():
            with open(OUT_JSONL, 'w', encoding='utf-8') as f:
                for w, v in done.items():
                    f.write(json.dumps({w: v}, ensure_ascii=False) + '\n')
        PROGRESS.unlink()
        print(f"  перенесено в {OUT_JSONL.name}")

    todo = [k for k in accents.keys() if k not in done_words]
    print(f"Осталось обработать: {len(todo)}")

    print("Загружаем ruphon...")
    phonemizer = RUPhon().load("small", workdir="./models", device="CPU")
    conv = IpaToAscii()
    print("Модели готовы\n", flush=True)

    start = time.time()
    with open(OUT_JSONL, 'a', encoding='utf-8') as f:
        for i, word in enumerate(todo):
            stressed_word = accents[word]
            try:
                ipa = phonemizer.phonemize(stressed_word, put_stress=True, stress_symbol="'")
                phon = conv.parse_ipa(ipa)
                clean_ph = [p for p in phon if p.get('type') in ('vowel', 'consonant')]
                ascii_str = conv.to_ascii_string(clean_ph, mark_soft=False)
                syllables = sum(1 for p in clean_ph if p['type'] == 'vowel')

                entry = {
                    'kind': 'word',
                    'phonemes': clean_ph,
                    'syllables': syllables,
                    'ascii': ascii_str,
                    'ipa': ipa
                }
                f.write(json.dumps({word: entry}, ensure_ascii=False) + '\n')
            except Exception:
                pass

            if (i + 1) % 5000 == 0:
                f.flush()
                elapsed = time.time() - start
                speed = (i + 1) / elapsed
                print(f"  {i+1}/{len(todo)} — {speed:.1f} слов/сек", flush=True)
    
    f.flush()
    print("Готово!", flush=True)

if __name__ == "__main__":
    main()
