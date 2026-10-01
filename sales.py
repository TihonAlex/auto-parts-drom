import sqlite3
import csv
from datetime import datetime

DB_NAME = "parts_database.db"

def create_sale(article: str, client_name: str, client_phone: str = "") -> int:
    """Создает новую продажу и резервирует деталь. Телефон необязателен."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Проверяем, свободна ли деталь
    cursor.execute("SELECT status FROM parts WHERE артикул = ?", (article,))
    part = cursor.fetchone()
    
    if not part:
        conn.close()
        return -1  # Деталь не найдена
    if part[0] != 'available':
        conn.close()
        return -2  # Деталь уже зарезервирована или продана

    # 2. Создаем запись о продаже (телефон может быть пустым)
    cursor.execute("""
        INSERT INTO sales (part_article, client_name, client_phone, status)
        VALUES (?, ?, ?, 'pending')
    """, (article, client_name, client_phone))
    sale_id = cursor.lastrowid
    
    # 3. Меняем статус детали на 'reserved'
    cursor.execute("UPDATE parts SET status = 'reserved' WHERE артикул = ?", (article,))
    
    conn.commit()
    conn.close()
    return sale_id

def update_sale_status(sale_id: int, new_status: str):
    """Обновляет статус продажи и синхронизирует статус детали."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Получаем артикул детали для этой продажи
    cursor.execute("SELECT part_article FROM sales WHERE id = ?", (sale_id,))
    sale = cursor.fetchone()
    if not sale:
        conn.close()
        return False
    article = sale[0]
    
    # Определяем новый статус для детали
    part_status_map = {
        'paid': 'sold',
        'shipped': 'shipped',
        'cancelled': 'available',
        'pending': 'reserved'
    }
    new_part_status = part_status_map.get(new_status, 'reserved')
    
    # Обновляем продажу
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if new_status == 'paid':
        cursor.execute("UPDATE sales SET status = ?, paid_at = ? WHERE id = ?", (new_status, now, sale_id))
    elif new_status == 'shipped':
        cursor.execute("UPDATE sales SET status = ?, shipped_at = ? WHERE id = ?", (new_status, now, sale_id))
    else:
        cursor.execute("UPDATE sales SET status = ? WHERE id = ?", (new_status, sale_id))
        
    # Обновляем деталь
    cursor.execute("UPDATE parts SET status = ? WHERE артикул = ?", (new_part_status, article))
    
    conn.commit()
    conn.close()
    return True

def get_sales_by_status(status: str) -> list:
    """Возвращает список продаж по статусу."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.part_article, p.name, s.client_name, s.client_phone, s.created_at 
        FROM sales s 
        JOIN parts p ON s.part_article = p.артикул 
        WHERE s.status = ?
        ORDER BY s.created_at DESC
    """, (status,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_sale_details(sale_id: int) -> dict:
    """Возвращает полные данные о продаже."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.part_article, p.name, p.price, s.client_name, s.client_phone, 
               s.status, s.tracking_number, s.created_at
        FROM sales s 
        JOIN parts p ON s.part_article = p.артикул 
        WHERE s.id = ?
    """, (sale_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0], "article": row[1], "name": row[2], "price": row[3],
            "client_name": row[4], "client_phone": row[5], "status": row[6],
            "tracking": row[7], "date": row[8]
        }
    return None

def add_tracking_to_sale(sale_id: int, tracking_number: str, cdek_uuid: str):
    """Добавляет трек-номер к продаже."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sales SET tracking_number = ?, cdek_uuid = ? WHERE id = ?
    """, (tracking_number, cdek_uuid, sale_id))
    conn.commit()
    conn.close()

def generate_excel_report():
    """Генерирует CSV файл со всеми продажами и статусами деталей."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.part_article, p.name, p.price, s.client_name, s.client_phone, 
               s.status, s.tracking_number, s.created_at, s.paid_at, s.shipped_at
        FROM sales s 
        JOIN parts p ON s.part_article = p.article 
        ORDER BY s.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    filename = "sales_report.csv"
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Артикул", "Название", "Цена", "Клиент", "Телефон", "Статус", "Трек-номер", "Создана", "Оплачена", "Отгружена"])
        writer.writerows(rows)
        
    return filename