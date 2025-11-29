import os
import json
from typing import Dict, List, Tuple

# Конфигурируемые параметры
MAX_HISTORY_LENGTH = 30  # Максимальная длина сохраненной истории

# Минимальное количество совпадающих логов, чтобы понимать что полученная история - это продолжение сохранённой
MIN_MATCHES = max(5, min(MAX_HISTORY_LENGTH // 3, 10))

# Глобальная переменная для хранения историй чатов
chat_histories: Dict[str, str] = {}

# Файл для сохранения данных между перезапусками
HISTORY_FILE = "chat_histories.json"

def load_histories():
    """Загружает истории чатов из файла"""
    global chat_histories
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                chat_histories = json.load(f)
    except Exception as e:
        print(f"Ошибка при загрузке историй: {e}")
        chat_histories = {}

def save_histories():
    """Сохраняет истории чатов в файл"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_histories, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении историй: {e}")

def parse_history_text(text: str) -> List[str]:
    """Парсит текст истории на отдельные строки"""
    return [line.strip() for line in text.split('\n') if line.strip()]

def update_chat_history(clean_log_text: str, chat_id: str) -> str:
    """
    Обновляет историю чата и возвращает обработанный текст для предсказаний.
    
    Args:
        clean_log_text: Очищенный текст истории рулетки
        chat_id: ID чата
        
    Returns:
        str: Обновленный текст истории для предсказаний
    """
    # Загружаем истории при первом вызове
    if not chat_histories:
        load_histories()
    
    # Преобразуем chat_id в строку для consistency
    chat_id_str = str(chat_id)
    
    # Получаем текущую сохраненную историю
    saved_history = chat_histories.get(chat_id_str, "").strip()
    
    # Если история пустая или не существует, сохраняем новую и возвращаем
    if not saved_history:
        chat_histories[chat_id_str] = clean_log_text
        save_histories()
        return clean_log_text
    
    # Парсим обе истории на строки
    new_lines = parse_history_text(clean_log_text)
    saved_lines = parse_history_text(saved_history)
    
    # Переменные для алгоритма
    non_matching_part = []  # Переменная 1 - несовпадения
    matching_part = []       # Переменная 2 - совпадения
    
    # Курсоры
    i = 0  # Курсор для new_lines
    j = 0  # Курсор для saved_lines
    
    # Алгоритм сравнения
    while i < len(new_lines):
        if j < len(saved_lines) and new_lines[i] == saved_lines[j]:
            # Совпадение найдено
            matching_part.append(new_lines[i])
            i += 1
            j += 1
        else:
            # Несовпадение
            if matching_part:
                # Если до этого были совпадения, сбрасываем matching_part в non_matching_part
                non_matching_part.extend(matching_part)
                matching_part = []
                j = 0  # Сбрасываем курсор сохраненной истории
                # i не увеличиваем - проверяем ту же строку снова
            else:
                # Не было совпадений до этого, просто добавляем в non_matching_part
                non_matching_part.append(new_lines[i])
                i += 1
                j = 0  # Сбрасываем курсор сохраненной истории
    
    # Проверяем результаты
    if len(matching_part) >= MIN_MATCHES:
        # Достаточно совпадений - объединяем non_matching_part с сохраненной историей
        updated_lines = non_matching_part + saved_lines
    else:
        # Недостаточно совпадений - заменяем историю полностью
        updated_lines = new_lines
    
    # Обрезаем до MAX_HISTORY_LENGTH если нужно
    if len(updated_lines) > MAX_HISTORY_LENGTH:
        updated_lines = updated_lines[:MAX_HISTORY_LENGTH]
    
    # Обновляем сохраненную историю
    updated_history = "\n".join(updated_lines)
    chat_histories[chat_id_str] = updated_history
    save_histories()
    
    return updated_history

# Загружаем истории при импорте модуля
load_histories()