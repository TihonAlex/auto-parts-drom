from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import sales
import shipping
import sheets_sync
import asyncio
import logging
import sqlite3
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Создаем состояния для FSM
class ReserveStates(StatesGroup):
    waiting_for_client_name = State()

# Временное решение для быстрого запуска
BOT_TOKEN = "8813446707:AAGZkc4nGqwNzRjyeu0px7JvJxWYPsGlSqY"
bot = Bot(token=BOT_TOKEN)

logging.basicConfig(level=logging.INFO)
dp = Dispatcher(storage=MemoryStorage())

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📦 Проверить наличие")], [KeyboardButton(text="📋 Мои заказы")]],
        resize_keyboard=True
    )

@dp.message(Command("sales"))
async def cmd_sales_menu(message: types.Message):
    await message.answer(
        "📋 <b>Управление продажами</b>\n\nВыберите категорию:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=" Ожидают оплаты (Резерв)", callback_data="sales_pending")],
            [types.InlineKeyboardButton(text="💰 Оплачены, ждут отгрузки", callback_data="sales_paid")],
            [types.InlineKeyboardButton(text="🚛✨ Отгружены", callback_data="sales_shipped")],
            [types.InlineKeyboardButton(text=" Отмененные", callback_data="sales_cancelled")],
            [types.InlineKeyboardButton(text="📥 Скачать таблицу (Excel)", callback_data="sales_export")]
        ]),
        parse_mode="HTML"
    )

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Я бот для управления складом.\n\n📌 <b>Команды:</b>\n/stock [артикул]\n/find [название]\n/messages\n/reply ID текст\n/test_message\n/sync", reply_markup=get_main_keyboard(), parse_mode="HTML")

@dp.message(Command("stock"))
async def cmd_stock(message: types.Message):
    try:
        article = message.text.split(maxsplit=1)[1].strip().upper()
        conn = sqlite3.connect("parts_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT артикул, наименование, марка, модель, цена_дром, остаток, локация, status FROM parts WHERE артикул = ?", (article,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            status_emoji = {"available": "🟢 Свободна", "sold": "🔴 Продана", "paid": "🟡 Оплачена", "shipped": "📦 Отгружена"}.get(result[7], "❓ Неизвестно")
            
            text = (f"📦 <b>{result[0]}</b>\n"
                    f"📝 {result[1]}\n"
                    f"🚗 {result[3]} {result[2]}\n"
                    f"💰 {result[4] or '?'} ₽\n"
                    f"📍 {result[6] or 'Не указана'}\n"
                    f"📊 Статус: {status_emoji}")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продать", callback_data=f"sell_{article}"),
                 InlineKeyboardButton(text="💰 Оплачено", callback_data=f"paid_{article}")],
                [InlineKeyboardButton(text="📦 Отгрузить", callback_data=f"ship_{article}"),
                 InlineKeyboardButton(text="🔄 Вернуть в продажу", callback_data=f"available_{article}")],
                [InlineKeyboardButton(text="💰 Оформить продажу", callback_data=f"start_sale_{article}")]
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(f"❌ Артикул <code>{article}</code> не найден.", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("find"))
async def cmd_find(message: types.Message):
    try:
        query = message.text.split(maxsplit=1)[1].strip()
    except IndexError:
        await message.answer("❌ Укажи название. Пример: /find фара Camry")
        return

    conn = sqlite3.connect("parts_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT артикул, наименование, марка, модель, цена_дром, локация, status FROM parts")
    all_parts = cursor.fetchall()
    conn.close()

    query_lower = query.lower()
    words = [w for w in query_lower.split() if len(w) > 2]

    results = []
    for row in all_parts:
        name_lower = row[1].lower()
        if all(w in name_lower for w in words):
            results.append(row)

    if not results:
        await message.answer(f"❌ Ничего не найдено: {query}")
        return

    text = f"🔍 <b>Найдено {len(results)}:</b>\n\n"
    keyboard_buttons = []
    for row in results[:10]:
        status_emoji = {"available": "🟢", "sold": "🔴", "paid": "🟡", "shipped": "📦"}.get(row[6], "❓")
        button_text = f"{status_emoji} {row[0]} — {row[1][:40]}"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"detail_{row[0]}")])
        text += f"{status_emoji} <code>{row[0]}</code> — {row[1]}\n💰 {row[4] or '?'} ₽\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.message(Command("messages"))
