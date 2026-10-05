import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
from datetime import datetime

# ID твоей рабочей таблицы (из успешного теста)
SHEET_ID = '1YybdZWWlKPUZMqrlMVsh0CAxKs-5WhVn2HYE7que1SM'

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
        print(f"❌ Ошибка авторизации: {e}")
        raise e

def update_sheet_status(article, status, date_str=""):
    """Обновляет СТАТУС (кол. 8) и ДАТУ ПРОДАЖИ (кол. 9) в существующей таблице"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        clean_article = str(article).strip()
        cell = sheet.find(clean_article)
        
        if cell:
            row = cell.row
            # Колонка 8 = СТАТУС, Колонка 9 = ДАТА ПРОДАЖИ
            sheet.update_cell(row, 8, status)
            if date_str:
                sheet.update_cell(row, 9, date_str)
            return f"✅ Строка {row} успешно обновлена."
        else:
            return f"⚠️ Артикул '{clean_article}' НЕ НАЙДЕН в таблице."
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def export_db_to_sheet():
    """Выгружает все данные из SQLite в твою существующую таблицу, сохраняя колонки"""
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
            article, name, brand, model, price_sale, location, status = part
            
            status_text = {
                'available': 'Свободна',
                'sold': 'Продана',
                'paid': 'Оплачена',
                'shipped': 'Отгружена'
            }.get(status, 'Свободна')
            
            # Маппинг строго под твои 11 колонок:
            # 1: АРТИКУЛ, 2: НАИМЕНОВАНИЕ, 3: МАРКА, 4: МОДЕЛЬ, 
            # 5: ЦЕНА СКЛАД (пока пусто), 6: ЦЕНА К ПРОДАЖЕ, 7: ЛОКАЦИЯ, 
            # 8: СТАТУС, 9: ДАТА ПРОДАЖИ (пусто), 10: РАЗМЕЩЕНО НА ДРОМ (пусто), 11: КОММЕНТАРИИ (пусто)
            rows_to_add.append([
                article,
                name,
                brand,
                model,
                '',                # ЦЕНА СКЛАД
                str(price_sale),   # ЦЕНА К ПРОДАЖЕ
                location,
                status_text,       # СТАТУС
                '',                # ДАТА ПРОДАЖИ
                '',                # РАЗМЕЩЕНО НА ДРОМ
                ''                 # КОММЕНТАРИИ
            ])
        
        # Очищаем старые данные (оставляем только заголовки в строке 1)
        if sheet.row_count > 1:
            sheet.delete_rows(2, sheet.row_count)
        
        # Добавляем актуальные данные
        if rows_to_add:
            sheet.append_rows(rows_to_add)
        
        return f"✅ Успешно выгружено {len(rows_to_add)} позиций в таблицу!"
        
    except Exception as e:
        return f"❌ Ошибка при выгрузке: {e}"

def sync_sheet_to_db():
    """Забирает новые позиции из Google Таблицы в SQLite (если офис добавил вручную)"""
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
        print(f"❌ Ошибка синхронизации: {e}")
        return 0