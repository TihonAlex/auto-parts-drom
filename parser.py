import pandas as pd
import re
import openpyxl
from openpyxl.styles import Font
import shutil
import os
from datetime import datetime

def backup_to_external_drive(file_path, drive_name):
    """Создает резервную копию файла на внешнем диске с меткой времени"""
    # Путь к внешнему диску в macOS
    external_root = f"/Volumes/{drive_name}"
    
    # Проверяем, подключен ли диск
    if not os.path.exists(external_root):
        print(f"⚠️ Внешний диск '{drive_name}' не найден. Пропускаем бэкап.")
        return False
    
    # Создаем папку для бэкапов проекта на диске
    backup_dir = os.path.join(external_root, "AutoParts_Project_Backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Формируем имя файла с датой и временем: parsed_parts_2026-09-20_15-30-00.xlsx
    filename = os.path.basename(file_path)
    name, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"{name}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Копируем файл (copy2 сохраняет метаданные, включая дату создания)
    try:
        shutil.copy2(file_path, backup_path)
        print(f"✅ Резервная копия создана на внешнем диске: {backup_filename}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании резервной копии: {e}")
        return False


class PartsParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = []
        self.current_category = None
        self.current_brand = None
        self.current_subcategory = None
        self.column_map = {}
        
        self.categories = [
            'Оптика', 'Лобовые', 'Капоты', 'Защита ДВС', 'Рамка кузова', 
            'Решетки', 'Бампера', 'Ударогасители', 'Железо', 'Усилители бампера',
            'Бампера  + спойлеры + молдинг', 'Крыло', 'Крышка багажника', 'Двери'
        ]
        
        self.subcategories = [
            'БЛОК-ФАРЫ', 'ГАБАРИТЫ', 'ПРОТИВОТУМАННЫЕ ФАРЫ', 
            'ЗАДНИЕ ФОНАРИ И ВСТАВКИ', 'П/ТУМАННЫЕ ФАРЫ', 
            'ГАБАРИТЫ ПОВОРОТЫ', 'ТУМАНКИ', 'ЛОБОВЫЕ СТЁКЛА'
        ]
        
        self.brands = {
            'TOYOTA': 'TOYOTA', 'NISSAN': 'NISSAN', 'MAZDA': 'MAZDA', 
            'HONDA': 'HONDA', 'DAEWOO': 'DAEWOO', 'MITSUBISHI': 'MITSUBISHI', 
            'FORD': 'FORD', 'MERCEDES-BENZ': 'MERCEDES-BENZ', 'MERSEDES-BENZ': 'MERCEDES-BENZ',
            'MERSEDES': 'MERCEDES-BENZ', 'AUDI': 'AUDI', 'VOLKSWAGEN': 'VOLKSWAGEN', 
            'VOLKWAGEN': 'VOLKSWAGEN', 'VOLKSvagen': 'VOLKSWAGEN', 'OPEL': 'OPEL',
            'ВАЗ': 'ВАЗ', 'VAZ': 'ВАЗ', 'HYUNDAI': 'HYUNDAI', 'RENAULT': 'RENAULT', 
            'BMW': 'BMW', 'CHEVROLET': 'CHEVROLET', 'CHEVRОLET': 'CHEVROLET',
            'SKODA': 'SKODA', 'SCODA': 'SKODA', 'KIA': 'KIA', 'LAND ROVER': 'LAND ROVER', 
            'FIAT': 'FIAT', 'SUBARU': 'SUBARU', 'SUZUKI': 'SUZUKI',
            'PEUGEOT': 'PEUGEOT', 'CITROEN': 'CITROEN', 'JAGUAR': 'JAGUAR', 
            'PORSCHE': 'PORSCHE', 'PORSСHE': 'PORSCHE', 'LADA': 'LADA', 'ГАЗ': 'ГАЗ', 'УАЗ': 'УАЗ',
            'LIFAN': 'LIFAN', 'CHERY': 'CHERY', 'GEELY': 'GEELY', 'HAVAL': 'HAVAL', 
            'SSANG YONG': 'SSANG YONG', 'JAC': 'JAC', 'OMODA': 'OMODA',
            'DAIHATSU': 'DAIHATSU', 'INFINITI': 'INFINITI', 'LEXUS': 'LEXUS', 
            'CADILLAC': 'CADILLAC', 'VOLVO': 'VOLVO', 'SEAT': 'SEAT', 'EXEED': 'EXEED'
        }
    
    def is_category(self, text):
        if not text or pd.isna(text):
            return False
        text = str(text).strip().upper()
        return any(cat.upper() in text for cat in self.categories)
    
    def is_subcategory(self, text):
        if not text or pd.isna(text):
            return False
        text = str(text).strip().upper()
        return any(sub.upper() in text for sub in self.subcategories)
    
    def is_brand(self, text):
        if not text or pd.isna(text):
            return False
        text = str(text).strip().upper()
        return text in self.brands.keys()
    
    def detect_column_structure(self, row):
        self.column_map = {}
        for idx, val in enumerate(row):
            if pd.notna(val):
                val_str = str(val).strip().upper()
                if 'АРТИКУЛ' in val_str:
                    self.column_map['article'] = idx
                elif 'НАИМЕНОВАНИЕ' in val_str or 'ТМЦ' in val_str:
                    self.column_map['name'] = idx
                elif 'ЯЧЕЙКА' in val_str or 'ПОЛКА' in val_str:
                    self.column_map['location'] = idx
                elif 'ПРОИЗВОДИТЕЛЬ' in val_str or 'АНАЛОГ' in val_str:
                    self.column_map['manufacturer'] = idx
                elif 'КОЛ-ВО' in val_str or 'КОЛИЧЕСТВО' in val_str:
                    self.column_map['quantity'] = idx
                elif 'ДРОМ' in val_str or 'РОЗНИЦА' in val_str:
                    self.column_map['price_drom'] = idx
                elif 'ЗАКУП' in val_str:
                    self.column_map['price_purchase'] = idx
                elif 'ОПТ' in val_str:
                    self.column_map['price_wholesale'] = idx
                elif 'ЦЕНА' in val_str and 'price_drom' not in self.column_map:
                    self.column_map['price_drom'] = idx
                elif 'МАРКА' in val_str:
                    self.column_map['brand'] = idx
                elif 'КУЗОВ' in val_str:
                    self.column_map['body_number'] = idx
    
    def parse_file(self):
        print(f"Начинаю парсинг файла: {self.file_path}")
        all_sheets = pd.read_excel(self.file_path, sheet_name=None, header=None)
        print(f"Найдено листов в файле: {len(all_sheets)}")
        
        for sheet_name, df in all_sheets.items():
            print(f"\nОбрабатываю лист: '{sheet_name}'")
            self.current_category = sheet_name
            self.current_brand = None
            self.current_subcategory = None
            self.column_map = {}
            
            for idx, row in df.iterrows():
                first_value = None
                for val in row:
                    if pd.notna(val) and str(val).strip():
                        first_value = str(val).strip()
                        break
                
                if not first_value:
                    continue
                
                if self.is_category(first_value):
                    self.current_category = first_value
                    self.current_brand = None
                    print(f"  Найдена категория: {self.current_category}")
                    continue
                
                if self.is_subcategory(first_value):
                    self.current_subcategory = first_value.upper()
                    continue
                
                if self.is_brand(first_value):
                    brand_key = first_value.upper()
                    self.current_brand = self.brands.get(brand_key, brand_key)
                    continue
                
                if self._is_header_row(row):
                    self.detect_column_structure(row)
                    continue
                
                if self._is_data_row(row):
                    item = self._extract_item(row)
                    if item:
                        self.data.append(item)
        
        print(f"\n✅ Парсинг завершен. Всего найдено товаров: {len(self.data)}")
        return self.data
    
    def _is_header_row(self, row):
        row_values = [str(v).strip().upper() for v in row if pd.notna(v)]
        header_keywords = ['АРТИКУЛ', 'НАИМЕНОВАНИЕ', 'ТМЦ', 'ЦЕНА', 'КОЛ-ВО', 
                          'ПОЛКА', 'ЯЧЕЙКА', 'ПРОИЗВОДИТЕЛЬ', 'МАРКА']
        return any(keyword in ' '.join(row_values) for keyword in header_keywords)
    
    def _is_data_row(self, row):
        if 'article' in self.column_map:
            idx = self.column_map['article']
            if idx < len(row) and pd.notna(row[idx]):
                val = str(row[idx]).strip()
                if re.search(r'[A-Za-zА-Яа-я]', val) and re.search(r'[0-9]', val):
                    return True
                if val.isdigit() and len(val) > 4:
                    return True
        return False
    
    def _get_value(self, row, key):
        if key in self.column_map:
            idx = self.column_map[key]
            if idx < len(row) and pd.notna(row[idx]):
                return str(row[idx]).strip()
        return ''
    
    def _extract_item(self, row):
        item = {
            'Артикул': self._get_value(row, 'article'),
            'Наименование': self._get_value(row, 'name'),
            'Категория': self.current_category or '',
            'Подкатегория': self.current_subcategory or '',
            'Марка': self.current_brand or '',
            'Модель': '',
            '№ кузова': self._get_value(row, 'body_number'),
            'Состояние': '',
            'Производитель': self._get_value(row, 'manufacturer'),
            'Остаток': self._get_value(row, 'quantity'),
            'Примечание': '',
            'Локация': self._get_value(row, 'location'),
            'Цена закуп': '',
            'Цена опт': '',
            'Цена Дром': ''
        }
        
        if 'price_drom' in self.column_map:
            idx = self.column_map['price_drom']
            if idx < len(row) and pd.notna(row[idx]):
                try:
                    price = float(str(row[idx]).replace(',', '.').replace(' ', ''))
                    if price > 0:
                        item['Цена Дром'] = price
                except:
                    pass
        
        if 'price_purchase' in self.column_map:
            idx = self.column_map['price_purchase']
            if idx < len(row) and pd.notna(row[idx]):
                try:
                    price = float(str(row[idx]).replace(',', '.').replace(' ', ''))
                    if price > 0:
                        item['Цена закуп'] = price
                except:
                    pass
        
        if 'price_wholesale' in self.column_map:
            idx = self.column_map['price_wholesale']
            if idx < len(row) and pd.notna(row[idx]):
                try:
                    price = float(str(row[idx]).replace(',', '.').replace(' ', ''))
                    if price > 0:
                        item['Цена опт'] = price
                except:
                    pass
        
        item['Состояние'] = self._detect_condition(item)
        name = item['Наименование']
        item['Модель'] = self._extract_model(name)
        
        if not item['№ кузова']:
            item['№ кузова'] = self._extract_body_number(name)
        
        if item['Состояние'] == 'Б/У' and not item['Примечание']:
            item['Примечание'] = 'Фото по запросу'
        
        return item
    
    def _detect_condition(self, item):
        text = f"{item['Наименование']} {item['Производитель']}".upper()
        used_indicators = ['Б/У', 'БУ', 'Б\\У', 'ОРИГ Б/У', 'ОРИГ/НОВЫЙ', 
                          'ОРИГИНАЛ Б/У', 'Б/У ОРИГИНАЛ', 'Б/У ОРИГ', 'DEF',
                          'С ДЕФЕКТОМ', 'С РЕМОНТОМ', 'ТРЕЩИНА']
        for indicator in used_indicators:
            if indicator in text:
                return 'Б/У'
        
        new_indicators = ['SAT', 'DEPO', 'TYC', 'НОВЫЙ', 'НОВ', 'NEW', 
                         'ОРИГИНАЛ/НОВЫЙ', 'ОРИГ/НОВЫЙ', 'ОРИГ НОВЫЙ',
                         'НОВ/ОРИГ', 'НОВЫЙ/ОРИГ', 'Дубл/новый', 'ДУБЛЬ/НОВЫЙ']
        for indicator in new_indicators:
            if indicator in text:
                return 'Новая'
        return 'Б/У'
    
    def _extract_model(self, text):
        if not text:
            return ''
        patterns = [
            r'(Land Cruiser\s*\d+)', r'(Land Cruiser\s+Prado)', r'(RAV4)',
            r'(Camry)', r'(Corolla)', r'(Civic)', r'(Accord)', r'(CR-V)',
            r'(Fit)', r'(Outlander)', r'(Lancer)', r'(Pajero)', r'(X-Trail)',
            r'(Qashqai)', r'(Focus)', r'(Golf)', r'(Passat)', r'(Astra)',
            r'(Vectra)', r'(Logan)', r'(Sandero)', r'(Duster)', r'(Solaris)',
            r'(Rio)', r'(Ceed)', r'(Sportage)', r'(Spectra)', r'(Nexia)',
            r'(Matiz)', r'(Lacetti)', r'(Cruze)', r'(Aveo)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ''
    
    def _extract_body_number(self, text):
        if not text:
            return ''
        patterns = [
            r'\b(AE100|AE101|AE110|ACV30|ACV40|ACV50|FJ120|FJ150|UZJ100|UZJ200|'
            r'NCP10|NCP90|ZCA20|ZCA25|MCU10|MCU15|MCU30|MCU35|'
            r'GD1|GD3|GE8|RD1|RD5|RE5|BG5|BL5|BK5|BL#|J10|J15|J20|'
            r'W210|W124|W221|W202|E46|E39|B5|B6|ZE120|NZE120|RT190|'
            r'CP8W|FD1|FD3|ES1|AZT250|Y10|Y11|AT211|ST210|GF7|GF8|KS|KW|BM51|J10#|J15#|J200)\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return ''
    
    def remove_duplicates(self):
        if not self.data:
            return
        print(f"\n🔍 Удаление дубликатов внутри файла...")
        initial_count = len(self.data)
        df = pd.DataFrame(self.data)
        df_no_duplicates = df.drop_duplicates(subset=['Артикул'], keep='first')
        print(f"  Найдено внутренних дубликатов: {initial_count - len(df_no_duplicates)}")
        self.data = df_no_duplicates.to_dict('records')

    def mark_drom_status(self, drom_csv_path="drom_active.csv"):
        import os
        if not os.path.exists(drom_csv_path):
            print("⚠️ Файл drom_active.csv не найден. Пропускаем сверку с Дромом.")
            return
        
        print(f"🔍 Сверяем артикулы с активными объявлениями на Дроме ({drom_csv_path})...")
        drom_df = pd.read_csv(drom_csv_path)
        active_articles = set(drom_df['Извлеченный артикул'].dropna().astype(str).str.upper())
        
        df = pd.DataFrame(self.data)
        df['Статус Дром'] = df['Артикул'].astype(str).str.upper().apply(
            lambda x: "Уже размещено" if x in active_articles else "К загрузке"
        )
        self.data = df.to_dict('records')
        print("✅ Сверка завершена.")

    def save_to_excel(self, output_path):
        if not self.data:
            print("Нет данных для сохранения")
            return

        backup_to_external_drive(output_path, "Dockst-AT") 
        
        df = pd.DataFrame(self.data)
        columns_order = [
            'Артикул', 'Наименование', 'Категория', 'Подкатегория',
            'Марка', 'Модель', '№ кузова', 'Состояние', 'Производитель',
            'Остаток', 'Примечание', 'Локация', 'Цена закуп', 'Цена опт',
            'Цена Дром', 'Статус Дром'
        ]
        existing_columns = [col for col in columns_order if col in df.columns]
        df = df[existing_columns]
        
        # 1. Сохраняем базовый файл через pandas
        df.to_excel(output_path, index=False, sheet_name='Товары')
        print(f"\n💾 Данные сохранены в файл: {output_path}")
        
        # 2. Применяем визуальное форматирование через openpyxl
        print("🎨 Применяем форматирование (жирный + курсив) для размещенных позиций...")
        wb = openpyxl.load_workbook(output_path)
        ws = wb.active
        
        # Находим индекс колонки "Статус Дром"
        status_col_idx = None
        for col in range(1, ws.max_column + 1):
            if ws.cell(row=1, column=col).value == "Статус Дром":
                status_col_idx = col
                break
        
        if status_col_idx:
            formatted_count = 0
            # Проходим по всем строкам данных (начиная со 2-й, так как 1-я - заголовок)
            for row in range(2, ws.max_row + 1):
                cell_value = ws.cell(row=row, column=status_col_idx).value
                if str(cell_value).strip() == "Уже размещено":
                    # Применяем жирный и курсив ко всем ячейкам в этой строке
                    target_font = Font(bold=True, italic=True)
                    for col in range(1, ws.max_column + 1):
                        ws.cell(row=row, column=col).font = target_font
                    formatted_count += 1
            
            wb.save(output_path)
            print(f"✅ Форматирование успешно применено к {formatted_count} строкам!")
        else:
            print("⚠️ Колонка 'Статус Дром' не найдена, форматирование пропущено.")


if __name__ == "__main__":
    input_file = "КНИГА (УЧЕТ).xls"
    output_file = "parsed_parts.xlsx"
    
    parser = PartsParser(input_file)
    parser.parse_file()
    parser.remove_duplicates()
    parser.mark_drom_status("drom_active.csv")
    parser.save_to_excel(output_file)
    
    print("\n✅ Готово! Открой файл parsed_parts.xlsx и проверь результат.")