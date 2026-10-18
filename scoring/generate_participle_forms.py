#!/usr/bin/env python3
"""Генерит падежные формы для причастий (действ. и страдат. прош.)."""
import json
import re
from pathlib import Path

INDEX = Path.home() / "models/phoneme_index_v2.json"
WORK = Path("/mnt/c/Users/admin/Documents/rhymemaster_work")

# Паттерны причастий:
# -ший/-вший → мягкое склонение (стем = без -ий)
# -нный/-тый/-мый → твёрдое склонение (стем = без -ый)
# Для -ший: смешанное (свежий: свежая, свежее, свежие)
ADJ_SOFT = {
    'masc': 'ий', 'femn': 'ая', 'neut': 'ее', 'plur': 'ие',
    'gent_masc': 'его', 'gent_femn': 'ей', 'gent_plur': 'их',
    'datv_masc': 'ему', 'datv_femn': 'ей', 'datv_plur': 'им',
    'accs_masc': 'ий', 'accs_femn': 'ую', 'accs_neut': 'ее', 'accs_plur': 'ие',
    'ablt_masc': 'им', 'ablt_femn': 'ей', 'ablt_plur': 'ими',
    'loct_masc': 'ем', 'loct_femn': 'ей', 'loct_plur': 'их',
}
ADJ_HARD = {
    'masc': 'ый', 'femn': 'ая', 'neut': 'ое', 'plur': 'ые',
    'gent_masc': 'ого', 'gent_femn': 'ой', 'gent_plur': 'ых',
    'datv_masc': 'ому', 'datv_femn': 'ой', 'datv_plur': 'ым',
    'accs_masc': 'ый', 'accs_femn': 'ую', 'accs_neut': 'ое', 'accs_plur': 'ые',
    'ablt_masc': 'ым', 'ablt_femn': 'ой', 'ablt_plur': 'ыми',
    'loct_masc': 'ом', 'loct_femn': 'ой', 'loct_plur': 'ых',
}

def detect_participle_pattern(form):
    """Определяет паттерн склонения причастия."""
    w = form.lower()
    # возвратное
    reflexive = False
    if w.endswith('ся'):
        reflexive = True
        w = w[:-2]
    elif w.endswith('сь'):
        reflexive = True
        w = w[:-2]
    
    if w.endswith(('ший', 'вший', 'мший')):
        stem = w[:-2]  # чиливший → чиливш
        return 'soft', stem, reflexive
    if w.endswith(('нный', 'тый', 'мый', 'тый')):
        stem = w[:-2]  # забаненный → забаненн
        return 'hard', stem, reflexive
    
    return None, None, reflexive


def make_forms(form):
    """Возвращает список падежных форм (без исходной)."""
    pat, stem, reflexive = detect_participle_pattern(form)
    if pat is None:
        return []
    
    endings = ADJ_SOFT if pat == 'soft' else ADJ_HARD
    forms = set()
    
    for case in ['masc', 'femn', 'neut', 'plur',
                 'gent_masc', 'gent_femn', 'gent_plur',
                 'datv_masc', 'datv_femn', 'datv_plur',
                 'accs_masc', 'accs_femn', 'accs_neut', 'accs_plur',
                 'ablt_masc', 'ablt_femn', 'ablt_plur',
                 'loct_masc', 'loct_femn', 'loct_plur']:
        ending = endings.get(case)
        if not ending:
            continue
        result = stem + ending
        if reflexive:
            result += 'ся'
        forms.add(result)
    
    return sorted(forms)


def main():
    print("Загружаем индекс...")
    idx = json.load(open(INDEX, encoding="utf-8"))
    print(f"  {len(idx)} записей")
    
    # Загружаем причастия из файлов Harness
    participles = []
    for i in range(1, 5):
        path = WORK / f"participles_batch{i}.txt"
        if not path.exists():
            continue
        for line in open(path, encoding="utf-8"):
            if '|' not in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 3:
                continue
            base, typ, form = parts[0].lower(), parts[1], parts[2].lower()
            if typ in ('ДЕЙСТВ_ПРОШ', 'СТРАДАТ_ПРОШ'):
                participles.append(form)
    
    print(f"  причастий для склонения: {len(participles)}")
    
    # Генерим формы
    all_forms = set()
    for p in participles:
        for f in make_forms(p):
            all_forms.add(f)
    
    print(f"  падежных форм сгенерировано: {len(all_forms)}")
    
    # Фильтр: уже в индексе
    todo = [f for f in all_forms if f not in idx]
    print(f"  новых: {len(todo)}")
    
    if not todo:
        print("Нечего добавлять")
        return
    
    # G2P
    from g2p import G2P
    from ipa_to_ascii import IpaToAscii
    from build_phoneme_index import (
        normalize, clean_ipa_string, parse_to_phonemes, build_entry, extract_parts
    )
    
    print("\nG2P...")
    g2p = G2P()
    conv = IpaToAscii()
    print("готово\n")
    
    BATCH = 50
    added, failed = 0, []
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i+BATCH]
        normed = [normalize(w) for w in batch]
        prepared = [g2p.prepare_input(n) for n in normed if n]
        if not prepared:
            failed.extend(batch); continue
        try:
            results = g2p.model._infer(prepared)
        except Exception as e:
            print(f"  ошибка: {e}")
            failed.extend(batch); continue
        for j, raw in enumerate(results):
            if j >= len(batch): break
            word = batch[j]
            ipa, ipa_borders = extract_parts(raw)
            phon = parse_to_phonemes(conv, ipa_borders)
            if not phon:
                phon = parse_to_phonemes(conv, ipa)
            if not phon:
                failed.append(word); continue
            entry = build_entry(conv, phon, 'word_forms')
            entry['ipa'] = clean_ipa_string(ipa)
            idx[word] = entry
            added += 1
        print(f"  {min(i+BATCH, len(todo))}/{len(todo)} — {added}")
    
    print(f"\nСохраняем...")
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    print(f"  добавлено: {added}, провалов: {len(failed)}")
    print(f"  всего: {len(idx)}")


if __name__ == "__main__":
    main()
