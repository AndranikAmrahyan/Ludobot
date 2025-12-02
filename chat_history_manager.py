import os
import json
import re
from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Конфигурируемые параметры
MAX_HISTORY_LENGTH = 30  # Максимальная длина сохраненной истории
MIN_MATCHES = max(5, min(MAX_HISTORY_LENGTH // 3, 10))  # Минимальное количество совпадений. # Минимальное количество совпадающих логов, чтобы понимать что полученная история - это продолжение сохранённой
RESET_TIME_UTC = time(21, 0)  # 21:00 UTC

# Глобальные переменные
chat_histories: Dict[str, str] = {}  # История каждого чата
chat_predictions: Dict[str, dict] = {}  # Последнее предсказание для каждого чата: {'prediction': str, 'message_id': int}
stats_total = 0  # Общее количество предсказаний
stats_correct = 0  # Количество правильных предсказаний
stats_reset_date = ""  # Дата последнего сброса статистики (YYYY-MM-DD)

# Файлы для сохранения данных
HISTORY_FILE = "chat_histories.json"
PREDICTIONS_FILE = "chat_predictions.json"
STATS_FILE = "stats.json"

def load_data():
    """Загружает все данные из файлов"""
    global chat_histories, chat_predictions, stats_total, stats_correct, stats_reset_date
    
    # Загружаем истории чатов
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                if os.path.getsize(HISTORY_FILE) > 0:
                    chat_histories = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке историй: {e}")
        chat_histories = {}
    
    # Загружаем предсказания
    try:
        if os.path.exists(PREDICTIONS_FILE):
            with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
                if os.path.getsize(PREDICTIONS_FILE) > 0:
                    chat_predictions = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке предсказаний: {e}")
        chat_predictions = {}
    
    # Загружаем статистику
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                if os.path.getsize(STATS_FILE) > 0:
                    stats_data = json.load(f)
                    stats_total = stats_data.get("total", 0)
                    stats_correct = stats_data.get("correct", 0)
                    stats_reset_date = stats_data.get("reset_date", "")
                    
                    # Проверяем, нужно ли сбросить статистику
                    check_and_reset_stats()
    except Exception as e:
        logger.error(f"Ошибка при загрузке статистики: {e}")
        stats_total = 0
        stats_correct = 0
        stats_reset_date = get_today_key()

def save_data():
    """Сохраняет все данные в файлы"""
    try:
        # Сохраняем истории
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_histories, f, ensure_ascii=False, indent=2)
        
        # Сохраняем предсказания
        with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_predictions, f, ensure_ascii=False, indent=2)
        
        # Сохраняем статистику
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "total": stats_total, 
                "correct": stats_correct,
                "reset_date": stats_reset_date
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")

