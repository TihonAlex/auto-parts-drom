import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
from datetime import datetime

# ID твоей рабочей таблицы
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
    """Обновляет СТАТУС ПРОДАЖИ (кол. 17), ДАТУ ПРОДАЖИ (кол. 18) 
       и меняет цвет текста в колонках A, B, P при статусе 'Продана'"""
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SHEET_ID)  # ← ВАЖНО: получаем объект таблицы
        sheet = spreadsheet.sheet1
        
        clean_article = str(article).strip()
        cell = sheet.find(clean_article)
        
        if not cell:
            return f"️ Артикул '{clean_article}' НЕ НАЙДЕН в таблице."
        
        row = cell.row
        
        # 1. Обновляем текст в колонках 17 (СТАТУС ПРОДАЖИ) и 18 (ДАТА ПРОДАЖИ)
        sheet.update_cell(row, 17, status)
        if date_str:
            sheet.update_cell(row, 18, date_str)
        
        # 2. Определяем цвет текста
        if status == "Продана":
            text_color = {'red': 0.0, 'green': 0.7, 'blue': 0.0}  # 🟢 Зелёный
        else:
            text_color = {'red': 0.0, 'green': 0.0, 'blue': 0.0}  # ⚫ Чёрный
        
        # 3. Красим текст в колонках A (1), B (2), P (16)
        # Индексы колонок считаются с 0: A=0, B=1, P=15
        requests = []
        for col_index in [0, 1, 15]:  # A, B, P
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet.id,
                        "startRowIndex": row - 1,
                        "endRowIndex": row,
                        "startColumnIndex": col_index,
                        "endColumnIndex": col_index + 1
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "foregroundColor": text_color,
                                "bold": (status == "Продана")  # Жирный только при продаже
                            }
                        }
                    },
                    "fields": "userEnteredFormat.textFormat(foregroundColor,bold)"
                }
            })
        
        # 4. ОТПРАВЛЯЕМ ЗАПРОС ЧЕРЕЗ ОБЪЕКТ ТАБЛИЦЫ (spreadsheet), а НЕ client!
        spreadsheet.batch_update({"requests": requests})
        
        return f"✅ Строка {row} обновлена. Статус: '{status}', цвет текста изменён."
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def export_db_to_sheet():
    """Выгружает данные из SQLite в таблицу, соблюдая структуру из 18 колонок"""
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SHEET_ID)
        sheet = spreadsheet.sheet1
        
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
            
            rows_to_add.append([
                article,          # 1. АРТИКУЛ
                name,             # 2. НАИМЕНОВАНИЕ
                '',               # 3. КАТЕГОРИЯ
                '',               # 4. ПОДКАТЕГОРИЯ
                brand,            # 5. МАРКА
                model,            # 6. МОДЕЛЬ
                '',               # 7. № КУЗОВА
                '',               # 8. СОСТОЯНИЕ
                '',               # 9. ПРОИЗВОДИТЕЛЬ
                str(stock),       # 10. ОСТАТОК
                '',               # 11. ПРИМЕЧАНИЕ
                location,         # 12. ЛОКАЦИЯ
                '',               # 13. ЦЕНА ЗАКУП
                '',               # 14. ЦЕНА ОПТ
                str(price_drom),  # 15. ЦЕНА ДРОМ
                '',               # 16. СТАТУС ДРОМ
                status_text,      # 17. СТАТУС ПРОДАЖИ
                ''                # 18. ДАТА ПРОДАЖИ
            ])
        
        if sheet.row_count > 1:
            sheet.delete_rows(2, sheet.row_count)
        
        if rows_to_add:
            sheet.append_rows(rows_to_add)
        
        return f"✅ Успешно выгружено {len(rows_to_add)} позиций!"
        
    except Exception as e:
        return f"❌ Ошибка при выгрузке: {e}"

def sync_sheet_to_db():
    """Забирает новые позиции из Google Таблицы в SQLite"""
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SHEET_ID)
        sheet = spreadsheet.sheet1
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