async def cmd_messages(message: types.Message):
    conn = sqlite3.connect("parts_database.db")
    rows = conn.execute("SELECT id, client_name, client_message FROM messages WHERE status = 'new' ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    if not rows:
        await message.answer("📭 Новых сообщений нет")
        return
    text = "📨 <b>Новые:</b>\n\n" + "\n".join([f"🆔 <code>{r[0]}</code> {r[1]}\n💬 {r[2][:80]}" for r in rows]) + "\n\n💡 Ответь: <code>/reply ID текст</code>"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("reply"))
async def cmd_reply(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("❌ Формат: /reply ID текст\nПример: /reply 1 Здравствуйте!")
            return
        msg_id, reply_text = int(parts[1]), parts[2]
        conn = sqlite3.connect("parts_database.db")
        if conn.execute("SELECT 1 FROM messages WHERE id = ?", (msg_id,)).fetchone():
            conn.execute("UPDATE messages SET our_reply = ?, status = 'reply_ready' WHERE id = ?", (reply_text, msg_id))
            conn.commit()
            await message.answer(f"✅ Ответ сохранён (ID: {msg_id})")
        else:
            await message.answer(f"❌ Сообщение #{msg_id} не найдено")
        conn.close()
    except ValueError:
        await message.answer("❌ ID должен быть числом")
@dp.message(Command("export_to_sheet"))
async def cmd_export_to_sheet(message: types.Message):
    await message.answer("⏳ Выгружаю все данные из базы в Google Таблицу...")
    report = sheets_sync.export_db_to_sheet()
    await message.answer(report)

@dp.message(Command("sync"))
async def cmd_sync(message: types.Message):
    try:
        await message.answer("⏳ Синхронизация с Google Таблицей...")
        added = sheets_sync.sync_sheet_to_db()
        
        if added > 0:
            await message.answer(f"✅ Успешно! Добавлено новых позиций из таблицы: <b>{added}</b>")
        else:
            await message.answer("✅ Синхронизация завершена. Новых позиций не найдено.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при синхронизации:\n<code>{e}</code>")
        print(f"🔥 Ошибка в коде синхронизации: {e}")

@dp.message(Command("test_message"))
async def cmd_test_message(message: types.Message):
    conn = sqlite3.connect("parts_database.db")
    conn.execute("INSERT INTO messages (drom_thread_id, client_name, client_message, status) VALUES (?, ?, ?, 'new')", (f"test_{int(time.time())}", "Клиент", "Здравствуйте! Фара на Camry 06 (арт. 5310133180A1) в наличии?"))
    conn.commit()
    conn.close()
    await message.answer("✅ Тестовое сообщение создано. Проверь: /messages")

# Хендлер получения имени клиента
@dp.message(ReserveStates.waiting_for_client_name)
async def process_client_name(message: types.Message, state: FSMContext):
    print("🔥 FSM-ХЕНДЛЕР ВЫЗВАН! Текст:", message.text)
    
    data = await state.get_data()
    article = data.get('article')
    client_name = message.text.strip()
    
    if not client_name:
        await message.answer(" Имя не может быть пустым. Напиши хотя бы фамилию.")
        return
    
    sale_id = sales.create_sale(article, client_name)
    
    if sale_id > 0:
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        sync_report = sheets_sync.update_sheet_status(article, "Резерв", current_date)
        
        await message.answer(
            f"✅ <b>Резерв #{sale_id} создан!</b>\n"
            f" Деталь: {article}\n"
            f"👤 Клиент: {client_name}\n\n"
            f"📝 {sync_report}\n\n"
            f"Статус детали изменен на ' Резерв'.\n"
            f"Когда деньги придут — зайди в /sales и оформи доставку.",
            parse_mode="HTML"
        )
    elif sale_id == -2:
        await message.answer("⚠️ Эта деталь уже зарезервирована или продана!")
    else:
        await message.answer(f"❌ Деталь {article} не найдена в базе.")
    
    await state.clear()

@dp.message(lambda message: message.text and not message.text.startswith('/'))
async def handle_article_input(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return
    
    query = message.text.strip()
    if query in ['📦 Проверить наличие', '📋 Мои заказы']:
        return

    conn = sqlite3.connect("parts_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT артикул, наименование, марка, модель, цена_дром, остаток, локация, status FROM parts")
    all_parts = cursor.fetchall()
    conn.close()

    query_lower = query.lower()

    # 1. Точный поиск по артикулу
    exact_match = next((row for row in all_parts if row[0].lower() == query_lower), None)

    if exact_match:
        status_emoji = {"available": " Свободна", "sold": "🔴 Продана", "paid": " Оплачена", "shipped": " Отгружена"}.get(exact_match[7], "❓ Неизвестно")
        
        text = (f"📦 <code>{exact_match[0]}</code>\n"
                f" {exact_match[1]}\n"
                f"🚗 {exact_match[3]} {exact_match[2]}\n"
                f"💰 <b>{exact_match[4] or '?'} ₽</b>\n"
                f"📍 {exact_match[6] or 'Не указана'}\n"
                f"📊 Статус: {status_emoji}")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продать", callback_data=f"sell_{exact_match[0]}"),
             InlineKeyboardButton(text="💰 Оплачено", callback_data=f"paid_{exact_match[0]}")],
            [InlineKeyboardButton(text="📦 Отгрузить", callback_data=f"ship_{exact_match[0]}"),
             InlineKeyboardButton(text="🔄 Вернуть в продажу", callback_data=f"available_{exact_match[0]}")],
            [InlineKeyboardButton(text="💰 Оформить продажу", callback_data=f"start_sale_{exact_match[0]}")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return

    # 2. Частичный поиск по артикулу
    partial_matches = [row for row in all_parts if row[0].lower().startswith(query_lower)]

    if partial_matches:
        if len(partial_matches) == 1:
            row = partial_matches[0]
            status_emoji = {"available": "🟢 Свободна", "sold": "🔴 Продана", "paid": "🟡 Оплачена", "shipped": "📦 Отгружена"}.get(row[7], "❓ Неизвестно")
            
            text = (f"📦 <code>{row[0]}</code>\n"
                    f" {row[1]}\n"
                    f"🚗 {row[3]} {row[2]}\n"
                    f"💰 <b>{row[4] or '?'} ₽</b>\n"
                    f"📍 {row[6] or 'Не указана'}\n"
                    f"📊 Статус: {status_emoji}\n\n"
                    f" Найдено по частичному совпадению артикула")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продать", callback_data=f"sell_{row[0]}"),
                 InlineKeyboardButton(text="💰 Оплачено", callback_data=f"paid_{row[0]}")],
                [InlineKeyboardButton(text=" Отгрузить", callback_data=f"ship_{row[0]}"),
                 InlineKeyboardButton(text="🔄 Вернуть в продажу", callback_data=f"available_{row[0]}")],
                [InlineKeyboardButton(text="💰 Оформить продажу", callback_data=f"start_sale_{row[0]}")]
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            text = f"🔍 <b>Найдено {len(partial_matches)} вариантов по артикулу:</b>\n\n"
            keyboard_buttons = []
            
            for row in partial_matches[:10]:
                status_emoji = {"available": "🟢", "sold": "🔴", "paid": "🟡", "shipped": "📦"}.get(row[7], "❓")
                button_text = f"{status_emoji} {row[0]} — {row[1][:30]}"
                keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"detail_{row[0]}")])
                text += f"{status_emoji} <code>{row[0]}</code> — {row[1][:40]} ({row[4] or '?'} ₽)\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return

    # 3. Поиск по словам в названии
    if len(query) > 3:
        words = [w for w in query_lower.split() if len(w) > 2]
        results = []
        for row in all_parts:
            name_lower = row[1].lower()
            if all(w in name_lower for w in words):
                results.append(row)

        if len(results) == 1:
            row = results[0]
            status_emoji = {"available": "🟢 Свободна", "sold": "🔴 Продана", "paid": "🟡 Оплачена", "shipped": "📦 Отгружена"}.get(row[7], "❓ Неизвестно")
            
            text = (f"📦 <code>{row[0]}</code>\n"
                    f"📝 {row[1]}\n"
                    f"🚗 {row[3]} {row[2]}\n"
                    f"💰 <b>{row[4] or '?'} ₽</b>\n"
                    f" {row[6] or 'Не указана'}\n"
                    f"📊 Статус: {status_emoji}")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Продать", callback_data=f"sell_{row[0]}"),
                 InlineKeyboardButton(text="💰 Оплачено", callback_data=f"paid_{row[0]}")],
                [InlineKeyboardButton(text="📦 Отгрузить", callback_data=f"ship_{row[0]}"),
                 InlineKeyboardButton(text="🔄 Вернуть в продажу", callback_data=f"available_{row[0]}")]
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        elif len(results) > 1:
            text = f" <b>Найдено {len(results)} вариантов по названию:</b>\n\n"
            
            keyboard_buttons = []
            for row in results[:10]:
                status_emoji = {"available": "🟢", "sold": "🔴", "paid": "🟡", "shipped": "📦"}.get(row[7], "❓")
                button_text = f"{status_emoji} {row[0]} — {row[1][:40]}"
                keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"detail_{row[0]}")])
                text += f"{status_emoji} <code>{row[0]}</code> — {row[1][:50]}... ({row[4] or '?'} ₽)\n\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(f"❌ Не найдено: <code>{query}</code>", parse_mode="HTML")
    else:
        await message.answer(f"❌ Не найдено: <code>{query}</code>", parse_mode="HTML")

