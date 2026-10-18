#!/usr/bin/env python3
"""Фиксер глагольных форм. Эффективный: один проход по word_forms."""
import json
import re
from pathlib import Path

INDEX = Path.home() / "models/phoneme_index_v2.json"
DECL = Path("/mnt/c/Users/admin/Documents/rhymemaster_work/indecl_DECL.txt")

VOWELS_ASCII = 'aeiouy'
RU_VOWELS = 'аеёиоуыэюя'


def get_stress_pos_from_end(phonemes):
    vowels = [p for p in phonemes if p['type'] == 'vowel']
    for i, v in enumerate(vowels):
        if v.get('stressed'):
            return len(vowels) - i
    return None


def get_vowel_positions(phonemes):
    return [i for i, p in enumerate(phonemes) if p['type'] == 'vowel']


def apply_stress_at_from_end(phonemes, pos_from_end):
    vowel_indices = get_vowel_positions(phonemes)
    if not vowel_indices:
        return False
    total = len(vowel_indices)
    if pos_from_end < 1 or pos_from_end > total:
        return False
    target_vowel = total - pos_from_end
    target_idx = vowel_indices[target_vowel]
    for p in phonemes:
        if p['type'] == 'vowel':
            p['stressed'] = False
    phonemes[target_idx]['stressed'] = True
    return True


def ascii_to_string(phonemes):
    return ' '.join(("'" + p['symbol']) if p.get('stressed') else p['symbol'] for p in phonemes)


def get_stem(word):
    if word.endswith('ться'):
        return word[:-4]
    elif word.endswith('ть'):
        return word[:-2]
    return None


def is_garbage_form(word, base):
    base_stem = get_stem(base)
    if not base_stem or not word.startswith(base_stem):
        return False
    rest = word[len(base_stem):]
    
    if base_stem and base_stem[-1] in 'аеёиоуыэюя':
        if rest in ('си', 'се', 'сю', 'сей', 'сям', 'сях', 'сями'):
            return True
    if 'жж' in word and 'жж' not in base:
        return True
    if re.match(r'^т(ю|ет|ешь|ем|ете|ут|ют)$', rest):
        return True
    return False


def main():
    print("Загружаем индекс...")
    idx = json.load(open(INDEX, encoding="utf-8"))
    print(f"  {len(idx)} записей")
    
    decl = [l.strip().lower() for l in open(DECL, encoding="utf-8") if l.strip()]
    verbs = [w for w in decl if w.endswith(('ть', 'ться')) and w in idx]
    print(f"  глаголов: {len(verbs)}")
    
    # Строим map: stem → base. Сортируем по длине (длинные первыми)
    stems = []
    for base in verbs:
        stem = get_stem(base)
        if stem and len(stem) >= 3:
            stems.append((stem, base))
    stems.sort(key=lambda x: -len(x[0]))  # длинные первыми
    
    # Один проход по word_forms
    word_forms_keys = [k for k, v in idx.items() if v.get('kind') == 'word_forms']
    print(f"  word_forms: {len(word_forms_keys)}")
    
    stats = {
        'fixed_stress': 0,
        'fixed_yo': 0,
        'deleted_garbage': 0,
        'skipped_multi': 0,
        'no_base_found': 0,
    }
    
    print("Обработка...")
    to_delete = []
    
    for w in word_forms_keys:
        # Находим базу
        base = None
        for stem, b in stems:
            if w.startswith(stem) and w != b:
                base = b
                break
        
        if base is None:
            stats['no_base_found'] += 1
            continue
        
        e = idx[w]
        
        # Мусор — удаляем
        if is_garbage_form(w, base):
            to_delete.append(w)
            stats['deleted_garbage'] += 1
            continue
        
        # Многоударные не трогаем
        vowels_count = sum(1 for p in e['phonemes'] if p['type'] == 'vowel')
        stressed_count = sum(1 for p in e['phonemes'] if p['type'] == 'vowel' and p.get('stressed'))
        if stressed_count > 1:
            stats['skipped_multi'] += 1
            continue
        
        # Приоритет ё
        if 'ё' in w:
            k_vowels_ru = [ch for ch in w.lower() if ch in RU_VOWELS]
            yo_idx = None
            for i, ch in enumerate(k_vowels_ru):
                if ch == 'ё':
                    yo_idx = i
                    break
            if yo_idx is not None:
                vowel_indices = get_vowel_positions(e['phonemes'])
                if yo_idx < len(vowel_indices):
                    target = vowel_indices[yo_idx]
                    for p in e['phonemes']:
                        if p['type'] == 'vowel':
                            p['stressed'] = False
                    e['phonemes'][target]['stressed'] = True
                    e['phonemes'][target]['symbol'] = 'o'
                    e['ascii'] = ascii_to_string(e['phonemes'])
                    e['syllables'] = vowels_count
                    stats['fixed_yo'] += 1
                    continue
        
        # Копируем ударение инфинитива
        base_pos = get_stress_pos_from_end(idx[base]['phonemes'])
        if base_pos and apply_stress_at_from_end(e['phonemes'], base_pos):
            e['ascii'] = ascii_to_string(e['phonemes'])
            e['syllables'] = vowels_count
            stats['fixed_stress'] += 1
    
    for w in to_delete:
        del idx[w]
    
    print("\n=== Результат ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print(f"\nСохраняем...")
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    
    broken = [w for w, e in idx.items() if e.get('kind') == 'word_forms'
              and sum(1 for p in e['phonemes'] if p['type'] == 'vowel') > 1
              and sum(1 for p in e['phonemes'] if p['type'] == 'vowel' and p.get('stressed')) != 1]
    print(f"\nБитых word_forms: {len(broken)}")
    if broken:
        print(f"  примеры: {broken[:15]}")
    print(f"Всего: {len(idx)}")


if __name__ == "__main__":
    main()
