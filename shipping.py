import re
import sqlite3
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def parse_client_data(text: str) -> dict:
    """Умно парсит данные клиента, разделяя адрес на компоненты."""
    data = {
        "name": "Не указано",
        "phone": "Не указано",
        "index": "Не указано",
        "city": "Не указано",
        "street": "Не указано",
        "house": "Не указано",
        "building": "",  # Корпус/Строение
        "flat": "",      # Квартира/Офис
        "raw_text": text
    }
    
    # 1. Ищем телефон
    phone_match = re.search(r'(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text)
    if phone_match:
        phone = phone_match.group(0).replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if phone.startswith('8') and len(phone) == 11:
            phone = '+7' + phone[1:]
        data["phone"] = phone

    # 2. Ищем индекс (6 цифр подряд)
    index_match = re.search(r'\b(\d{6})\b', text)
    if index_match:
        data["index"] = index_match.group(1)

    # 3. Разбиваем текст на строки для анализа
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines:
        line_lower = line.lower()
        
        # Ищем строку с городом
        if 'г.' in line_lower or 'город' in line_lower:
            city_match = re.search(r'(?:г\.|город)\s*([А-Яа-яЁё\-]+)', line, re.IGNORECASE)
            if city_match:
                data["city"] = city_match.group(1).capitalize()
                
        # Ищем улицу
        if re.search(r'(ул\.|улица|пр\.|проспект|пер\.|переулок|пл\.|площадь)', line_lower):
            street_match = re.search(r'(ул\.|улица|пр\.|проспект|пер\.|переулок|пл\.|площадь)\.?\s*([А-Яа-яЁё\-]+(?:\s+[А-Яа-яЁё\-]+)?)', line, re.IGNORECASE)
            if street_match:
                data["street"] = street_match.group(2).capitalize()
                
        # Ищем дом (д. 5, дом 5, просто 5 после улицы)
        house_match = re.search(r'(?:д\.|дом|д)\s*\.?(\d+[А-Яа-я]?)', line, re.IGNORECASE)
        if house_match:
            data["house"] = house_match.group(1)
            
        # Ищем корпус/строение (к. 1, корп. 1, стр. 1)
        build_match = re.search(r'(?:к\.|корп\.|корпус|стр\.|строение)\s*\.?(\d+[А-Яа-я]?)', line, re.IGNORECASE)
        if build_match:
            data["building"] = build_match.group(1)
            
        # Ищем квартиру/офис (кв. 10, офис 15)
        flat_match = re.search(r'(?:кв\.|квартира|оф\.|офис)\s*\.?(\d+[А-Яа-я]?)', line, re.IGNORECASE)
        if flat_match:
            data["flat"] = flat_match.group(1)

        # Имя (первая подходящая строка без ключевых слов адреса)
        if data["name"] == "Не указано":
            if len(line) > 3 and not any(k in line_lower for k in ['телефон', 'тел.', 'phone', '+7', '8 ', 'г.', 'ул.', 'д.', 'кв.', 'индекс', 'index']):
                # Простая проверка, что это не адресная строка
                if not re.search(r'\d', line): # Если в строке нет цифр, скорее всего это имя
                    data["name"] = line

    return data

def save_client(db_path: str, phone: str, name: str, city: str, address: str):
    """Сохраняет или обновляет данные клиента в БД."""
    if phone == "Не указано":
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO clients (phone, full_name, city, address, last_purchase)
        VALUES (?, ?, ?, ?, CURRENT_DATE)
    """, (phone, name, city, address))
    conn.commit()
    conn.close()

def get_client_by_phone(db_path: str, phone: str) -> dict:
    """Возвращает данные клиента по телефону, если он уже есть в базе."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, city, address FROM clients WHERE phone = ?", (phone,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {"name": result[0], "city": result[1], "address": result[2]}
    return None

def get_shipping_keyboard(article: str) -> InlineKeyboardMarkup:
    """Формирует клавиатуру для выбора ТК и действий."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 СДЭК (Склад-Склад)", callback_data=f"ship_cdek_{article}"),
            InlineKeyboardButton(text="🚛 ПЭК", callback_data=f"ship_pek_{article}")
        ],
        [
            InlineKeyboardButton(text="✏️ Поправить данные вручную", callback_data=f"edit_ship_{article}")
        ]
    ])