@dp.callback_query(lambda c: c.data and c.data.startswith(('sell_', 'paid_', 'ship_', 'available_')))
async def handle_status_change(callback_query: types.CallbackQuery):
    try:
        # Сразу даем понять, что бот работает
        await callback_query.answer("⏳ Обрабатываю...")
        
        action, article = callback_query.data.split('_', 1)
        article = article.strip() # Очищаем артикул от скрытых пробелов или переносов
        
        status_map = {
            'sell': 'sold',
            'paid': 'paid',
            'ship': 'shipped',
            'available': 'available'
        }
        
        new_status = status_map.get(action)
        if not new_status:
            await callback_query.message.answer("❌ Неизвестное действие")
            return
        
        # 1. Обновляем SQLite
        conn = sqlite3.connect("parts_database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE parts SET status = ? WHERE артикул = ?", (new_status, article))
        conn.commit()
        
        # Проверяем, действительно ли база обновилась
        cursor.execute("SELECT status FROM parts WHERE артикул = ?", (article,))
        check_result = cursor.fetchone()
        conn.close()
        
        if not check_result or check_result[0] != new_status:
            await callback_query.message.answer(f"❌ Ошибка БД: не удалось обновить статус для {article}")
            return

        # 2. Обновляем Google Sheets
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        status_text = {"sold": "Продана", "paid": "Оплачена", "shipped": "Отгружена", "available": "Свободна"}.get(new_status, new_status)
        
        # Вызываем функцию и получаем текстовый отчет
        sync_report = sheets_sync.update_sheet_status(
            article, 
            status_text, 
            current_date if new_status in ['sold', 'paid', 'shipped'] else ""
        )
        
        # 3. Отправляем подробный отчет пользователю
        status_emoji = {"available": "🟢 Свободна", "sold": "🔴 Продана", "paid": "🟡 Оплачена", "shipped": "📦 Отгружена"}.get(new_status, "❓")
        
        await callback_query.message.answer(
            f"✅ Статус изменен: {status_emoji}\n"
            f"📦 Артикул: <code>{article}</code>\n"
            f"📝 Отчет таблицы: {sync_report}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        # Если произошла любая ошибка, мы обязательно её увидим в Telegram
        error_msg = f"🔥 КРИТИЧЕСКАЯ ОШИБКА:\n<code>{str(e)}</code>"
        await callback_query.message.answer(error_msg, parse_mode="HTML")
        print(f"ERROR in handle_status_change: {e}")

@dp.callback_query(lambda c: c.data and c.data.startswith('detail_'))
async def handle_detail_click(callback_query: types.CallbackQuery):
    article = callback_query.data.split('_', 1)[1]
    
    conn = sqlite3.connect("parts_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT артикул, наименование, марка, модель, цена_дром, остаток, локация, status FROM parts WHERE артикул = ?", (article,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        status_emoji = {"available": "🟢 Свободна", "sold": "🔴 Продана", "paid": " Оплачена", "shipped": " Отгружена"}.get(row[7], "❓ Неизвестно")
        
        text = (f"📦 <code>{row[0]}</code>\n"
                f"📝 {row[1]}\n"
                f"🚗 {row[3]} {row[2]}\n"
                f"💰 <b>{row[4] or '?'} ₽</b>\n"
                f"📍 {row[6] or 'Не указана'}\n"
                f"📊 Статус: {status_emoji}")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Продать", callback_data=f"sell_{row[0]}"),
             InlineKeyboardButton(text="💰 Оплачено", callback_data=f"paid_{row[0]}")],
            [InlineKeyboardButton(text=" Отгрузить", callback_data=f"ship_{row[0]}"),
             InlineKeyboardButton(text=" Вернуть в продажу", callback_data=f"available_{row[0]}")]
        ])
        
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback_query.answer()
    else:
        await callback_query.answer(" Деталь не найдена")

