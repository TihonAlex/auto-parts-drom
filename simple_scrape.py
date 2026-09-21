import pandas as pd
import re

print("🔍 Анализируем файл parsed_parts.xlsx для поиска уже размещенных позиций...")

try:
    # Читаем распарсенный файл
    df = pd.read_excel("parsed_parts.xlsx")
    
    # Ищем позиции, которые уже имеют цену Дром (значит они скорее всего размещены)
    # Или можем использовать другую логику - например, если есть артикул
    
    active_parts = []
    
    for idx, row in df.iterrows():
        article = str(row.get('Артикул', '')).strip()
        name = str(row.get('Наименование', '')).strip()
        price = row.get('Цена Дром', '')
        
        if pd.notna(price) and price != '' and price != 0:
            # Если есть цена, считаем что позиция размещена
            active_parts.append({
                'Артикул': article,
                'Название': name,
                'Извлеченный артикул': article
            })
    
    # Сохраняем результат
    df_active = pd.DataFrame(active_parts)
    df_active.to_csv("drom_active.csv", index=False, encoding='utf-8-sig')
    
    print(f"✅ Создан файл drom_active.csv")
    print(f"   Найдено {len(df_active)} позиций с ценой Дром")
    print(f"   Теперь запусти parser.py еще раз для добавления колонки 'Статус Дром'")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")