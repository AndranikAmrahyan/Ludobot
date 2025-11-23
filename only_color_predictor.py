"""
only_color_predictor.py

Самодостаточный модуль для:
  - оценки моделей на ваших логах (адаптирован для малых и больших наборов данных)
  - быстрого получения предсказания цвета следующего броска из текста лога через predict_from_text(...)

Запуск: Python 3.8+. Требует scikit-learn, pandas, numpy.

Содержит:
  - parse_numbers_from_text(text)
  - color_of(num)
  - build_dataset(numbers, k)
  - evaluate_models(numbers, max_k=MAX_K)
  - train_and_get_predictor(numbers, k, model_name)
  - predict_from_text(text, k, model_name, order='newest')  # удобная обёртка

Примеры использования приведены в блоке __main__.
"""

import re
import numpy as np
import pandas as pd
from collections import Counter
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# RED set (европейская/стандартная раскраска рулетки)
RED = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

# ---- КОНФИГУРАЦИЯ ----

# - LAST_LOG_TEXT: вставьте ваш лог как в примере ниже (можно использовать многострочную строку).
# - K: сколько последних бросков использовать как признаки для модели (по умолчанию 3).
#       Рекомендации:
#         - Обычно K ≈ 20% от длины лога (строк) — округлять вверх до целого, минимум 1, максимум {MAX_K}
#         - При очень коротких логах (<5 строк) прогноз малонадежен
#         - Markov лучше с небольшим K (1-2), RF/Logistic — K=2-3
# - MODEL: 'Markov', 'Logistic' или 'RF' (по умолчанию 'RF').
# - ORDER: 'newest' (в тексте последний первым) или 'oldest' (хронологически) — по умолчанию 'newest'.
#

# Если хотите временно использовать интерактивный режим (через терминал сразу) — присвойте LAST_LOG_TEXT = None.
# Если K = None, то значение k выбирается автоматически:
#    k ≈ 20% от длины лога (округление вверх), минимум 1 и максимум MAX_K.
# Это удобно, если длина лога каждый раз разная — модель сама подберёт оптимальное k.

LAST_LOG_TEXT = """
— 3 (🔴 Красное)
— 0 (🟢 Зеленое)
— 30 (🔴 Красное)
— 22 (⚫️ Чёрное)
— 19 (🔴 Красное)
— 22 (⚫️ Чёрное)
— 31 (⚫️ Чёрное)
— 19 (🔴 Красное)
— 22 (⚫️ Чёрное)
— 31 (⚫️ Чёрное)
— 1 (🔴 Красное)
— 19 (🔴 Красное)
— 0 (🟢 Зеленое)
— 1 (🔴 Красное)
— 22 (⚫️ Чёрное)
"""
# K = 3            # старый вариант — жёстко задать k для всех моделей
K = None           # если None — k будет автоматически подобран отдельно для каждой модели
MODEL = 'RF'
# ORDER = 'newest'

# Максимально допустимое значение k (удобно менять в одном месте)
MAX_K = 4

# --- Описания моделей и рекомендации по размерам лога / выбору k ---
MODEL_DESCRIPTIONS = {
    'Markov': {
        'short': 'Частотная модель по последовательностям цветов. Очень простая, требует мало данных.',
        'when': 'Хороша при крайне малых логах (<=10). Быстрая и интерпретируемая.'
    },
    'Logistic': {
        'short': 'Логистическая регрессия — линейная модель, использующая числовые признаки и run-length.',
        'when': 'Работает лучше при умеренных объёмах (>=20). Может плохо вести себя на очень малых выборках.'
    },
    'RF': {
        'short': 'Random Forest — ансамбль деревьев. Устойчив к шуму и хорошо работает на небольших/средних объёмах.',
        'when': 'Рекомендую по умолчанию для большинства логов (15+).'
    }
}


def color_of(num: int) -> str:
    """Возвращает цвета и "обучает" моделей на русском: 'красное' / 'чёрное' / 'зелёное'."""
    if num == 0:
        return "зелёное"
    return "красное" if num in RED else "чёрное"


def parse_numbers_from_text(text: str) -> list:
    """Парсит последовательность чисел (0..99) из текста.
    Возвращает список int в том же порядке, что и в тексте.
    Работает корректно с EM-DASH (—) и unicode-символами.
    """
    nums = re.findall(r'\b(?:0|[1-9][0-9]?)\b', text)
    return [int(n) for n in nums]