@dp.message(Command("ship"))
async def cmd_ship(message: types.Message):
    try:
        client_text = message.text.split(maxsplit=1)[1].strip()
    except IndexError:
        await message.answer("⚠️ Используй команду так:\n`/ship Иванов Иван, г. Москва, ул. Ленина 1, +79001234567`", parse_mode="Markdown")
        return

    parsed = shipping.parse_client_data(client_text)
    
    if parsed["phone"] != "Не указано":
        existing_client = shipping.get_client_by_phone("parts_database.db", parsed["phone"])
        if existing_client:
            await message.answer(
                f"👤 <b>Клиент уже в базе!</b>\n"
                f"Имя: {existing_client['name']}\n"
                f"Город: {existing_client['city']}\n"
                f"Адрес: {existing_client['address']}\n\n"
                f"Использовать старые данные или новые?\n"
                f"Новые данные: {parsed['name']}, {parsed['city']}, {parsed['address']}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Использовать старые", callback_data="use_old_client")],
                    [InlineKeyboardButton(text="🔄 Использовать новые", callback_data="use_new_client")]
                ]),
                parse_mode="HTML"
            )
            shipping.save_client("parts_database.db", parsed["phone"], parsed["name"], parsed["city"], parsed["address"])
            return

    shipping.save_client("parts_database.db", parsed["phone"], parsed["name"], parsed["city"], parsed["address"])
    
    await message.answer(
        f" <b>Данные для отправки распознаны:</b>\n"
        f" {parsed['name']}\n"
        f"📞 {parsed['phone']}\n"
        f"🏙 {parsed['city']}\n"
        f"🏠 {parsed['address']}\n\n"
        f"Выберите транспортную компанию для создания накладной:",
        reply_markup=shipping.get_shipping_keyboard("CURRENT_ARTICLE"),
        parse_mode="HTML"
    )

