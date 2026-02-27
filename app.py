from flask import Flask, render_template, request
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
import requests
from math import radians, sin, cos, sqrt, atan2
from flask import Flask, render_template, request, redirect, url_for, flash, session


app = Flask(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-123'  # нужен для сессий

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # если не залогинен, отправляет на страницу входа
# Функция для подключения к базе

class User(UserMixin):
    def __init__(self, id, email, first_name, last_name, home_address=None):
        self.id = id
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.home_address = home_address

    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()

        if user_data:
            return User(
                id=user_data['id'],
                email=user_data['email'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                home_address = user_data['home_address']
            )
        return None


# Функция для преобразования адреса в координаты
def get_coordinates_from_address(address):
    if not address:
        print("Адрес пустой")
        return None, None

    print(f"Ищем координаты для: '{address}'")

    from urllib.parse import quote

    # Кодируем адрес для URL
    encoded_address = quote(address)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"

    headers = {
        'User-Agent': 'SportRyadomApp/1.0',  # убрали русский текст
        'Accept-Language': 'ru'
    }

    try:
        print(f"Отправляем запрос к: {url[:100]}...")
        response = requests.get(url, headers=headers)
        print(f"Статус ответа: {response.status_code}")

        response.encoding = 'utf-8'
        data = response.json()

        print(f"Получено объектов: {len(data)}")

        if data and len(data) > 0:
            print(f"Найдено: {data[0].get('display_name')}")
            return float(data[0]['lat']), float(data[0]['lon'])
        else:
            print("Нет результатов")

    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

    return None, None

# Функция расчета расстояния по формуле гаверсинуса
def haversine(lat1, lon1, lat2, lon2):
    if not all([lat1, lon1, lat2, lon2]):
        return float('inf')

    R = 6371  # радиус Земли в км

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return round(R * c, 2)  # расстояние в км, округленное до 2 знаков


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Получаем данные из формы
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']

        # Хэшируем пароль
        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Сохраняем пользователя в БД
            cur.execute("""
                        INSERT INTO users (first_name, last_name, email, password_hash)
                        VALUES (%s, %s, %s, %s) RETURNING id
                        """, (first_name, last_name, email, password_hash))

            user_id = cur.fetchone()[0]
            conn.commit()

            # Сразу логиним пользователя
            user = User.get(user_id)
            login_user(user)

            return redirect(url_for('profile'))

        except psycopg2.IntegrityError:
            # Пользователь с таким email уже существует
            flash('Пользователь с таким email уже существует')
            return redirect(url_for('register'))
        finally:
            cur.close()
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_data = cur.fetchone()

        cur.close()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            # Создаем объект пользователя
            user = User(
                id=user_data['id'],
                email=user_data['email'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name']
            )
            login_user(user)
            return redirect(url_for('profile'))
        else:
            flash('Неверный email или пароль')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Получаем избранное пользователя
    cur.execute("""
                SELECT f.*, sf.name, sf.address
                FROM favorites f
                         JOIN sport_facilities sf ON f.facility_id = sf.id
                WHERE f.user_id = %s
                ORDER BY f.created_at DESC
                """, (current_user.id,))

    favorites = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('profile.html',
                           user=current_user,
                           favorites=favorites)

#маршрут для избранного
#избранное функц
@app.route('/favorite/<int:facility_id>', methods=['POST'])
@login_required
def toggle_favorite(facility_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Проверяем, есть ли уже в избранном
    cur.execute("""
                SELECT id
                FROM favorites
                WHERE user_id = %s
                  AND facility_id = %s
                """, (current_user.id, facility_id))

    favorite = cur.fetchone()

    if favorite:
        # Если есть - удаляем
        cur.execute("DELETE FROM favorites WHERE id = %s", (favorite[0],))
        flash('Удалено из избранного')
    else:
        # Если нет - добавляем
        cur.execute("""
                    INSERT INTO favorites (user_id, facility_id)
                    VALUES (%s, %s)
                    """, (current_user.id, facility_id))
        flash('Добавлено в избранное')

    conn.commit()
    cur.close()
    conn.close()

    return redirect(request.referrer or url_for('index'))


@app.route('/update_address', methods=['POST'])
@login_required
def update_address():
    home_address = request.form['home_address']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
                UPDATE users
                SET home_address = %s
                WHERE id = %s
                """, (home_address, current_user.id))

    conn.commit()
    cur.close()
    conn.close()

    flash('Адрес сохранен')
    return redirect(url_for('profile'))


@app.route('/nearby')
@login_required
def nearby():
    # Проверяем, есть ли адрес у пользователя
    if not current_user.home_address:
        flash('Сначала укажите домашний адрес в профиле')
        return redirect(url_for('profile'))

    print(f"1. Адрес из БД: '{current_user.home_address}'")

    # Получаем координаты адреса пользователя
    user_lat, user_lon = get_coordinates_from_address(current_user.home_address)

    print(f"2. Полученные координаты: lat={user_lat}, lon={user_lon}")

    if not user_lat or not user_lon:
        print("3. Координаты не найдены!")
        flash('Не удалось определить координаты вашего адреса. Проверьте правильность ввода.')
        return redirect(url_for('profile'))

    print(f"3. Координаты найдены, ищем объекты...")

    # Получаем все объекты из БД с координатами
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
                SELECT id, name, address, latitude, longitude, available_k, district
                FROM sport_facilities
                WHERE latitude IS NOT NULL
                  AND longitude IS NOT NULL
                """)
    facilities = cur.fetchall()
    print(f"4. Найдено объектов с координатами: {len(facilities)}")

    cur.close()
    conn.close()

    # Считаем расстояние для каждого объекта
    facilities_with_distance = []
    for f in facilities:
        distance = haversine(user_lat, user_lon, f['latitude'], f['longitude'])
        facilities_with_distance.append({
            'id': f['id'],
            'name': f['name'],
            'address': f['address'],
            'district': f['district'],
            'available_k': f['available_k'],
            'distance': distance
        })

    # Сортируем по расстоянию
    facilities_with_distance.sort(key=lambda x: x['distance'])

    # Берем ближайшие 10
    nearby_facilities = facilities_with_distance[:10]
    print(f"5. Отображаем {len(nearby_facilities)} объектов")

    return render_template('nearby.html',
                           facilities=nearby_facilities,
                           user_address=current_user.home_address,
                           user_lat=user_lat,
                           user_lon=user_lon)

def get_db_connection():
    conn = psycopg2.connect(
        database="sport_ryadom",
        user="user",
        password="",
        host="localhost"
    )
    return conn


# Главная страница с поиском
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Получаем параметры из URL (что ввел пользователь)
    sport_filter = request.args.get('sport', '')
    available_filter = request.args.get('available', '')
    name_filter = request.args.get('name', '')
    district_filter = request.args.get('district', '')

    # Получаем все виды спорта для выпадающего списка
    cur.execute("""
                SELECT DISTINCT unnest(services) as sport
                FROM sport_facilities
                WHERE services IS NOT NULL
                ORDER BY sport
                """)
    sports = [row['sport'] for row in cur.fetchall()]

    # Получаем все районы для выпадающего списка
    cur.execute("""
                SELECT DISTINCT district
                FROM sport_facilities
                WHERE district IS NOT NULL
                  AND district != ''
                ORDER BY district
                """)
    districts = [row['district'] for row in cur.fetchall()]


    # Базовый SQL запрос
    query = """
            SELECT id, name, address, district, available_k, latitude, longitude
            FROM sport_facilities
            WHERE 1 = 1 \
            """
    params = []

    # Добавляем фильтр по названию (поиск по части слова)
    if name_filter:
        query += " AND name ILIKE %s"
        params.append(f'%{name_filter}%')

    # Добавляем фильтр по виду спорта
    if sport_filter:
        query += " AND %s = ANY(services)"
        params.append(sport_filter)

    # Добавляем фильтр по доступности
    if available_filter:
        query += " AND available_k = %s"
        params.append(available_filter)

    # Добавляем фильтр по району
    if district_filter:
        query += " AND district = %s"
        params.append(district_filter)

    # Добавляем сортировку и ограничение
    query += " ORDER BY name LIMIT 100"

    # Выполняем запрос
    cur.execute(query, params)
    facilities = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('index.html',
                           sports=sports,
                           districts=districts,
                           facilities=facilities,
                           selected_sport=sport_filter,
                           selected_available=available_filter,
                           search_name=name_filter,
                           selected_district = district_filter)  # выбранный район



# Страница объекта (пока оставим как есть)
@app.route('/facility/<int:id>')
def facility_detail(id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT * FROM sport_facilities WHERE id = %s", (id,))
    facility = cur.fetchone()

    # Проверяем, есть ли объект в избранном у текущего пользователя
    is_favorite = False
    if current_user.is_authenticated:
        cur.execute("""
                    SELECT id
                    FROM favorites
                    WHERE user_id = %s
                      AND facility_id = %s
                    """, (current_user.id, id))
        is_favorite = cur.fetchone() is not None

    cur.close()
    conn.close()

    if facility is None:
        return "Объект не найден", 404

    # Обрабатываем часы работы
    if facility['working_hours']:
        # Убираем DayWeek: и WorkHours:
        hours = facility['working_hours'].replace('DayWeek:', '').replace('WorkHours:', '')

        # Разбиваем на строки
        lines = hours.split('\n')

        # Оставляем только непустые строки (убираем пробелы, табуляцию)
        clean_lines = [line.strip() for line in lines if line.strip()]

        # Склеиваем обратно с переносами
        facility['working_hours'] = '<br>'.join(clean_lines)
    else:
        facility['working_hours'] = 'не указано'

    # Обрабатываем телефон и добавляем (+7)
    if facility['phone']:
        phone = facility['phone'].replace('PublicPhone:', '').strip()
        if phone.startswith('('):
            # (499) 178-75-55 -> +7 (499) 178-75-55
            facility['phone'] = '+7 ' + phone
        else:
            facility['phone'] = '+7 ' + phone
    else:
        facility['phone'] = 'не указан'

    # Обрабатываем email
    if facility['email']:
        facility['email'] = facility['email'].replace('Email:', '').strip()

    return render_template('detail.html', facility=facility, is_favorite=is_favorite)


@app.route('/compare')
def compare():
    # Получаем ID выбранных объектов из URL
    ids = request.args.getlist('ids')

    # Преобразуем строки в числа
    int_ids = [int(id) for id in ids if id.isdigit()]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Если мы на странице выбора и ID меньше 2
    if len(int_ids) < 2 and session.get('original_ids'):
        original_ids = session['original_ids']
        cur.execute("SELECT * FROM sport_facilities WHERE id = ANY(%s)", (original_ids,))
        original_facilities = cur.fetchall()
        cur.close()
        conn.close()
        flash('❌ Выберите хотя бы 2 объекта для сравнения', 'error')
        return render_template('select_compare.html', facilities=original_facilities)

    # Получаем данные по каждому ID
    facilities = []
    for id in int_ids:
        cur.execute("SELECT * FROM sport_facilities WHERE id = %s", (id,))
        facility = cur.fetchone()
        if facility:
            # Обрабатываем данные
            if facility['working_hours']:
                hours = facility['working_hours'].replace('DayWeek:', '').replace('WorkHours:', '')
                lines = hours.split('\n')
                clean_lines = [line.strip() for line in lines if line.strip()]
                facility['working_hours'] = '<br>'.join(clean_lines)

            if facility['phone']:
                phone = facility['phone'].replace('PublicPhone:', '').strip()
                if phone.startswith('('):
                    facility['phone'] = '+7 ' + phone
                else:
                    facility['phone'] = '+7 ' + phone

            if facility['email']:
                facility['email'] = facility['email'].replace('Email:', '').strip()

            facilities.append(facility)

    # Если меньше 2 - ошибка
    if len(facilities) < 2:
        flash('❌ Выберите хотя бы 2 объекта для сравнения', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('index'))

    # Если больше 3 - показываем страницу выбора и сохраняем исходные ID
    if len(facilities) > 3:
        session['original_ids'] = int_ids
        cur.close()
        conn.close()
        return render_template('select_compare.html', facilities=facilities)

    # Очищаем сессию если все хорошо
    session.pop('original_ids', None)
    cur.close()
    conn.close()

    # Если 2-3 - показываем сравнение
    return render_template('compare.html', facilities=facilities)

if __name__ == '__main__':
    app.run(debug=True)