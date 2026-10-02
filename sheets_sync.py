import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
from datetime import datetime

# ВСТАВЬ СЮДА ID СВОЕЙ РАБОЧЕЙ GOOGLE ТАБЛИЦЫ (из адресной строки)
SHEET_ID = '1Z1Td434s7Y4LnGwACfccrDhPcIqTS7sWSvO_UQJMDBA' 

# Получаем JSON либо из переменной окружения (Railway), либо из файла (локально)
CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

def get_client():
    """Авторизация в Google Sheets"""
    try:
        if CREDS_JSON:
            # Для Railway: читаем из переменной окружения
            creds_dict = json.loads(CREDS_JSON)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            # Для локального запуска: читаем из файла credentials.json
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
        
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Ошибка авторизации Google Sheets: {e}")
        raise e

def update_sheet_status(article, status, date_str=""):
    """Обновляет статус и дату продажи в Google Таблице и возвращает отчет"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        # Очищаем артикул от случайных пробелов для надежного поиска
        clean_article = str(article).strip()
        
        # Ищем ячейку с нужным артикулом
        cell = sheet.find(clean_article)
        
        if cell:
            row = cell.row
            # Колонка H (8) = Статус
            sheet.update_cell(row, 8, status)
            
            # Колонка I (9) = Дата продажи
            if date_str:
                sheet.update_cell(row, 9, date_str)
                
            return f"✅ Строка {row} в таблице успешно обновлена."
        else:
            return f"⚠️ Артикул '{clean_article}' НЕ НАЙДЕН в таблице. Проверьте ID таблицы и наличие артикула в колонке А."
            
    except Exception as e:
        return f"❌ Ошибка при обновлении таблицы: {str(e)}"

def sync_sheet_to_db():
    """Забирает новые позиции из Google Таблицы в локальную базу SQLite"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        
        conn = sqlite3.connect("parts_database.db")
        cursor = conn.cursor()
        added_count = 0
        
        for row in data:
            article = str(row.get('Артикул', '')).strip()
            # Пропускаем пустые строки или заголовки
            if not article or article.lower() in ['nan', 'none', '', 'артикул']:
                continue
            
            # Проверяем, есть ли уже такая деталь в базе
            cursor.execute("SELECT 1 FROM parts WHERE артикул = ?", (article,))
            if not cursor.fetchone():
                # Если нет, добавляем её
                name = str(row.get('Наименование', ''))
                brand = str(row.get('Марка', ''))
                model = str(row.get('Модель', ''))
                price = str(row.get('Цена к продаже', ''))
                location = str(row.get('Локация', ''))
                status = str(row.get('Статус', 'available')).lower()
                
                # Приводим статус к формату базы (available, sold, paid, shipped)
                if 'продан' in status: status = 'sold'
                elif 'оплач' in status: status = 'paid'
                elif 'отгруж' in status: status = 'shipped'
                else: status = 'available'

                cursor.execute("""
                    INSERT INTO parts (артикул, наименование, марка, модель, цена_дром, остаток, локация, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (article, name, brand, model, price, '1', location, status))
                added_count += 1
        
        conn.commit()
        conn.close()
        return added_count
    except Exception as e:
        print(f"❌ Ошибка синхронизации из таблицы: {e}")
        return 0