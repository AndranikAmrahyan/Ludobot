# НЕ ОЧИСТИТЬ КЭШ В RENDER - ПОТЕРЯЕШЬ ДАННЫЕ!
# Если ошибка о конфликте, нужно создать новый токен бота: Телеграм @BotFather - команда /revoke
# ТОЛЬКО для Render прямо в коде дать BOT_TOKEN

import logging
import threading
import asyncio
import aiohttp
import os
import re
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, Bot
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)
import signal
import sys
from functools import partial

# Импортируем модуль для предсказаний
import only_color_predictor as ocp
# Импортируем модуль для управления историей чатов и статистики
import chat_history_manager as chm

# Загрузка переменных окружения
load_dotenv()

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Конфигурация
class Config:
    BOT_TOKEN = "7487925725:AAHzJyVWRG2fklT0hQvaXrq-Cawq9vzomEQ"  # os.getenv("BOT_TOKEN")
    RENDER_APP_URL = "https://einstein-point-bot.onrender.com"  # os.getenv("RENDER_APP_URL")
    ALLOWED_CHAT_IDS = [-1002157100033, -1002439723121, -1002248982019]  # @Family_Worlds | @Einstein_bot_test_2 | Group(Private): BOT TEST
    CREATOR = "@andranik_amrahyan"
    
    # Конфигурация для отслеживания предсказаний
    ROULETTE_BOT_ID = 6964500387  # Айди игрового бота рулетки
    
    # Минимальное количество логов для анализа
    MIN_RESULTS_FOR_ANALYSIS = 5
    
    # Конфигурация персонажей
    CHARACTERS = {
        'Markov': {
            'name': 'Андраник',
            'description': 'паттерны последовательностей цветов',
            'emoji': '🔍'
        },
        'Logistic': {
            'name': 'Мюнхен', 
            'description': 'математические закономерности и длины серий',
            'emoji': '📊'
        },
        'RF': {
            'name': 'Кирилл',
            'description': 'множество признаков и последовательностей',
            'emoji': '🎯'
        }
    }

# Инициализация Flask
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Telegram Bot is running!"

@app_flask.route("/ping")
def ping():
    return "pong", 200

