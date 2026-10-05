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
    """
    Обновляет СТАТУС (кол. P=16) и ДАТУ ПРОДАЖИ (кол. Q=17).
    При статусе 'Продана' → текст 'ПРОДАНА' заглавными, цвет букв зелёный в A, B, P, Q.
    """
    try:
        client = get_client()
        spreadsheet = client.open_by_key(SHEET_ID)
        sheet = spreadsheet.sheet1
        
        clean_article = str(article).strip()
        cell = sheet.find(clean_article)
        
        if not cell:
            return f"️ Артикул '{clean_article}' НЕ НАЙДЕН в таблице."
        
        row = cell.row
        
        # 1. Определяем текст статуса (ПРОДАНА заглавными, если продана)
        if status.lower() in ['продана', 'продано', 'sold']:
            status_text = "ПРОДАНА"
        else:
            status_text = status
        
        # 2. Обновляем текст в колонках P (16) и Q (17)
        sheet.update_cell(row, 16, status_text)
        if date_str:
            sheet.update_cell(row, 17, date_str)
        
        # 3. Определяем цвет текста
        if status.lower() in ['продана', 'продано', 'sold', 'оплачена', 'paid']:
            text_color = {'red': 0.0, 'green': 0.7, 'blue': 0.0}  # 🟢 Зелёный
            bold = True
        else:
            text_color = {'red': 0.0, 'green': 0.0, 'blue': 0.0}  # ⚫ Чёрный
            bold = False
        
        # 4. Красим текст в колонках A(0), B(1), P(15), Q(16)
        requests = []
        for col_index in [0, 1, 15, 16]:  # A, B, P, Q
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
                                "bold": bold
                            }
                        }
                    },
                    "fields": "userEnteredFormat.textFormat(foregroundColor,bold)"
                }
            })
        
        # 5. Отправляем запрос через объект таблицы
        spreadsheet.batch_update({"requests": requests})
        
        return f"✅ Строка {row} обновлена. Статус: '{status_text}'."
        
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def export_db_to_sheet():
    """Выгружает данные из SQLite в таблицу (17 колонок: A-Q)"""
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
                'sold': 'ПРОДАНА',
                'paid': 'Оплачена',
                'shipped': 'Отгружена'
            }.get(status, 'Свободна')
            
            # Маппинг под 17 колонок (A-Q):
            rows_to_add.append([
                article,          # 1. A: АРТИКУЛ
                name,             # 2. B: НАИМЕНОВАНИЕ
                '',               # 3. C: КАТЕГОРИЯ
                '',               # 4. D: ПОДКАТЕГОРИЯ
                brand,            # 5. E: МАРКА
                model,            # 6. F: МОДЕЛЬ
                '',               # 7. G: № КУЗОВА
                '',               # 8. H: СОСТОЯНИЕ
                '',               # 9. I: ПРОИЗВОДИТЕЛЬ
                str(stock),       # 10. J: ОСТАТОК
                '',               # 11. K: ПРИМЕЧАНИЕ
                location,         # 12. L: ЛОКАЦИЯ
                '',               # 13. M: ЦЕНА ЗАКУП
                '',               # 14. N: ЦЕНА ОПТ
                str(price_drom),  # 15. O: ЦЕНА ДРОМ
                '',               # 16. P: СТАТУС ДРОМ
                status_text,      # 17. Q: СТАТУС ПРОДАЖИ (было P, теперь Q)
                ''                # 18. R: ДАТА ПРОДАЖИ (было Q, теперь R)
            ])
        
        # Очищаем старые данные (оставляем только заголовки в строке 1)
        if sheet.row_count > 1:
            sheet.delete_rows(2, sheet.row_count)
        
        # Добавляем актуальные данные
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