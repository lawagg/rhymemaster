import json
import time
import requests
from pathlib import Path

API_KEY = "sk-1054f916e93542beb8e36a23f988d24d"
BASE = Path.home() / "models"
INPUT = BASE / "phrases_for_semantics.txt" # Файл, который мы создали ранее
PROGRESS_FILE = BASE / "phrases_semantics_progress.json"

BATCH_SIZE = 50
MODEL = "deepseek-chat"
API_URL = "https://api.deepseek.com/v1/chat/completions"

def call_api(phrases_batch):
    prompt = (
        "Для каждой фразы напиши её короткий смысловой синоним или определение (1-3 слова).\n"
        "Формат вывода: строго 'фраза<TAB>синоним', по одной на строку.\n"
        "Без JSON, без нумерации, без кавычек и комментариев. Порядок должен совпадать с входным.\n\n"
    )
    for p in phrases_batch:
        prompt += f"{p}\n"
        
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = content.replace("```", "").strip()
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                if len(lines) == len(phrases_batch):
                    return lines
                else:
                    print(f"    [WARN] Ожидалось {len(phrases_batch)} строк, получено {len(lines)}. Пробуем еще раз...")
            else:
                print(f"    [ERROR] API {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"    [ERROR] Сеть: {e}")
        time.sleep(2)
    return None

def main():
    print("Загружаем фразы...")
    with open(INPUT, encoding="utf-8") as f:
        phrases = [l.strip() for l in f if l.strip()]
        
    done = {}
    if PROGRESS_FILE.exists():
        done = json.load(open(PROGRESS_FILE, encoding='utf-8'))
        print(f"  Уже обработано: {len(done)}")
        
    todo = [p for p in phrases if p not in done]
    print(f"  Осталось обработать: {len(todo)}")
    
    if not todo:
        print("Всё уже обработано!")
        return

    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        print(f"  [{i}/{len(todo)}] Отправляем пачку из {len(batch)} фраз...", flush=True)
        
        lines = call_api(batch)
        if lines:
            for line in lines:
                if '\t' in line:
                    orig, syn = line.split('\t', 1)
                    done[orig.strip()] = syn.strip()
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(done, f, ensure_ascii=False)
        else:
            print("    [FAIL] Пропускаем пачку.")
        time.sleep(1)

    print("\n=== ОБРАБОТКА ЗАВЕРШЕНА ===")
    print(f"Всего синонимов получено: {len(done)}")
    
    # Сохраняем финальный файл для Navec
    out_file = BASE / "phrases_synonyms.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(done, f, ensure_ascii=False)
    print(f"Файл: {out_file}")

if __name__ == "__main__":
    main()