def run_web_server():
    app_flask.run(host="0.0.0.0", port=8080)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    help_text = (
        "🎰 <b>Ludobot - Помощь</b>\n\n"
        "🔮 <b>Команда /ludobot:</b>\n"
        "Отправьте команду <code>/ludobot</code> в ответ на сообщение с историей рулетки, чтобы получить прогнозы от наших экспертов\n\n"
        "💡 <b>Команда /rec:</b>\n"
        "Рекомендации по стратегии игры\n\n"
        "ℹ️ <b>Команда /help:</b>\n"
        "Показать это сообщение\n\n"
        "👥 <b>Наши эксперты:</b>\n"
    )
    
    # Добавляем информацию о персонажах
    for model, char_info in Config.CHARACTERS.items():
        help_text += f"• {char_info['emoji']} <b>{char_info['name']}</b> - анализирует {char_info['description']}\n"
    
    help_text += (
        f"\n📋 <b>Формат истории рулетки:</b>\n"
        "<code>\n"
        "— 22 (⚫️ Чёрное)\n"
        "— 31 (⚫️ Чёрное)\n"
        "— 1 (🔴 Красное)\n"
        "...\n"
        "</code>\n"
        f"👨💻 Создатель: {Config.CREATOR}"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def rec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда рекомендаций"""
    rec_text = (
        "🎯 <b>Рекомендации по стратегии игры:</b>\n\n"
        
        "🟢 <b>Про ноль:</b>\n"
        "• Модели не предсказывают зелёный цвет (0)\n"
        "• Рекомендуется всегда ставить небольшую фиксированную сумму на 0\n"
        "• Или не ставить - пока вы уверены что зелёный не выпадет\n\n"
        
        "🎲 <b>Основная стратегия:</b>\n"
        "• Выбирайте цвет, который предсказали как минимум 2 из 3 моделей\n"
        "• Начинайте с небольшой суммы ставки\n"
        "• Если ставка не сыграла - немного увеличьте сумму следующей ставки\n"
        "• Продолжайте ставить на цвет, который предскажут, пока не выиграете\n"
        "• После выигрыша вернитесь к начальной сумме ставки\n\n"
        
        "⚠️ <b>Важные предупреждения:</b>\n"
        "• Играйте ответственно и только на те деньги, которые можете позволить себе потерять\n"
        "• Помните, что рулетка - это игра случая\n"
        "• Никакая стратегия не гарантирует 100% выигрыш\n"
        "• Устанавливайте лимиты потерь перед началом игры\n\n"
        
        "📈 <b>Управление балансом:</b>\n"
        "• Разделите ваш баланс на 20-50 частей\n"
        "• Одна ставка = 1 часть баланса\n"
        "• Не превышайте 5% баланса на одну ставку\n"
        "• При удвоении баланса заберите половину выигрыша\n\n"
        
        "🔄 <b>Дисциплина:</b>\n"
        "• Придерживайтесь выбранной стратегии\n"
        "• Не поддавайтесь эмоциям\n"
        "• Делайте перерывы в игре\n"
        "• Анализируйте результаты\n\n"
        #
        # f"🤖 Рекомендации от: {Config.CREATOR}"
    )
    await update.message.reply_text(rec_text, parse_mode="HTML")

async def ludobot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /ludobot"""
    # await update.message.reply_text(
    #     "🎰 <b>Технический перерыв</b>\n"
    #     "Бот проходит обновление, чтобы покорять сердца игроков.",
    #     parse_mode="HTML",
    #     reply_to_message_id=update.message.message_id
    # )
    # return
    
    # Проверяем, что команда является ответом на сообщение
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте команду /ludobot в ответ на сообщение с историей рулетки.",
            reply_to_message_id=update.message.message_id
        )
        return

    chat_id = update.effective_chat.id
    replied_message = update.message.reply_to_message
    text = replied_message.text or replied_message.caption

    if not text:
        await update.message.reply_text(
            "❌ Сообщение, на которое вы ответили, не содержит текста.",
            reply_to_message_id=update.message.message_id
        )
        return

    # Очищаем текст от лишних строк и оставляем только строки с результатами рулетки
    lines = text.split('\n')
    roulette_pattern = r'^—\s*(\d+)\s*\((.+)\)'
    found_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:  # Пропускаем пустые строки
            continue
        match = re.match(roulette_pattern, line)
        if match:
            found_lines.append(line)

    if not found_lines:
        await update.message.reply_text(
            "❌ Сообщение, на которое вы ответили, не содержит историю рулетки в правильном формате.\n"
            "Формат должен быть:\n"
            "— 22 (⚫️ Чёрное)\n"
            "— 31 (⚫️ Чёрное)\n"
            "— 1 (🔴 Красное)",
            reply_to_message_id=update.message.message_id
        )
        return
    
    if len(found_lines) < Config.MIN_RESULTS_FOR_ANALYSIS:  # Минимум логов для анализа
        await update.message.reply_text(
            f"❌ Для анализа необходимо как минимум {Config.MIN_RESULTS_FOR_ANALYSIS} результатов в истории рулетки.",
            reply_to_message_id=update.message.message_id
        )
        return

    # Сохраняем очищенные строки в переменную для передачи в predictor
    clean_log_text = "\n".join(found_lines)
    
    # Обновляем историю чата (Прибавляем к старой, имеющейся истории текущего чата)
    updated_history = chm.update_chat_history(clean_log_text, chat_id)
    # print(updated_history)
    
    # Получаем текущую статистику для отображения
    correct_predictions, total_predictions = chm.get_current_stats()
    win_rate = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
    
    try:
        # Передаем очищенный текст в модуль предсказаний
        ocp.LAST_LOG_TEXT = updated_history
        
        # Получаем предсказания от всех моделей
        models_to_run = ['Markov', 'Logistic', 'RF']
        predictions = []
        
        for model in models_to_run:
            try:
                # Используем автоматический выбор k для каждой модели
                numbers = ocp.parse_numbers_from_text(updated_history)
                n = len(numbers)
                k_used = ocp.choose_k_for_model(n, model)
                
                pred_fn, trained = ocp.train_and_get_predictor(numbers, k_used, model)
                pred, info = pred_fn(numbers[:k_used])
                
                predictions.append({
                    'model': model,
                    'k': k_used,
                    'prediction': pred,
                    'info': info
                })
                
            except Exception as e:
                logger.error(f"Ошибка в модели {model}: {e}")
                predictions.append({
                    'model': model,
                    'k': 0,
                    'prediction': f"Ошибка: {str(e)}",
                    'info': {}
                })

        # Формируем ответное сообщение с персонажами
        response = "🎰 <b>Прогнозы наших экспертов:</b>\n\n"
        
        for pred in predictions:
            model_name = pred['model']
            prediction = pred['prediction']
            k_used = pred['k']
            info = pred['info']
            
            # Получаем конфигурацию персонажа
            character = Config.CHARACTERS.get(model_name, {
                'name': model_name,
                'description': 'закономерности',
                'emoji': '❓'
            })
            
            # Экранируем специальные символы HTML
            safe_prediction = str(prediction).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Определяем эмодзи для цвета предсказания
            if "красное" in safe_prediction.lower():
                color_emoji = "🔴"
            elif "чёрное" in safe_prediction.lower():
                color_emoji = "⚫️"
            elif "зелёное" in safe_prediction.lower():
                color_emoji = "🟢"
            else:
                color_emoji = "❓"
            
            # Вычисляем вероятность с учетом типа модели
            probability = "?"
            if info and isinstance(info, dict):
                if model_name == 'Markov':
                    # Для Markov: применяем сглаживание Лапласа с разными весами для разных цветов
                    # Веса: красное=1, чёрное=1, зелёное=0.1 (зелёный выпадает реже)
                    alpha_weights = {
                        'красное': 1.0,
                        'чёрное': 1.0,
                        'зелёное': 0.1
                    }
                    
                    # Вычисляем сглаженные вероятности с учетом весов
                    total_smooth = sum(info.get(color, 0) + alpha_weights.get(color, 1.0) for color in alpha_weights)
                    if safe_prediction in alpha_weights:
                        prob_value = (info.get(safe_prediction, 0) + alpha_weights[safe_prediction]) / total_smooth
                        probability = f"{prob_value * 100:.1f}%"
                    else:
                        probability = "33.3%"
                    
                else:
                    # Для Logistic и RF: используем готовые вероятности
                    if safe_prediction in info:
                        prob_value = info[safe_prediction]
                        probability = f"{prob_value * 100:.1f}%"
            
            # Формируем строку с персонажем
            response += (f"{character['emoji']} <b>{character['name']}</b> смотрит на {character['description']} "
                        f"и говорит: {color_emoji} <b>{safe_prediction}</b> ({probability})\n\n")
        
        # Анализируем консенсус моделей
        color_counts = {}
        for pred in predictions:
            color = pred['prediction']
            if "красное" in color.lower() or "чёрное" in color.lower() or "зелёное" in color.lower():
                color_counts[color] = color_counts.get(color, 0) + 1
        
        # Находим цвет с максимальным количеством голосов
        consensus_prediction = None
        if color_counts:
            consensus_color = max(color_counts.items(), key=lambda x: x[1])
            if consensus_color[1] >= 2:  # Если минимум 2 модели согласны
                consensus_prediction = consensus_color[0]
                if "красное" in consensus_prediction.lower():
                    consensus_emoji = "🔴"
                elif "чёрное" in consensus_prediction.lower():
                    consensus_emoji = "⚫️"
                else:
                    consensus_emoji = "🟢"
                
                # response += f"💡 <b>Консенсус:</b> {consensus_emoji} {consensus_prediction} ({consensus_color[1]}/3 моделей)\n\n"
                response += f"💡 <b>Рекомендуем:</b> {consensus_prediction}\n\n"
                
        response += "────────────────────"
                
        # Добавляем статистику
        if total_predictions > 0:
            stats_text = f"📊 Сегодня правильно предсказаны: {correct_predictions}/{total_predictions} (Винрейт: {win_rate:.1f}%)"
            response += f"\n{stats_text}"
        
        response += "\n📚 Используйте <code>/rec</code> для получения рекомендаций по стратегии"
        # response += f"📊 Проанализировано результатов: {len(found_lines)}"
        
        # Отправляем сообщение с прогнозами
        sent_message = await update.message.reply_text(
            response,
            parse_mode="HTML",
            reply_to_message_id=update.message.message_id
        )
        
        # Получаем информацию о прошлом предсказании для этого чата
        saved_prediction_data = chm.get_prediction_data(chat_id)
        
        # Проверяем условия для сохранения нового предсказания
        should_save_prediction = (
            consensus_prediction and 
            replied_message.from_user and 
            replied_message.from_user.id == Config.ROULETTE_BOT_ID and
            getattr(replied_message, 'forward_from', None) is None
        )
        
        # Если есть сохраненное предсказание, проверяем, что текущее сообщение новее
        if should_save_prediction and saved_prediction_data:
            saved_message_id = saved_prediction_data.get('message_id', 0)
            if replied_message.message_id <= saved_message_id:
                logger.info(f"Сообщение {replied_message.message_id} не новее сохраненного {saved_message_id}, предсказание не сохранено")
                should_save_prediction = False
        
        # Сохраняем предсказание для чата, если все условия выполнены
        if should_save_prediction:
            chm.save_prediction(
                chat_id=chat_id, 
                message_id=replied_message.message_id, 
                prediction=consensus_prediction
            )
            logger.info(f"Сохранено предсказание для чата {chat_id} на сообщение {replied_message.message_id}: {consensus_prediction}")
        
    except Exception as e:
        logger.error(f"Ошибка в ludobot_command: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка при анализе истории рулетки: {str(e)}",
            reply_to_message_id=update.message.message_id
        )

