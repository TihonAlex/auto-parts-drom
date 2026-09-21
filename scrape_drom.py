import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import re

async def scrape_drom_active_listings():
    print("🚀 Запускаем браузер для сбора активных объявлений с Дрома...")
    
    async with async_playwright() as p:
        # Запускаем браузер в видимом режиме, чтобы ты видел, что происходит
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Ссылка на твои активные объявления
        url = "https://baza.drom.ru/personal/actual/bulletins"
        print(f"Переходим по ссылке: {url}")
        await page.goto(url, wait_until="networkidle")
        
        # Даем время на возможную загрузку или капчу (если вдруг появится)
        await asyncio.sleep(3)
        
        active_parts = []
        
        while True:
            print("📄 Сканируем текущую страницу объявлений...")
            
            # На Дроме каждое объявление в личном кабинете обычно имеет блок с названием и описанием
            # Мы соберем все заголовки объявлений со страницы
            titles = await page.locator('.b-ListingItem__title, .js-cb-ListingItem-title, a[href*="/user/"]').all_text_contents()
            
            # Если элементов нет, пробуем более общий селектор для списка объявлений в личном кабинете
            if not titles:
                # Альтернативный селектор для таблицы/списка объявлений
                rows = await page.locator('tr, .b-ListingItem').all()
                for row in rows:
                    text = await row.inner_text()
                    if text.strip():
                        titles.append(text)
            
            for title in titles:
                # Очищаем текст от лишних пробелов и переносов строк
                clean_title = " ".join(title.split())
                if len(clean_title) > 10: # Фильтруем мусорные короткие строки
                    # Пытаемся извлечь артикул (OEM номер) из заголовка с помощью регулярного выражения
                    # Ищем последовательности букв и цифр, характерные для артикулов (например, 8159060040, ST21211D7L)
                    oem_match = re.search(r'\b([A-Za-zА-Яа-я]{1,4}\d{4,10}|\d{7,12})\b', clean_title)
                    oem = oem_match.group(1).upper() if oem_match else "Не найден"
                    
                    active_parts.append({
                        'Название на Дроме': clean_title,
                        'Извлеченный артикул': oem
                    })
            
            # Проверяем, есть ли кнопка "Следующая страница"
            next_button = page.locator('a:has-text("Следующая"), .b-Pagination__next, [rel="next"]')
            if await next_button.count() > 0:
                print("➡️ Переходим на следующую страницу...")
                await next_button.click()
                await asyncio.sleep(2) # Пауза, чтобы не спамить запросами (безопасность аккаунта!)
            else:
                print("✅ Все страницы просмотрены.")
                break
        
        await browser.close()
        
        # Сохраняем результат в CSV
        df = pd.DataFrame(active_parts)
        output_file = "drom_active.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"💾 Данные сохранены в файл: {output_file}")
        print(f"Всего найдено активных объявлений: {len(df)}")

# Запуск скрипта
if __name__ == "__main__":
    asyncio.run(scrape_drom_active_listings())