#!/usr/bin/env python3
"""Морфологический модуль для сленга + слогосчёт + глаголы/прилагательные."""
import json
import re
from pathlib import Path
import pymorphy3

morph = pymorphy3.MorphAnalyzer()

VOWELS = set("аоуыэиеёюя")

ETALONS = {
    'masc_cons': {'stem_suffix': '', 'endings': {
        'nomn': '', 'gent': 'а', 'datv': 'у', 'accs': '', 'ablt': 'ом', 'loct': 'е',
        'plur_nomn': 'ы', 'plur_gent': 'ов', 'plur_datv': 'ам', 'plur_accs': 'ы',
        'plur_ablt': 'ами', 'plur_loct': 'ах'}},
    'fem_a': {'stem_suffix': 'а', 'endings': {
        'nomn': 'а', 'gent': 'ы', 'datv': 'е', 'accs': 'у', 'ablt': 'ой', 'loct': 'е',
        'plur_nomn': 'ы', 'plur_gent': '', 'plur_datv': 'ам', 'plur_accs': 'ы',
        'plur_ablt': 'ами', 'plur_loct': 'ах'}},
    'fem_soft': {'stem_suffix': 'ь', 'endings': {
        'nomn': 'ь', 'gent': 'и', 'datv': 'и', 'accs': 'ь', 'ablt': 'ью', 'loct': 'и',
        'plur_nomn': 'и', 'plur_gent': 'ей', 'plur_datv': 'ям', 'plur_accs': 'и',
        'plur_ablt': 'ями', 'plur_loct': 'ях'}},
    'neut_o': {'stem_suffix': 'о', 'endings': {
        'nomn': 'о', 'gent': 'а', 'datv': 'у', 'accs': 'о', 'ablt': 'ом', 'loct': 'е',
        'plur_nomn': 'а', 'plur_gent': '', 'plur_datv': 'ам', 'plur_accs': 'а',
        'plur_ablt': 'ами', 'plur_loct': 'ах'}},
    'neut_e': {'stem_suffix': 'е', 'endings': {
        'nomn': 'е', 'gent': 'я', 'datv': 'ю', 'accs': 'е', 'ablt': 'ем', 'loct': 'е',
        'plur_nomn': 'я', 'plur_gent': 'ей', 'plur_datv': 'ям', 'plur_accs': 'я',
        'plur_ablt': 'ями', 'plur_loct': 'ях'}},
    'neut_yo': {'stem_suffix': 'ё', 'endings': {
        'nomn': 'ё', 'gent': 'я', 'datv': 'ю', 'accs': 'ё', 'ablt': 'ём', 'loct': 'е',
        'plur_nomn': 'я', 'plur_gent': 'ей', 'plur_datv': 'ям', 'plur_accs': 'я',
        'plur_ablt': 'ями', 'plur_loct': 'ях'}},
    'fem_ya': {'stem_suffix': 'я', 'endings': {
        'nomn': 'я', 'gent': 'и', 'datv': 'е', 'accs': 'ю', 'ablt': 'ей', 'loct': 'е',
        'plur_nomn': 'и', 'plur_gent': 'ей', 'plur_datv': 'ям', 'plur_accs': 'и',
        'plur_ablt': 'ями', 'plur_loct': 'ях'}},
    'adj_hard': {'stem_suffix': 'ый', 'endings': {
        'nomn_masc': 'ый', 'nomn_femn': 'ая', 'nomn_neut': 'ое', 'nomn_plur': 'ые',
        'gent_masc': 'ого', 'gent_femn': 'ой', 'gent_plur': 'ых',
        'datv_masc': 'ому', 'datv_femn': 'ой', 'datv_plur': 'ым',
        'accs_masc': 'ый', 'accs_femn': 'ую', 'accs_neut': 'ое', 'accs_plur': 'ые',
        'ablt_masc': 'ым', 'ablt_femn': 'ой', 'ablt_plur': 'ыми',
        'loct_masc': 'ом', 'loct_femn': 'ой', 'loct_plur': 'ых'}},
    'adj_soft': {'stem_suffix': 'ий', 'endings': {
        'nomn_masc': 'ий', 'nomn_femn': 'яя', 'nomn_neut': 'ее', 'nomn_plur': 'ие',
        'gent_masc': 'его', 'gent_femn': 'ей', 'gent_plur': 'их',
        'datv_masc': 'ему', 'datv_femn': 'ей', 'datv_plur': 'им',
        'accs_masc': 'ий', 'accs_femn': 'юю', 'accs_neut': 'ее', 'accs_plur': 'ие',
        'ablt_masc': 'им', 'ablt_femn': 'ей', 'ablt_plur': 'ими',
        'loct_masc': 'ем', 'loct_femn': 'ей', 'loct_plur': 'их'}},
    'adj_sk': {'stem_suffix': 'ий', 'endings': {
        'nomn_masc': 'ий', 'nomn_femn': 'ая', 'nomn_neut': 'ое', 'nomn_plur': 'ие',
        'gent_masc': 'ого', 'gent_femn': 'ой', 'gent_plur': 'их',
        'datv_masc': 'ому', 'datv_femn': 'ой', 'datv_plur': 'им',
        'accs_masc': 'ий', 'accs_femn': 'ую', 'accs_neut': 'ое', 'accs_plur': 'ие',
        'ablt_masc': 'им', 'ablt_femn': 'ой', 'ablt_plur': 'ими',
        'loct_masc': 'ом', 'loct_femn': 'ой', 'loct_plur': 'их'}},
}