# ОБРАБОТЧИК КНОПОК МЕНЮ ПРОДАЖ
@dp.callback_query(F.data.startswith("sales_"))
async def process_sales_menu(callback: types.CallbackQuery):
    action = callback.data.split("_")[1]
    
    if action == "export":
        filename = sales.generate_excel_report()
        with open(filename, "rb") as doc:
            await callback.message.answer_document(doc, caption="📊 Отчет по всем продажам")
        await callback.answer()
        return

    status_map = {
        "pending": "pending",
        "paid": "paid",
        "shipped": "shipped",
        "cancelled": "cancelled",
        "menu": "menu"
    }
    status = status_map.get(action)
    if not status:
        await callback.answer(" Неизвестное действие")
        return
    
    # Хендлер для кнопки "Назад"
    if action == "menu":
        await cmd_sales_menu(callback.message)
        await callback.answer()
        return

    sales_list = sales.get_sales_by_status(status)
    if not sales_list:
        await callback.message.answer("📭 В этой категории пока пусто.")
        await callback.answer()
        return

    text = f"📋 <b>Список ({status}):</b>\n\n"
    keyboard = []
    for s in sales_list:
        text += f"#{s[0]} | {s[2]} | {s[3]}\n"
        keyboard.append([types.InlineKeyboardButton(text=f"#{s[0]} {s[2]}", callback_data=f"view_sale_{s[0]}")])
    
    keyboard.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="sales_menu")])
    
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    await callback.answer()

