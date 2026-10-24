import json
import time
import requests
from pathlib import Path

API_KEY = "sk-1054f916e93542beb8e36a23f988d24d"
BASE = Path.home() / "models"
WORK = Path("/mnt/c/Users/admin/Documents/rhymemaster_work")
INPUT = WORK / "stress_manual.txt"
PROGRESS_FILE = BASE / "slang_semantics_progress.json"

BATCH_SIZE = 50
MODEL = "deepseek-chat"
API_URL = "https://api.deepseek.com/v1/chat/completions"

def call_api(words_batch):
    prompt = (
        "Для каждого русского сленгового или матерного слова напиши его короткий смысловой синоним или определение (1-3 слова).\n"
        "Формат вывода: строго 'слово<TAB>синоним', по одной на строку. Без JSON, без нумерации.\n\n"
    )
    for w in words_batch:
        prompt += f"{w}\n"
        
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
                if len(lines) == len(words_batch):
                    return lines
                else:
                    print(f"    [WARN] Ожидалось {len(words_batch)} строк, получено {len(lines)}.")
            else:
                print(f"    [ERROR] API {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"    [ERROR] Сеть: {e}")
        time.sleep(2)
    return None

def main():
    print("Загружаем слова...")
    words = []
    with open(INPUT, encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w:
                words.append(w.replace('+', '').lower())
        
    done = {}
    if PROGRESS_FILE.exists():
        done = json.load(open(PROGRESS_FILE, encoding='utf-8'))
        print(f"  Уже обработано: {len(done)}")
        
    todo = [w for w in words if w not in done]
    print(f"  Осталось обработать: {len(todo)}")
    
    if not todo:
        print("Всё уже обработано!")
        return

    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        print(f"  [{i}/{len(todo)}] Отправляем пачку из {len(batch)} слов...", flush=True)
        
        lines = call_api(batch)
        if lines:
            for line in lines:
                if '\t' in line:
                    orig, syn = line.split('\t', 1)
                    done[orig.strip()] = syn.strip()
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(done, f, ensure_ascii=False)
        time.sleep(1)

    print("\n=== ОБРАБОТКА ЗАВЕРШЕНА ===")
    print(f"Всего синонимов получено: {len(done)}")
    
    out_file = BASE / "slang_synonyms.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(done, f, ensure_ascii=False)
    print(f"Файл: {out_file}")

if __name__ == "__main__":
    main()
