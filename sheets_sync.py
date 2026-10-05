import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
from datetime import datetime

SHEET_ID = '1YybdZWWlKPUZMqrlMVsh0CAxKs-5WhVn2HYE7que1SM'
CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

def get_client():
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
    """Обновляет СТАТУС ПРОДАЖИ (кол. 17) и ДАТУ ПРОДАЖИ (кол. 18)"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        clean_article = str(article).strip()
        cell = sheet.find(clean_article)
        
        if cell:
            row = cell.row
            # Колонка 17 = СТАТУС ПРОДАЖИ, Колонка 18 = ДАТА ПРОДАЖИ
            sheet.update_cell(row, 17, status)
            if date_str:
                sheet.update_cell(row, 18, date_str)
            return f"✅ Строка {row} успешно обновлена (Статус и Дата)."
        else:
            return f"⚠️ Артикул '{clean_article}' НЕ НАЙДЕН в таблице."
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def export_db_to_sheet():
    """Выгружает данные из SQLite в таблицу, соблюдая новую структуру из 18 колонок"""
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        
        conn = sqlite3.connect("parts_database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT артикул, наименование, марка, модель, цена_дром, остаток, локация, status FROM parts")
        parts = cursor.fetchall()
        conn.close()
        
        if not parts:
            return "❌ База данных пустая!"
        
        rows_to_add = []
        for part in parts:
            article, name, brand, model, price_drom, stock, location, status = part
            
            status_text = {
                'available': 'Свободна',
                'sold': 'Продана',
                'paid': 'Оплачена',
                'shipped': 'Отгружена'
            }.get(status, 'Свободна')
            
            # Маппинг строго под 18 колонок:
            rows_to_add.append([
                article,          # 1. АРТИКУЛ
                name,             # 2. НАИМЕНОВАНИЕ
                '',               # 3. КАТЕГОРИЯ (пока пусто)
                '',               # 4. ПОДКАТЕГОРИЯ (пока пусто)
                brand,            # 5. МАРКА
                model,            # 6. МОДЕЛЬ
                '',               # 7. № КУЗОВА (пока пусто)
                '',               # 8. СОСТОЯНИЕ (пока пусто)
                '',               # 9. ПРОИЗВОДИТЕЛЬ (пока пусто)
                str(stock),       # 10. ОСТАТОК
                '',               # 11. ПРИМЕЧАНИЕ (пока пусто)
                location,         # 12. ЛОКАЦИЯ
                '',               # 13. ЦЕНА ЗАКУП (пока пусто)
                '',               # 14. ЦЕНА ОПТ (пока пусто)
                str(price_drom),  # 15. ЦЕНА ДРОМ
                '',               # 16. СТАТУС ДРОМ (пока пусто)
                status_text,      # 17. СТАТУС ПРОДАЖИ
                ''                # 18. ДАТА ПРОДАЖИ (пока пусто)
            ])
        
        # Очищаем старые данные (оставляем только заголовки в строке 1)
        if sheet.row_count > 1:
            sheet.delete_rows(2, sheet.row_count)
        
        # Добавляем актуальные данные
        if rows_to_add:
            sheet.append_rows(rows_to_add)
        
        return f"✅ Успешно выгружено {len(rows_to_add)} позиций в новую структуру!"
        
    except Exception as e:
        return f"❌ Ошибка при выгрузке: {e}"

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
                price = str(row.get('ЦЕНА ДРОМ', ''))
                location = str(row.get('ЛОКАЦИЯ', ''))
                
                # Базовая синхронизация основных полей
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