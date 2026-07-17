# Батор Дугаров — фотогалерея

Премиальный адаптивный сайт-портфолио фотографа с отдельной защищённой панелью управления.

## Что внутри

- `frontend/` — React + TypeScript + Vite. Публичная галерея, фильтры, необычная журнальная сетка, полноэкранный просмотр с клавиатурной навигацией и адаптивная вёрстка.
- `backend/` — Flask API, SQLite, серверные сессии, CSRF-защита, ограничение попыток входа и CRUD для фотографий.
- `backend/data/photos.json` — отдельный seed-массив временных кадров Unsplash. Его можно заменить данными Telegram-бота или импортом из API.
- `frontend/src/data/photos.json` — тот же небольшой fallback для просмотра интерфейса, если backend временно недоступен; в обычной работе источник — `/api/photos`.
- `backend/uploads/` — локальные загруженные изображения. Папка не попадает в git.
- `backend/instance/portfolio.db` — SQLite-база, создаётся автоматически.

Блок «Обо мне» намеренно не добавлен. Публичный интерфейс содержит только первый экран, галерею, контакты и футер.

## Безопасность загрузок и EXIF

При выборе файла в админке он отправляется на backend в `/api/admin/photos/inspect`. Сервер проверяет фактический формат, размер и содержимое изображения через Pillow, читает камеру, объектив, дату, ISO, фокусное расстояние, выдержку, диафрагму и размеры, после чего показывает их в редакторе.

Перед сохранением изображение пере-кодируется без EXIF. Это удаляет GPS и прочие скрытые метаданные из публичного файла. GPS никогда не возвращается API и не отображается в интерфейсе. Любое EXIF-поле можно изменить или очистить вручную.

Админка использует:

- хэш пароля Werkzeug (пароль не хранится в исходниках);
- HttpOnly + SameSite-сессию Flask;
- CSRF-токен в заголовке `X-CSRF-Token` для всех изменяющих запросов;
- лимит неудачных входов в SQLite;
- проверку MIME/формата Pillow, расширения и максимального размера;
- CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy` и отключённую геолокацию браузера.

## Локальный запуск на Windows

Откройте PowerShell и выполните команды из корня `D:\ФОТО_САЙТ`.

Для frontend нужен Node.js 20.19+ и pnpm; для backend — Python 3.10+.

```powershell
cd D:\ФОТО_САЙТ
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Сгенерируйте хэш пароля и вставьте полученную строку в `ADMIN_PASSWORD_HASH` файла `.env`:

```powershell
.\.venv\Scripts\python.exe backend\scripts\generate_password_hash.py
```

В `.env` также укажите длинный случайный `SECRET_KEY`. Его можно получить так:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Запустите backend в первом окне:

```powershell
cd D:\ФОТО_САЙТ\backend
..\.venv\Scripts\python.exe -m flask --app wsgi:app run --host 127.0.0.1 --port 5000
```

Установите зависимости frontend и запустите Vite во втором окне:

```powershell
cd D:\ФОТО_САЙТ\frontend
pnpm install
pnpm dev
```

Откройте `http://localhost:5173`. Панель находится по адресу `http://localhost:5173/admin`.

Для production-сборки:

```powershell
cd D:\ФОТО_САЙТ\frontend
pnpm build
```

После сборки Flask/Gunicorn может обслуживать `frontend/dist` напрямую. В режиме разработки Vite проксирует `/api` и `/uploads` на `127.0.0.1:5000`.

## Деплой на Ubuntu VPS: Nginx + Gunicorn

Ниже предполагается, что проект размещён в `/var/www/bator-dugarov`.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx
sudo mkdir -p /var/www/bator-dugarov
sudo chown -R "$USER":"$USER" /var/www/bator-dugarov
cd /var/www/bator-dugarov

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
python backend/scripts/generate_password_hash.py
```

Вставьте хэш в `.env`, задайте уникальный `SECRET_KEY`, а перед HTTPS оставьте `SESSION_COOKIE_SECURE=false`. После установки сертификата переключите его на `true`.

Установите Node.js 20.19+ и pnpm любым удобным способом, затем соберите клиент:

```bash
pnpm --dir frontend install
pnpm --dir frontend build
mkdir -p backend/uploads backend/instance/staging
```

Создайте `/etc/systemd/system/bator-dugarov.service`:

```ini
[Unit]
Description=Bator Dugarov photo portfolio API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/bator-dugarov
EnvironmentFile=/var/www/bator-dugarov/.env
ExecStart=/var/www/bator-dugarov/.venv/bin/gunicorn --chdir /var/www/bator-dugarov/backend --workers 2 --bind 127.0.0.1:8000 wsgi:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Перед запуском выдайте сервису права на runtime-папки:

```bash
sudo chown -R www-data:www-data backend/instance backend/uploads
sudo systemctl daemon-reload
sudo systemctl enable --now bator-dugarov
```

Создайте `/etc/nginx/sites-available/bator-dugarov` и замените `example.com` на домен:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    root /var/www/bator-dugarov/frontend/dist;
    index index.html;
    client_max_body_size 20M;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /uploads/ {
        alias /var/www/bator-dugarov/backend/uploads/;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Активируйте конфигурацию:

```bash
sudo ln -s /etc/nginx/sites-available/bator-dugarov /etc/nginx/sites-enabled/bator-dugarov
sudo nginx -t
sudo systemctl reload nginx
```

После подключения HTTPS через Certbot установите в `.env`:

```dotenv
SESSION_COOKIE_SECURE=true
TRUST_PROXY=true
```

После изменения `.env`, кода или seed-данных перезапустите сервис:

```bash
sudo systemctl restart bator-dugarov
```

## Проверка проекта

```powershell
cd D:\ФОТО_САЙТ
.\.venv\Scripts\python.exe -m pytest -q backend\tests
cd frontend
pnpm typecheck
pnpm build
```