# Обработчик для новых чатов
async def handle_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.bot.id in [user.id for user in update.message.new_chat_members]:
        chat_id = update.effective_chat.id
        if chat_id not in Config.ALLOWED_CHAT_IDS:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🚫 Бот доступен только для разрешенных чатов.\n"
                    f"Для получения бота свяжитесь с {Config.CREATOR}"
                )
            )
            await context.bot.leave_chat(chat_id)
        else:
            await help_command(update, context)

# Самопингование
async def self_ping(context):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{Config.RENDER_APP_URL}/ping") as resp:
                logger.info(f"Self-ping status: {resp.status}")
    except Exception as e:
        logger.error(f"Self-ping error: {str(e)}")

# Обработчик остановки
async def shutdown(application):
    logger.info("Starting graceful shutdown...")
    application.job_queue.stop()  # Останавливаем все задачи
    await application.stop()
    await application.shutdown()
    logger.info("Application stopped successfully")

def handle_signal(application, loop, signal_name):
    logger.info(f"Received {signal_name} signal")
    loop.create_task(shutdown(application))

async def post_init(application):
    # Регистрируем периодический самопинг через job_queue
    application.job_queue.run_repeating(
        self_ping,
        interval=180,  # 3 минут
        first=10  # Первый пинг через 10 сек после старта
    )
    
    # Настраиваем обработчик сигналов только для UNIX-систем
    if sys.platform != 'win32':
        loop = asyncio.get_running_loop()
        for signame in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(
                getattr(signal, signame),
                partial(handle_signal, application, loop, signame)
            )