CASE_GRAMMEMES = {
    'nomn': {'nomn'}, 'gent': {'gent'}, 'datv': {'datv'},
    'accs': {'accs'}, 'ablt': {'ablt'}, 'loct': {'loct'},
}
CASE_LABELS = {'nomn': 'им.', 'gent': 'род.', 'datv': 'дат.', 'accs': 'вин.', 'ablt': 'тв.', 'loct': 'пр.'}


class SlangMorph:
    def __init__(self, slang_dict_path=None):
        if slang_dict_path is None:
            slang_dict_path = Path.home() / "models/slang_datasets/unified_slang_clean.json"
        self.slang_dict_path = Path(slang_dict_path)
        self.slang_words = set()
        self._load_slang()

    def _load_slang(self):
        if not self.slang_dict_path.exists():
            return
        with open(self.slang_dict_path, encoding="utf-8") as f:
            data = json.load(f)
        self.slang_words = set(k.lower() for k in data.keys())

    def is_slang(self, word: str) -> bool:
        return word.lower() in self.slang_words

    @staticmethod
    def detect_pattern(word: str) -> str:
        w = word.lower()
        if w.endswith('ский') or w.endswith('цкий'):
            return 'adj_sk'
        if w.endswith('ый'):
            return 'adj_hard'
        if w.endswith('ий'):
            return 'adj_soft'
        if w.endswith(('ость', 'есть', 'ность', 'мость')):
            return 'fem_soft'
        if w.endswith('ё'):
            return 'neut_yo'
        if w.endswith('е'):
            return 'neut_e'
        if w.endswith('о'):
            return 'neut_o'
        if w.endswith('я'):
            return 'fem_ya'
        if w.endswith('а'):
            return 'fem_a'
        if w.endswith('ь'):
            return 'fem_soft'
        return 'masc_cons'

    @staticmethod
    def _fix_spelling(word: str) -> str:
        if len(word) >= 2 and word.endswith('ы'):
            if word[-2] in 'кгхшщчж':
                return word[:-1] + 'и'
        return word

    @staticmethod
    def count_syllables(word: str) -> int:
        w = word.lower().strip()
        if not w:
            return 0
        w = re.sub(r'[^а-яё]', '', w)
        return sum(1 for ch in w if ch in VOWELS)

    def detect_pos(self, word: str) -> str:
        w = word.lower().strip()
        p = morph.parse(w)[0]
        # доверяем pymorphy3 только если слово реально в его словаре
        if p.is_known and p.score >= 0.5:
            pos = p.tag.POS
            if pos in ('INFN', 'VERB', 'GRND'):
                return 'VERB'
            if pos in ('ADJF', 'ADJS', 'COMP'):
                return 'ADJ'
            if pos == 'NOUN':
                return 'NOUN'
        # эвристика по окончанию
        stem = w
        if w.endswith(('ся', 'сь')):
            stem = w[:-2]
        if stem.endswith(('ить', 'ать', 'ять', 'еть', 'ыть', 'оть', 'уть')):
            return 'VERB'
        pat = self.detect_pattern(w)
        if pat.startswith('adj_'):
            return 'ADJ'
        return 'NOUN'

    def inflect(self, word: str, case: str = 'nomn', number: str = 'sing') -> str:
        w = word.lower().strip()
        pattern = self.detect_pattern(w)
        is_adj = pattern.startswith('adj_')
        if not self.is_slang(w) and not is_adj:
            p = morph.parse(w)[0]
            grams = CASE_GRAMMEMES.get(case, {'nomn'}) | ({'sing'} if number == 'sing' else {'plur'})
            f = p.inflect(grams)
            return f.word if f else w
        et = ETALONS[pattern]
        suffix = et['stem_suffix']
        stem = w[:-len(suffix)] if (suffix and w.endswith(suffix)) else w
        key = f'plur_{case}' if number == 'plur' else case
        ending = et['endings'].get(key, '')
        return self._fix_spelling(stem + ending)

    def _noun_forms(self, word: str) -> list:
        w = word.lower().strip()
        pattern = self.detect_pattern(w)
        et = ETALONS[pattern]
        suffix = et['stem_suffix']
        stem = w[:-len(suffix)] if (suffix and w.endswith(suffix)) else w
        results = []
        seen = set()
        for number in ['sing', 'plur']:
            for case in ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']:
                key = f'plur_{case}' if number == 'plur' else case
                ending = et['endings'].get(key, '')
                form = self._fix_spelling(stem + ending)
                if form in seen:
                    continue
                seen.add(form)
                results.append({
                    'form': form, 'pos': 'NOUN',
                    'case': case, 'case_label': CASE_LABELS[case],
                    'number': number,
                    'syllables': self.count_syllables(form),
                })
        return results

    def _adj_forms(self, word: str) -> list:
        w = word.lower().strip()
        p = morph.parse(w)[0]
        confident = p.score >= 0.5 and p.tag.POS in ('ADJF', 'ADJS')
        results = []
        seen = set()

        if confident:
            # путь через pymorphy3
            for number in ['sing', 'plur']:
                for case in ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']:
                    genders = ['masc', 'femn', 'neut'] if number == 'sing' else [None]
                    for gender in genders:
                        grams = CASE_GRAMMEMES[case] | {number}
                        if gender:
                            grams.add(gender)
                        f = p.inflect(grams)
                        if not f or f.word in seen:
                            continue
                        seen.add(f.word)
                        label = CASE_LABELS[case]
                        if gender:
                            label += f" {gender[:2]}."
                        results.append({
                            'form': f.word, 'pos': 'ADJ',
                            'case': case, 'case_label': label,
                            'number': number,
                            'syllables': self.count_syllables(f.word),
                        })
            return results

        # fallback — эталон
        pattern = self.detect_pattern(w)
        if not pattern.startswith('adj_'):
            pattern = 'adj_hard'
        et = ETALONS[pattern]
        suffix = et['stem_suffix']
        stem = w[:-len(suffix)] if (suffix and w.endswith(suffix)) else w
        for number in ['sing', 'plur']:
            for case in ['nomn', 'gent', 'datv', 'accs', 'ablt', 'loct']:
                genders = ['masc', 'femn', 'neut'] if number == 'sing' else [None]
                for gender in genders:
                    if number == 'sing':
                        key = f'{case}_{gender}'
                    else:
                        key = f'{case}_plur'
                    ending = et['endings'].get(key)
                    if ending is None:
                        continue
                    form = self._fix_spelling(stem + ending)
                    if form in seen:
                        continue
                    seen.add(form)
                    label = CASE_LABELS[case]
                    if gender:
                        label += f" {gender[:2]}."
                    results.append({
                        'form': form, 'pos': 'ADJ',
                        'case': case, 'case_label': label,
                        'number': number,
                        'syllables': self.count_syllables(form),
                    })
        return results

    def _verb_forms(self, word: str) -> list:
        w = word.lower().strip()
        results = []
        seen = set()

        def add(form, label, tense=None):
            if form and form not in seen:
                seen.add(form)
                results.append({
                    'form': form, 'pos': 'VERB', 'case': 'verb',
                    'case_label': label, 'number': 'sing',
                    'tense': tense, 'syllables': self.count_syllables(form),
                })

        add(w, 'инф.')

        p = morph.parse(w)[0]
        pymorphy_confident = p.score >= 0.7 and p.tag.POS in ('INFN', 'VERB')

        if pymorphy_confident:
            for tense, tense_lbl in [('pres', 'наст.'), ('futr', 'буд.')]:
                for person, person_lbl in [('1per', '1л'), ('2per', '2л'), ('3per', '3л')]:
                    for number in ['sing', 'plur']:
                        f = p.inflect({tense, person, number})
                        if f:
                            add(f.word, f'{tense_lbl} {person_lbl} {number[:2]}.', tense)
            for gender, gender_lbl in [('masc', 'м'), ('femn', 'ж'), ('neut', 'с')]:
                f = p.inflect({'past', gender, 'sing'})
                if f:
                    add(f.word, f'прош. {gender_lbl}.', 'past')
            f = p.inflect({'past', 'plur'})
            if f:
                add(f.word, 'прош. мн.', 'past')
            for number, num_lbl in [('sing', 'ед'), ('plur', 'мн')]:
                f = p.inflect({'impr', number})
                if f:
                    add(f.word, f'повел. {num_lbl}.', 'impr')
            return results

        reflexive = False
        base = w
        if base.endswith('ся'):
            reflexive = True
            base = base[:-2]
        elif base.endswith('сь'):
            reflexive = True
            base = base[:-2]

        if base.endswith('ить'):
            stem = base[:-3]
            conj = 2
        elif base.endswith(('ать', 'ять', 'еть', 'ыть', 'оть', 'уть')):
            stem = base[:-3]
            conj = 1
        else:
            return results

        def alter(s):
            if s.endswith('с'):
                return s[:-1] + 'ш'
            if s.endswith('з'):
                return s[:-1] + 'ж'
            return s

        if conj == 2:
            forms = {
                '1per_sing': alter(stem) + 'ю',
                '2per_sing': stem + 'ишь',
                '3per_sing': stem + 'ит',
                '1per_plur': stem + 'им',
                '2per_plur': stem + 'ите',
                '3per_plur': stem + 'ят',
            }
        else:
            v = base[-2]
            forms = {
                '1per_sing': stem + v + 'ю',
                '2per_sing': stem + v + 'ешь',
                '3per_sing': stem + v + 'ет',
                '1per_plur': stem + v + 'ем',
                '2per_plur': stem + v + 'ете',
                '3per_plur': stem + v + 'ют',
            }

        if reflexive:
            suffix_map = {
                '1per_sing': 'сь', '2per_sing': 'ся', '3per_sing': 'ся',
                '1per_plur': 'ся', '2per_plur': 'сь', '3per_plur': 'ся',
            }
            forms = {k: v + suffix_map[k] for k, v in forms.items()}

        for key, form in forms.items():
            person = key.split('_')[0]
            number = key.split('_')[1]
            add(form, f'наст. {person[0]}л. {number[:2]}.', 'pres')

        past_stem = base[:-2]
        past_forms = [
            (past_stem + 'л', 'прош. м.'),
            (past_stem + 'ла', 'прош. ж.'),
            (past_stem + 'ло', 'прош. с.'),
            (past_stem + 'ли', 'прош. мн.'),
        ]
        for form, label in past_forms:
            if reflexive:
                form = form + 'сь' if form.endswith('л') else form + 'ся'
            add(form, label, 'past')

        if conj == 2:
            imp_sing = base[:-3] + 'и'
            imp_plur = base[:-3] + 'ите'
        else:
            v = base[-2]
            imp_sing = base[:-3] + v + 'й'
            imp_plur = base[:-3] + v + 'йте'

        if reflexive:
            imp_sing += 'сь'
            imp_plur += 'сь'

        add(imp_sing, 'повел. ед.', 'impr')
        add(imp_plur, 'повел. мн.', 'impr')

        return results

    def all_forms(self, word: str, force_pos: str = None) -> list:
        w = word.lower().strip()
        pos = force_pos if force_pos else self.detect_pos(w)
        if pos == 'VERB':
            return self._verb_forms(w)
        if pos == 'ADJ':
            return self._adj_forms(w)
        if pos == 'NOUN':
            return self._noun_forms(w)
        # ADV, INTJ, INDECL, OTHER — одна форма
        return [{
            'form': w, 'pos': pos or 'OTHER', 'case': '-', 'case_label': '-',
            'number': '-', 'syllables': self.count_syllables(w),
        }]

    def find_forms_with_syllables(self, word: str, n: int) -> list:
        return [f for f in self.all_forms(word) if f['syllables'] == n]

    def find_forms_in_range(self, word: str, min_n: int, max_n: int) -> list:
        return [f for f in self.all_forms(word) if min_n <= f['syllables'] <= max_n]


if __name__ == "__main__":
    sm = SlangMorph()
    print(f"Загружено: {len(sm.slang_words)} сленговых слов\n")

    for word in ['вайб', 'чилить', 'кринжовый', 'агриться', 'ассист']:
        print(f"=== '{word}' ({sm.detect_pos(word)}) ===")
        forms = sm.all_forms(word)
        print(f"  Всего форм: {len(forms)}")
        for f in forms[:20]:
            print(f"    {f['form']:<15} {f['case_label']:<15} слогов: {f['syllables']}")
        if len(forms) > 20:
            print(f"    ... и ещё {len(forms) - 20}")
        print()