# ПРОСМОТР КОНКРЕТНОЙ ПРОДАЖИ
@dp.callback_query(F.data.startswith("view_sale_"))
async def view_sale(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    data = sales.get_sale_details(sale_id)
    if not data:
        await callback.message.answer("❌ Продажа не найдена.")
        return

    status_emoji = {"pending": "", "paid": "💰", "shipped": "🚚", "cancelled": "❌"}
    emoji = status_emoji.get(data['status'], "❓")

    text = (
        f"{emoji} <b>Продажа #{data['id']}</b>\n"
        f" <b>Деталь:</b> {data['name']} ({data['article']})\n"
        f"💰 <b>Цена:</b> {data['price']} ₽\n"
        f"👤 <b>Клиент:</b> {data['client_name']}\n"
        f"📞 <b>Тел:</b> {data['client_phone'] or 'Не указан'}\n"
        f"📅 <b>Дата:</b> {data['date']}\n"
    )
    if data['tracking']:
        text += f" <b>Трек:</b> {data['tracking']}\n"

    keyboard = []
    if data['status'] == 'pending':
        keyboard = [
            [types.InlineKeyboardButton(text="✅ Оплата получена", callback_data=f"sale_pay_{sale_id}")],
            [types.InlineKeyboardButton(text="🚚 Оформить доставку", callback_data=f"sale_ship_{sale_id}")],
            [types.InlineKeyboardButton(text="❌ Отмена продажи", callback_data=f"sale_cancel_{sale_id}")]
        ]
    elif data['status'] == 'paid':
        keyboard = [
            [types.InlineKeyboardButton(text="🚚 Оформить доставку", callback_data=f"sale_ship_{sale_id}")]
        ]

    if keyboard:
        keyboard.append([types.InlineKeyboardButton(text="🔙 Назад к списку", callback_data="sales_menu")])
        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="HTML")
    else:
        await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# ДЕЙСТВИЯ С ПРОДАЖЕЙ (ОПЛАТА / ОТМЕНА)
@dp.callback_query(F.data.startswith("sale_pay_"))
async def mark_sale_paid(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    sales.update_sale_status(sale_id, 'paid')
    await callback.message.answer("✅ Оплата подтверждена! Статус детали изменен на 'Продана'.")
    await view_sale(callback)

@dp.callback_query(F.data.startswith("sale_cancel_"))
async def cancel_sale(callback: types.CallbackQuery):
    sale_id = int(callback.data.split("_")[2])
    sales.update_sale_status(sale_id, 'cancelled')
    await callback.message.answer("❌ Продажа отменена. Деталь возвращена в свободную продажу.")
    await view_sale(callback)

# Хендлер нажатия на кнопку "Оформить продажу"
@dp.callback_query(F.data.startswith("start_sale_"))
async def start_sale_callback(callback: types.CallbackQuery, state: FSMContext):
    article = callback.data.split("_")[2]
    
    print("🔥 УСТАНАВЛИВАЕМ СОСТОЯНИЕ для артикула:", article)
    
    await state.update_data(article=article)
    await state.set_state(ReserveStates.waiting_for_client_name)
    
    current_state = await state.get_state()
    print(" ТЕКУЩЕЕ СОСТОЯНИЕ:", current_state)
    
    await callback.message.answer(
        f"💰 <b>Оформляем резерв: {article}</b>\n\n"
        f"На кого делаем резерв? (коротко, например: Иванов Дром):",
        parse_mode="HTML"
    )
    await callback.answer()

async def main():
    print("🚀 БОТ ЗАПУСКАЕТСЯ... (Ctrl+C для остановки)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен.")