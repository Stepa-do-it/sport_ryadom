import pandas as pd
import psycopg2
import re
from datetime import datetime

# Подключение к базе данных
conn = psycopg2.connect(
    database="sport_ryadom",
    user="user",  # твой пользователь (скорее всего user)
    password="",  # если пароль не ставил, оставь пустым
    host="localhost"
)
cur = conn.cursor()

# Создаем таблицу
cur.execute("""
            DROP TABLE IF EXISTS sport_facilities;
            CREATE TABLE sport_facilities
            (
                id            SERIAL PRIMARY KEY,
                name          VARCHAR(500),
                short_name    VARCHAR(500),
                full_name     TEXT,
                services      TEXT[],
                address       TEXT,
                district      VARCHAR(200),
                adm_area      VARCHAR(200),
                available_k   VARCHAR(50),
                available_o   VARCHAR(50),
                available_z   VARCHAR(50),
                available_s   VARCHAR(50),
                working_hours TEXT,
                phone         VARCHAR(200),
                email         VARCHAR(200),
                website       VARCHAR(500),
                latitude      FLOAT,
                longitude     FLOAT,
                global_id     BIGINT UNIQUE
            );
            """)
conn.commit()
print("Таблица создана")

# Читаем Excel файл, пропускаем первую строку данных (русские заголовки)
df = pd.read_excel('sport_data.xlsx', header=0)
print(f"Всего строк в файле: {len(df)}")


# Функция для парсинга адреса и доступности
def parse_object_address(address_text):
    if pd.isna(address_text) or address_text == 'nested data':
        return {}, {}

    result = {}
    availability = {}

    # Парсим построчно
    lines = str(address_text).split('\n')
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if key in ['AdmArea', 'District', 'PostalCode', 'Address']:
                result[key] = value
            elif key in ['available_k', 'available_o', 'available_z', 'available_s']:
                availability[key] = value

    return result, availability


# Функция для парсинга geoData
def parse_geodata(geo_text):
    if pd.isna(geo_text):
        return None, None

    try:
        # Ищем координаты в строке вида {coordinates=[[37.387, 55.881]]}
        match = re.search(r'\[\[(.*?),(.*?)\]\]', str(geo_text))
        if match:
            lon = float(match.group(1).strip())
            lat = float(match.group(2).strip())
            return lat, lon
    except:
        pass
    return None, None


# Загружаем данные, пропуская первую строку (индекс 0)
success_count = 0
for idx, row in df.iterrows():
    try:
        # Пропускаем строку, если global_id не число (это русские заголовки)
        if pd.isna(row['global_id']) or str(row['global_id']).strip() == 'global_id':
            print(f"Пропуск строки {idx} (служебная)")
            continue

        # Основные поля
        name = row['CommonName'] if pd.notna(row['CommonName']) else row['ShortName']
        short_name = row['ShortName'] if pd.notna(row['ShortName']) else ''
        full_name = row['FullName'] if pd.notna(row['FullName']) else ''

        # Парсим услуги (Services)
        services = []
        if pd.notna(row['Services']):
            services_text = str(row['Services'])
            # Убираем квадратные скобки и разбиваем по запятым
            services_text = services_text.strip('[]')
            services = [s.strip().strip("'\"") for s in services_text.split(',') if s.strip()]

        # Парсим адрес
        addr_info, availability = parse_object_address(row['ObjectAddress'])

        address = addr_info.get('Address', '')
        district = addr_info.get('District', '')
        adm_area = addr_info.get('AdmArea', '')

        # Доступность
        available_k = availability.get('available_k', '')
        available_o = availability.get('available_o', '')
        available_z = availability.get('available_z', '')
        available_s = availability.get('available_s', '')

        # Часы работы
        working_hours = row['WorkingHours'] if pd.notna(row['WorkingHours']) else ''

        # Контакты
        phone = row['PublicPhone'] if pd.notna(row['PublicPhone']) else ''
        email = row['Email'] if pd.notna(row['Email']) else ''
        website = row['WebSite'] if pd.notna(row['WebSite']) else ''

        # Координаты
        lat, lon = parse_geodata(row['geoData'])

        # global_id
        global_id = int(row['global_id']) if pd.notna(row['global_id']) else None

        # Вставляем в базу
        cur.execute("""
                    INSERT INTO sport_facilities
                    (name, short_name, full_name, services, address, district, adm_area,
                     available_k, available_o, available_z, available_s, working_hours,
                     phone, email, website, latitude, longitude, global_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s) ON CONFLICT (global_id) DO NOTHING
                    """, (
                        name, short_name, full_name, services, address, district, adm_area,
                        available_k, available_o, available_z, available_s, working_hours,
                        phone, email, website, lat, lon, global_id
                    ))

        success_count += 1
        if success_count % 50 == 0:
            conn.commit()
            print(f"Загружено {success_count} объектов...")

    except Exception as e:
        print(f"Ошибка в строке {idx}: {e}")
        continue

# Финальный коммит
conn.commit()
print(f"Загрузка завершена! Успешно загружено: {success_count} объектов")

# Проверка
cur.execute("SELECT COUNT(*) FROM sport_facilities")
count = cur.fetchone()[0]
print(f"Всего объектов в базе: {count}")

cur.close()
conn.close()