import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
from datetime import datetime

# ВСТАВЬ СЮДА ID СВОЕЙ РАБОЧЕЙ GOOGLE ТАБЛИЦЫ
SHEET_ID = '1YybdZWWIKPUZMqrIMVsh0CAxKs-5WhVn2HYE7que1SM'

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
            creds_dict = json.loads(CREDS_JSON)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
        
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Ошибка авторизации Google Sheets: {e}")
        raise e

def update_sheet_status(article, status, date_str=""):
    """Обновляет статус и дату продажи в Google Таблице"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        clean_article = str(article).strip()
        cell = sheet.find(clean_article)
        
        if cell:
            row = cell.row
            sheet.update_cell(row, 8, status)
            if date_str:
                sheet.update_cell(row, 9, date_str)
            return f"✅ Строка {row} обновлена."
        else:
            return f"️ Артикул '{clean_article}' НЕ НАЙДЕН в таблице."
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def sync_sheet_to_db():
    """Забирает новые позиции из Google Таблицы в SQLite"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        
        conn = sqlite3.connect("parts_database.db")
        cursor = conn.cursor()
        added_count = 0
        
        for row in data:
            article = str(row.get('АРТИКУЛ', '')).strip()
            if not article or article.lower() in ['nan', 'none', '', 'артикул']:
                continue
            
            cursor.execute("SELECT 1 FROM parts WHERE артикул = ?", (article,))
            if not cursor.fetchone():
                name = str(row.get('НАИМЕНОВАНИЕ', ''))
                brand = str(row.get('МАРКА', ''))
                model = str(row.get('МОДЕЛЬ', ''))
                price = str(row.get('ЦЕНА К ПРОДАЖЕ', ''))
                location = str(row.get('ЛОКАЦИЯ', ''))
                
                cursor.execute("""
                    INSERT INTO parts (артикул, наименование, марка, модель, цена_дром, остаток, локация, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (article, name, brand, model, price, '1', location, 'available'))
                added_count += 1
        
        conn.commit()
        conn.close()
        return added_count
    except Exception as e:
        print(f" Ошибка синхронизации: {e}")
        return 0

def export_db_to_sheet():
    """Выгружает все данные из SQLite в Google Таблицу"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        conn = sqlite3.connect("parts_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT артикул, наименование, марка, модель, цена_дром, локация, status FROM parts")
        parts = cursor.fetchall()
        conn.close()
        
        if not parts:
            return "❌ База данных пустая!"
        
        rows_to_add = []
        for part in parts:
            article, name, brand, model, price, location, status = part
            
            status_text = {
                'available': 'Свободна',
                'sold': 'Продана',
                'paid': 'Оплачена',
                'shipped': 'Отгружена'
            }.get(status, status)
            
            rows_to_add.append([
                article,
                name,
                brand,
                model,
                price,
                '',
                location,
                status_text,
                '',
                ''
            ])
        
        # Удаляем старые данные (кроме заголовков)
        if sheet.row_count > 1:
            sheet.delete_rows(2, sheet.row_count)
        
        # Добавляем новые данные
        if rows_to_add:
            sheet.append_rows(rows_to_add)
        
        return f"✅ Выгружено {len(rows_to_add)} позиций!"
        
    except Exception as e:
        return f"❌ Ошибка: {e}"