def build_dataset(numbers, k):
    """Строит таблицу признаков для прогноза цвета следующего броска.
    numbers: list интов, ожидается порядок newest-first (index 0 = последний бросок).
    k: число последних бросков, которые используются как признаки.
    Возвращает pd.DataFrame.
    """
    N = len(numbers)
    rows = []
    for t in range(k, N):
        prev = numbers[t-k:t]
        target = numbers[t]
        prev_colors = [color_of(x) for x in prev]
        prev_dozen = [3 if x == 0 else ((x - 1) // 12) for x in prev]
        # run of last color in the prev sequence (tail run length)
        run = 1
        last_color = prev_colors[-1]
        for j in range(len(prev_colors) - 2, -1, -1):
            if prev_colors[j] == last_color:
                run += 1
            else:
                break
        row = {f'num_l{i+1}': prev[-(i+1)] for i in range(k)}
        row.update({f'dozen_l{i+1}': prev_dozen[-(i+1)] for i in range(k)})
        row['run_len_last_color'] = run
        row['target_color'] = color_of(target)
        rows.append(row)
    df = pd.DataFrame(rows)
    # Если df пустой — вернём пустой датафрейм с правильными колонками
    if df.empty:
        cols = [f'num_l{i+1}' for i in range(k)] + [f'dozen_l{i+1}' for i in range(k)] + ['run_len_last_color', 'target_color']
        return pd.DataFrame(columns=cols)
    return df


def evaluate_models(numbers, max_k=MAX_K):
    """Оценка моделей на данных numbers для разных k (1..max_k).

    Подход: расширяющееся окно (time-series style) — последовательно обучаем на первых i строках
    и тестируем на i+1 (как в оригинале), но пороги уменьшены, чтобы работать и на малых N.

    Возвращает pd.DataFrame с усреднёнными точностями для каждой модели по k.
    """
    results = []
    for k in range(1, max_k + 1):
        data = build_dataset(numbers, k)
        if data.empty:
            results.append({'k': k, 'Markov': np.nan, 'Logistic': np.nan, 'RF': np.nan})
            continue
        X = data[[f'num_l{i+1}' for i in range(k)] + [f'dozen_l{i+1}' for i in range(k)] + ['run_len_last_color']].copy()
        for col in [f'num_l{i+1}' for i in range(k)]:
            X[col] = X[col] / 36.0
        y = data['target_color'].values
        le = LabelEncoder(); le.fit(y)
        N = len(X)
        # Минимальный стартовой размер обучающего множества — 5 строк или 10% от N
        train_start = max(5, int(0.1 * N))
        if train_start >= N:
            # Не получается сделать ни одной итерации обучения/тестирования
            results.append({'k': k, 'Markov': np.nan, 'Logistic': np.nan, 'RF': np.nan})
            continue
        step = max(1, int(max(1, N // 10)))  # шаг итерации — при малых N =1, при больших ~N/10
        models = {'Markov': None,
                  'Logistic': LogisticRegression(max_iter=400),
                  'RF': RandomForestClassifier(n_estimators=80, random_state=42)}
        scores = {name: [] for name in models}
        # подготовить цветовые последовательности для Markov
        color_seq = []
        for idx in range(k, k + len(data)):
            prev_nums = numbers[idx-k:idx]
            color_seq.append([color_of(x) for x in prev_nums])
        # expanding-window evaluation
        for i in range(train_start, N, step):
            X_train = X.iloc[:i]; y_train = y[:i]
            X_test = X.iloc[i:i+1]; y_test = y[i]
            # Markov: частотный по последовательностям цветов
            freq = {}
            for seq, nxt in zip(color_seq[:i], y[:i]):
                freq.setdefault(tuple(seq), Counter())[nxt] += 1
            last_key = tuple(color_seq[i])
            if last_key in freq:
                pred_markov = freq[last_key].most_common(1)[0][0]
            else:
                pred_markov = Counter(y_train).most_common(1)[0][0]
            scores['Markov'].append(1 if pred_markov == y_test else 0)
            # Logistic & RF
            for name, model in list(models.items())[1:]:
                try:
                    model.fit(X_train, le.transform(y_train))
                    yp = model.predict(X_test)[0]
                    scores[name].append(1 if yp == le.transform([y_test])[0] else 0)
                except Exception:
                    # на малых данных возможны ошибки — считаем как NaN (не учитываем)
                    pass
        avg_scores = {name: np.nan if len(vals) == 0 else np.mean(vals) for name, vals in scores.items()}
        results.append({'k': k, **avg_scores})
    return pd.DataFrame(results).set_index('k')


def train_and_get_predictor(numbers, k, model_name):
    """Обучает модель на всех доступных данных и возвращает функцию-predictor(latest_prev_newest_first).

    model_name: 'Markov', 'Logistic' или 'RF'
    numbers: list int newest-first
    predictor принимает аргумент latest_prev_newest_first — список, где index 0 = последний бросок.
    """
    data = build_dataset(numbers, k)
    if data.empty:
        raise ValueError("Недостаточно данных для построения признаков: data is empty")
    X = data[[f'num_l{i+1}' for i in range(k)] + [f'dozen_l{i+1}' for i in range(k)] + ['run_len_last_color']].copy()
    for col in [f'num_l{i+1}' for i in range(k)]:
        X[col] = X[col] / 36.0
    y = data['target_color'].values
    le = LabelEncoder(); le.fit(y)

    # сохранём имена колонок, чтобы в predict передавать DataFrame с теми же именами
    feature_columns = X.columns.tolist()

    if model_name == 'Markov':
        freq = {}
        color_seq = []
        for idx in range(k, k + len(data)):
            prev_nums = numbers[idx-k:idx]
            color_seq.append([color_of(x) for x in prev_nums])
        for seq, nxt in zip(color_seq, y):
            freq.setdefault(tuple(seq), Counter())[nxt] += 1

        def predictor(latest_prev_newest_first):
            # latest_prev_newest_first: newest-first (index 0 = last result)
            prev = list(reversed(latest_prev_newest_first[:k]))
            key = tuple([color_of(x) for x in prev])
            if key in freq:
                most = freq[key].most_common(1)[0]
                return most[0], {c: cnt for c, cnt in freq[key].items()}
            else:
                top = Counter(y).most_common(3)
                return top[0][0], {c: cnt for c, cnt in top}

        return predictor, None

    elif model_name == 'Logistic':
        clf = LogisticRegression(max_iter=400)
        clf.fit(X, le.transform(y))

        def predictor(latest_prev_newest_first):
            prev = latest_prev_newest_first[:k]
            num_feats = [prev[i] / 36.0 for i in range(k)]
            dozen_feats = [3 if prev[i] == 0 else ((prev[i] - 1) // 12) for i in range(k)]
            prev_colors = [color_of(x) for x in reversed(prev)]
            run = 1
            for j in range(len(prev_colors) - 2, -1, -1):
                if prev_colors[j] == prev_colors[-1]:
                    run += 1
                else:
                    break
            feat = np.array(num_feats + dozen_feats + [run]).reshape(1, -1)
            # создать DataFrame с теми же именами признаков — тогда sklearn не будет ругаться
            feat_df = pd.DataFrame(feat, columns=feature_columns)
            p_idx = clf.predict(feat_df)[0]
            probs = {le.inverse_transform([i])[0]: prob for i, prob in enumerate(clf.predict_proba(feat_df)[0])}
            return le.inverse_transform([p_idx])[0], probs

        return predictor, clf

    else:
        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(X, le.transform(y))

        def predictor(latest_prev_newest_first):
            prev = latest_prev_newest_first[:k]
            num_feats = [prev[i] / 36.0 for i in range(k)]
            dozen_feats = [3 if prev[i] == 0 else ((prev[i] - 1) // 12) for i in range(k)]
            prev_colors = [color_of(x) for x in reversed(prev)]
            run = 1
            for j in range(len(prev_colors) - 2, -1, -1):
                if prev_colors[j] == prev_colors[-1]:
                    run += 1
                else:
                    break
            feat = np.array(num_feats + dozen_feats + [run]).reshape(1, -1)
            feat_df = pd.DataFrame(feat, columns=feature_columns)
            p_idx = clf.predict(feat_df)[0]
            probs = {le.inverse_transform([i])[0]: prob for i, prob in enumerate(clf.predict_proba(feat_df)[0])}
            return le.inverse_transform([p_idx])[0], probs

        return predictor, clf


def predict_from_text(text: str, k: int, model_name: str = 'RF', order: str = 'newest'):
    """Удобный wrapper: принимает текст лога, парсит числа и возвращает предсказание.

    order: 'newest' (по умолчанию) — значит в тексте index 0 = последний результат.
           'oldest' — в тексте chronological oldest->newest (в этом случае функция перевернёт список).
    Возвращает кортеж (predicted_color, info_dict).
    """
    numbers = parse_numbers_from_text(text)
    if order == 'oldest':
        numbers = list(reversed(numbers))
    if len(numbers) < k + 1:
        raise ValueError(f"Недостаточно чисел в логе для k={k}. Требуется хотя бы k+1 (для таргета). Имеется: {len(numbers)}")
    pred_fn, model = train_and_get_predictor(numbers, k, model_name)
    # predict_fn ожидает список latest_prev_newest_first: index0 = последний бросок
    return pred_fn(numbers[:k])


def recommend_log_size_and_k(n_rows: int):
    """Дадим советы по длине лога и выбору k (пропорция от длины).

    Правило: k ≈ round(0.2 * N), ограничено [1, MAX_K].
    Рекомендации по длине у LAST_LOG_TEXT:
      - min: 6 (чтобы получилось хотя бы 3 обучающих примера при k=2)
      - рекомендовано: 15 (наиболее практично)
      - лучше: >=50 для более устойчивых оценок
    """
    if n_rows is None:
        return 1, 'Длина лога неизвестна — выбрано k=1 по умолчанию. Установите K вручную или K=None для авто-выбора при наличии лога.'
    rec_k = max(1, min(MAX_K, int(round(0.2 * n_rows))))
    if rec_k < 1:
        rec_k = 1
    if n_rows < 8:
        note = 'Слишком мало данных — результаты ненадёжны.'
    elif n_rows < 15:
        note = 'Подходяще, но чем больше — тем лучше.'
    elif n_rows < 50:
        note = 'Хорошо: достаточно для базовой модели (RF).'
    else:
        note = 'Очень хорошо: модель может извлечь стойкие паттерны (если они есть).'
    return rec_k, note


def choose_k_for_model(n_rows: int, model_name: str) -> int:
    """Выбирает k отдельно для каждой модели исходя из длины лога.
    Правила (эвристика):
      - базовая рекомендация rec_k = round(0.2 * N) ограничена 1..MAX_K
      - Markov: предпочитаем очень маленькие k (1 при коротких логах, максимум 2)
      - Logistic: требует больше данных; для коротких логов используем 2, при N>=20 допускаем 3
      - RF: гибкая — используем rec_k (clip 1..MAX_K)
    """
    if n_rows is None or n_rows <= 0:
        return 1
    rec_k = max(1, min(MAX_K, int(round(0.2 * n_rows))))
    model_name = model_name.lower()
    if model_name == 'markov':
        # Markov лучше с k=1..2 (малые k дают более надёжные частотные оценки)
        if n_rows < 12:
            return 1
        return min(2, rec_k)
    if model_name == 'logistic':
        # Logistic: минимум 2, если есть >=20 элементов — можно 3
        if n_rows < 20:
            return min(2, rec_k)
        return min(3, rec_k)
    # RF (RandomForest)
    return rec_k


if __name__ == '__main__':
    def main_demo():
        # --- Соберём числа и проверим вход ---
        text = LAST_LOG_TEXT
        numbers = parse_numbers_from_text(text)
        n = len(numbers)

        print('Распарсенные числа (newest-first):', numbers)
        print(f'Количество строк (чисел) в логе: {n}')

        rec_k, rec_note = recommend_log_size_and_k(n)
        print(f'Общая рекомендованная k (≈20% от N, ограничено 1..{MAX_K}): {rec_k} — {rec_note}')
        print('Рекомендации k по моделям (учитывают длину лога):')
        print('МОДЕЛИ:')
        for name, d in MODEL_DESCRIPTIONS.items():
            k_for = choose_k_for_model(n, name)
            print(f"- {name}: рекомендован k = {k_for} — {d['short']} ({d['when']})")

        # Если числа пустые — выходим с ошибкой
        if n == 0:
            raise SystemExit('В логе не найдено чисел. Проверьте кодировку/формат ввода.')

        # Если K задан явно (не None) — он будет использован для всех моделей
        # иначе k выбирается отдельно для каждой модели через choose_k_for_model
        models_to_run = ['Markov', 'Logistic', 'RF']
        for m in models_to_run:
            k_used = K if K is not None else choose_k_for_model(n, m)
            try:
                pred_fn, trained = train_and_get_predictor(numbers, k_used, m)
                pred, info = pred_fn(numbers[:k_used])
                print('\n=== МОДЕЛЬ:', m, '===')
                print(f'Используемый k = {k_used}')
                print('Предсказание (цвет):', pred)
                print('Детали:', info)
            except Exception as e:
                print(f"Модель {m} завершилась с ошибкой: {e}")

        print('\nГотово.')

    main_demo()