# --- Обработчик для ludobot_command: точное сообщение "лудобот" (без ничего до/после, регистронезависимо) ---
async def ludobot_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Триггерится только если текст сообщения после .strip() равен "лудобот" (любые регистры).
    Переиспользует ludobot_command (которая уже проверяет reply_to_message и формат истории).
    """
    if not update.message:
        return

    text = (update.message.text or "").strip()
    if text.lower() != "лудобот":
        return

    await ludobot_command(update, context)

def main():
    # Запуск Flask в отдельном потоке
    threading.Thread(target=run_web_server, daemon=True).start()

    # Создание и настройка бота
    application = ApplicationBuilder()\
        .token(Config.BOT_TOKEN)\
        .post_init(post_init)\
        .build()
    
    # Фильтр для разрешенных чатов
    allowed_chat = filters.Chat(chat_id=Config.ALLOWED_CHAT_IDS)
    
    # Обработчик для новых чатов
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat)
    )

    # Регистрация обработчиков с применением фильтра
    application.add_handler(CommandHandler("start", help_command, filters=allowed_chat))
    application.add_handler(CommandHandler("help", help_command, filters=allowed_chat))
    application.add_handler(CommandHandler("ludobot", ludobot_command, filters=allowed_chat))
    application.add_handler(CommandHandler("rec", rec_command, filters=allowed_chat))
    
    # --- Точное совпадение сообщения "лудобот" (без чего-либо до/после) ---
    ludobot_exact_re = re.compile(r'^\s*лудобот\s*$', re.IGNORECASE)
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(ludobot_exact_re) & allowed_chat,
            ludobot_text_handler
        )
    )

    # Запуск бота
    try:
        application.run_polling()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application stopped by user")
    finally:
        if application.running:
            application.stop()

if __name__ == "__main__":
    main()