def get_today_key():
    """Возвращает ключ для сегодняшней даты"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def should_reset_stats():
    """Проверяет, нужно ли сбросить статистику (если сейчас после 21:00 UTC)"""
    now_utc = datetime.now(timezone.utc)
    reset_datetime = datetime.combine(now_utc.date(), RESET_TIME_UTC).replace(tzinfo=timezone.utc)
    return now_utc >= reset_datetime

def check_and_reset_stats():
    """Проверяет и сбрасывает статистику если нужно"""
    global stats_total, stats_correct, stats_reset_date, chat_predictions
    
    today_key = get_today_key()
    
    # Проверяем, нужно ли сбросить статистику
    if should_reset_stats():
        # Если еще не сбрасывали сегодня или сбрасывали вчера
        if stats_reset_date != today_key:
            # Сбрасываем статистику
            stats_total = 0
            stats_correct = 0
            stats_reset_date = today_key
            
            # Очищаем все предсказания
            chat_predictions.clear()
            
            logger.info(f"Статистика сброшена (сейчас после 21:00 UTC). Дата сброса: {today_key}")
            
            # Сохраняем данные
            save_data()

def parse_history_text(text: str) -> List[str]:
    """Парсит текст истории на отдельные строки"""
    return [line.strip() for line in text.split('\n') if line.strip()]

def extract_color_from_line(line: str) -> str:
    """Извлекает цвет из строки истории"""
    # Паттерн для строки типа "— 18 (🔴 Красное)"
    match = re.match(r'^—\s*\d+\s*\((.+?)\)', line)
    if match:
        color_text = match.group(1).strip()
        color_text_lower = color_text.lower()
        
        if '🔴' in color_text or 'красн' in color_text_lower:
            return 'красное'
        elif '⚫️' in color_text or '⚫' in color_text or 'чёрн' in color_text_lower or 'черн' in color_text_lower:
            return 'чёрное'
        elif '🟢' in color_text or 'зелен' in color_text_lower:
            return 'зелёное'
    
    return None

def normalize_prediction(prediction: str) -> str:
    """Нормализует предсказание для сравнения"""
    prediction_lower = prediction.lower()
    
    if 'красн' in prediction_lower:
        return 'красное'
    elif 'чёрн' in prediction_lower or 'черн' in prediction_lower:
        return 'чёрное'
    elif 'зелен' in prediction_lower:
        return 'зелёное'
    
    return prediction

def update_chat_history(clean_log_text: str, chat_id: str) -> str:
    """
    Обновляет историю чата и проверяет предсказания.
    
    Args:
        clean_log_text: Очищенный текст истории рулетки
        chat_id: ID чата
        
    Returns:
        str: Обновленный текст истории для предсказаний
    """
    global stats_total, stats_correct
    
    # Загружаем данные при первом вызове
    if not chat_histories:
        load_data()
    
    # Проверяем и сбрасываем статистику если нужно
    check_and_reset_stats()
    
    # Преобразуем chat_id в строку
    chat_id_str = str(chat_id)
    
    # Получаем текущую сохраненную историю
    saved_history = chat_histories.get(chat_id_str, "").strip()
    
    # Получаем сохраненное предсказание для этого чата
    saved_prediction_data = chat_predictions.get(chat_id_str)
    
    # Если история пустая или не существует, сохраняем новую и возвращаем
    if not saved_history:
        chat_histories[chat_id_str] = clean_log_text
        save_data()
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
    
    # Проверяем предсказание, если оно есть и non_matching_part не пустой
    # И только если есть достаточно совпадений (len(matching_part) >= MIN_MATCHES)
    if saved_prediction_data and non_matching_part and len(matching_part) >= MIN_MATCHES:
        # Берём последнюю строку из non_matching_part
        last_line = non_matching_part[-1]
        actual_color = extract_color_from_line(last_line)
        
        if actual_color:
            # Нормализуем предсказание
            normalized_prediction = normalize_prediction(saved_prediction_data.get('prediction', ''))
            
            # Сравниваем
            is_correct = (normalized_prediction == actual_color)
            
            # Обновляем статистику
            stats_total += 1
            if is_correct:
                stats_correct += 1
            
            logger.info(f"Проверка предсказания для чата {chat_id_str}: "
                       f"предсказание '{normalized_prediction}' vs результат '{actual_color}' -> {is_correct}")
    
    # Проверяем результаты совпадений
    if len(matching_part) >= MIN_MATCHES:
        # Достаточно совпадений - объединяем non_matching_part с сохраненной историей
        updated_lines = non_matching_part + saved_lines
    else:
        # Недостаточно совпадений - заменяем историю полностью
        updated_lines = new_lines
        # Если история заменена полностью, удаляем предсказание для этого чата
        if chat_id_str in chat_predictions:
            del chat_predictions[chat_id_str]
            logger.info(f"История чата {chat_id_str} заменена полностью, предсказание удалено")
    
    # Обрезаем до MAX_HISTORY_LENGTH если нужно
    if len(updated_lines) > MAX_HISTORY_LENGTH:
        updated_lines = updated_lines[:MAX_HISTORY_LENGTH]
    
    # Обновляем сохраненную историю
    updated_history = "\n".join(updated_lines)
    chat_histories[chat_id_str] = updated_history
    
    # Сохраняем все данные
    save_data()
    
    return updated_history

def save_prediction(chat_id: str, message_id: int, prediction: str):
    """
    Сохраняет предсказание для чата.
    
    Args:
        chat_id: ID чата
        message_id: ID сообщения с логами, на которое сделано предсказание
        prediction: Предсказание (например, "красное", "чёрное")
    """
    chat_id_str = str(chat_id)
    chat_predictions[chat_id_str] = {
        'prediction': prediction,
        'message_id': message_id
    }
    save_data()
    logger.info(f"Сохранено предсказание для чата {chat_id_str} на сообщение {message_id}: {prediction}")

def get_prediction_data(chat_id: str) -> Optional[dict]:
    """
    Возвращает сохраненное предсказание и message_id для чата.
    
    Args:
        chat_id: ID чата
        
    Returns:
        Optional[dict]: {'prediction': str, 'message_id': int} или None
    """
    chat_id_str = str(chat_id)
    return chat_predictions.get(chat_id_str)

def get_current_stats() -> Tuple[int, int]:
    """
    Возвращает текущую статистику.
    
    Returns:
        Tuple[int, int]: (правильные предсказания, общее количество предсказаний)
    """
    # Проверяем и сбрасываем статистику если нужно
    check_and_reset_stats()
    return stats_correct, stats_total

def clear_chat_prediction(chat_id: str):
    """
    Очищает сохраненное предсказание для чата.
    
    Args:
        chat_id: ID чата
    """
    chat_id_str = str(chat_id)
    if chat_id_str in chat_predictions:
        del chat_predictions[chat_id_str]
        save_data()
        logger.info(f"Очищено предсказание для чата {chat_id_str}")

# Загружаем данные при импорте модуля
load_data()