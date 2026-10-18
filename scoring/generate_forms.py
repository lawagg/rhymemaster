#!/usr/bin/env python3
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import json, shutil
from pathlib import Path

BASE = Path.home() / "models"
INDEX = BASE / "phoneme_index_v2.json"
WORK = Path("/mnt/c/Users/admin/Documents/rhymemaster_work")

from g2p import G2P
from ipa_to_ascii import IpaToAscii
from build_phoneme_index import normalize, clean_ipa_string, parse_to_phonemes, build_entry, extract_parts
from slang_morph import SlangMorph


def load_pos_map(path):
    m = {}
    if not path.exists(): return m
    for line in open(path, encoding="utf-8"):
        if '|' not in line: continue
        parts = [x.strip() for x in line.split('|')]
        if len(parts) >= 2 and parts[0] and parts[1]:
            m[parts[0].lower()] = parts[1]
    return m


def main():
    bak = INDEX.with_suffix('.json.bak_before_mat_forms')
    if not bak.exists():
        shutil.copy2(INDEX, bak)
        print(f'бэкап: {bak}')

    print('Загружаем индекс...')
    idx = json.load(open(INDEX, encoding='utf-8'))
    print(f'  было: {len(idx)}')

    decl = [l.strip().lower() for l in open(WORK/'indecl_DECL.txt', encoding='utf-8') if l.strip()]
    print(f'DECL слов: {len(decl)}')

    pos_map = {}
    for fname in ['pos_809_answered.txt', 'pos_643_answered.txt', 'mat_dictionary_clean.txt', 'rude_dictionary.txt']:
        pos_map.update(load_pos_map(WORK / fname))
    print(f'pos-карт: {len(pos_map)}')

    sm = SlangMorph()
    all_forms = []
    skipped = {'ADV': 0, 'INTJ': 0, 'INDECL': 0, 'OTHER': 0}
    for w in decl:
        force_pos = pos_map.get(w)
        if force_pos in ('ADV', 'INTJ', 'INDECL', 'OTHER'):
            skipped[force_pos] += 1
            all_forms.append(w)
            continue
        for f in sm.all_forms(w, force_pos=force_pos):
            all_forms.append(f['form'])
    print(f'  пропущено: {skipped}')
    all_forms = list(dict.fromkeys(all_forms))
    print(f'  уникальных форм: {len(all_forms)}')

    todo = [f for f in all_forms if f not in idx and normalize(f)]
    print(f'  новых: {len(todo)}')

    if not todo:
        print('Нечего добавлять.')
        return

    print('G2P...')
    g2p = G2P()
    conv = IpaToAscii()
    print('готово\n')

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
            print(f'  ошибка {i}: {e}')
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
        print(f'  {min(i+BATCH, len(todo))}/{len(todo)} — {added}')

    with open(INDEX, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False)
    size = INDEX.stat().st_size / 1024 / 1024
    print(f'\nбыло: {len(idx)-added}, стало: {len(idx)}, размер: {size:.0f} МБ')
    print(f'добавлено: {added}, провалов: {len(failed)}')


if __name__ == '__main__':
    main()
