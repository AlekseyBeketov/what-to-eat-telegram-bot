# Deployment на Ubuntu/Debian с systemd

Инструкция рассчитана на чистый или уже подготовленный Ubuntu/Debian-сервер с `sudo`.
Если вы подключились как `root` (в prompt виден путь `~`, то есть `/root`), все
команды с `sudo` также выполняются, но отдельный `sudo` технически не нужен.
Бот работает через Telegram long polling, поэтому входящий порт, домен, reverse proxy,
Docker и внешняя база данных не нужны. Серверу нужен исходящий HTTPS-доступ к Telegram.

## Быстрый deploy нового изменения

### Локально

```bash
cd /Users/alexbeketov/what-to-eat-bot
git diff --cached --check
git commit -m "Описание изменения"
git push origin main
```

### На сервере

```bash
ssh root@6253761-nl646310
cd /root/what-to-eat-telegram-bot

sudo systemctl stop what-to-eat-bot.service

# Backup SQLite перед обновлением
DB=/root/what-to-eat-telegram-bot/data/what-to-eat.sqlite3
BACKUP=/var/backups/what-to-eat-bot/what-to-eat-$(date +%Y%m%d-%H%M%S).sqlite3
sudo install -d -m 750 -o root -g root /var/backups/what-to-eat-bot
sudo sqlite3 "$DB" ".backup '$BACKUP'"
sudo test -s "$BACKUP"

git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .

# Миграции БД
sudo systemd-run --wait --pipe --collect \
  --unit=what-to-eat-bot-migrate \
  --property=User=root \
  --property=WorkingDirectory=/root/what-to-eat-telegram-bot \
  --property=EnvironmentFile=/root/what-to-eat-telegram-bot/.env \
  /root/what-to-eat-telegram-bot/.venv/bin/python -m what_to_eat_bot.migrate

sudo systemctl start what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
sudo journalctl -u what-to-eat-bot.service -n 100 --no-pager
```

Если `git pull --ff-only` сообщает о локальных изменениях — остановись и не используй
`reset --hard` без проверки. При проблемах сначала останови unit, затем восстанови SQLite
из backup и верни предыдущую revision приложения.

## 0. Что подготовить до подключения

Нужно:

- SSH-доступ к серверу с пользователем, у которого есть `sudo` (или доступ `root`);
- Ubuntu/Debian и Python 3.12+;
- token бота из `@BotFather`;
- Git-доступ к репозиторию.

Проверьте сервер:

```bash
cat /etc/os-release
python3 --version
uname -m
sudo -v
```

Если `python3 --version` ниже `3.12`, остановитесь на этом шаге и установите Python
3.12 или 3.13 способом, принятым в вашей инфраструктуре. Не подменяйте системный
Python случайным бинарником: после установки повторно проверьте `python3 --version`.

## 1. Clone репозитория

Рекомендуемый путь приложения — `/root/what-to-eat-telegram-bot`. На чистом сервере:

```bash
sudo apt update
sudo apt install -y git
sudo install -d -m 755 -o "$USER" -g "$(id -gn)" /opt
git clone --branch main --single-branch \
  git@github.com:AlekseyBeketov/what-to-eat-telegram-bot.git \
  /root/what-to-eat-telegram-bot
```

Clone выполняется от вашего login/deploy-пользователя, а не от отдельного systemd-
пользователя: у него не будет GitHub SSH key. В вашем случае это может быть `root`,
если ключ находится в `/root/.ssh` и уже используется для GitHub.

Приложение размещается в `/root/what-to-eat-telegram-bot`, как и соседний
`TranscribeTelegramBot`. Текущий unit использует `ProtectHome=no` и запускается от
`root`, поэтому доступ к коду и локальному `.env` сохраняется.

Если SSH key не настроен, а repository публичный, можно использовать HTTPS:

```bash
git clone --branch main --single-branch \
  https://github.com/AlekseyBeketov/what-to-eat-telegram-bot.git \
  /root/what-to-eat-telegram-bot
```

Перед clone убедитесь, что `/root/what-to-eat-telegram-bot` ещё не существует. Не используйте
`rm -rf` для исправления ошибки пути — сначала проверьте содержимое каталога.

Ниже используется:

- repository: `/root/what-to-eat-telegram-bot`;
- service user/group: `root`;
- environment file: `/root/what-to-eat-telegram-bot/.env`;
- SQLite: `/root/what-to-eat-telegram-bot/data/what-to-eat.sqlite3`;
- unit: `what-to-eat-bot.service`.

Если repository находится в другом месте, согласованно измените `WorkingDirectory`, `ExecStart` и команды. systemd не разворачивает shell variables в этих полях.

## 2. System prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3 git
python3 --version
```

Нужен Python 3.12+. Если версия distribution старше, установите поддерживаемый Python 3.12/3.13 из доверенного для вашей инфраструктуры repository и используйте его далее.

## 3. Пользователь сервиса

Как и соседний `transcribe-bot`, этот unit запускается от `root` и работает из
`/root`. Это менее безопасно, чем отдельный service user, но соответствует
текущей operational-схеме сервера.

## 4. Virtual environment и dependencies

Эти команды выполняйте от того же SSH-пользователя, который сделал `git clone`.

```bash
cd /root/what-to-eat-telegram-bot
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
```

## 5. Локальный `.env`

```bash
cd /root/what-to-eat-telegram-bot
cp .env.example .env
chmod 600 .env
nano .env
```

Содержимое без кавычек вокруг значений:

```dotenv
BOT_TOKEN=token_from_botfather
DATABASE_PATH=/root/what-to-eat-telegram-bot/data/what-to-eat.sqlite3
LOG_LEVEL=INFO
INVITE_TTL_HOURS=72
BOT_USERNAME=bot_username_without_at
```

Не вставляйте token в unit, command history или repository. Проверка permissions:

```bash
sudo stat -c '%a %U %G %n' /root/what-to-eat-telegram-bot/.env
```

Ожидается `600 root root`.

## 6. Writable data directory

```bash
sudo install -d -m 750 -o root -g root /root/what-to-eat-telegram-bot/data
```

## 7. Migrations

```bash
sudo systemd-run --wait --pipe --collect \
  --unit=what-to-eat-bot-migrate \
  --property=User=root \
  --property=WorkingDirectory=/root/what-to-eat-telegram-bot \
  --property=EnvironmentFile=/root/what-to-eat-telegram-bot/.env \
  /root/what-to-eat-telegram-bot/.venv/bin/python -m what_to_eat_bot.migrate
sudo test -w /root/what-to-eat-telegram-bot/data
```

Migration запускается как transient oneshot unit с защищённым EnvironmentFile; token не вставляется в command line.

## 8. Установка unit

Проверьте paths в template, затем:

```bash
sudo install -m 644 deploy/what-to-eat-bot.service /etc/systemd/system/what-to-eat-bot.service
sudo systemctl daemon-reload
```

Если доступно:

```bash
sudo systemd-analyze verify /etc/systemd/system/what-to-eat-bot.service
```

## 9. Enable и start

Перед запуском убедитесь, что другой process с тем же Telegram token не выполняет polling.

```bash
sudo systemctl enable --now what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
```

## 10. Logs и диагностика

```bash
sudo journalctl -u what-to-eat-bot.service -n 200 --no-pager
sudo journalctl -u what-to-eat-bot.service -f
```

JSON logs не содержат token.

## 11. Управление

```bash
sudo systemctl restart what-to-eat-bot.service
sudo systemctl stop what-to-eat-bot.service
sudo systemctl start what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
```

Не используйте `pkill python`: это может остановить посторонние services.

## 12. Backup SQLite перед update

```bash
sudo install -d -m 750 -o root -g root /var/backups/what-to-eat-bot
DB=/root/what-to-eat-telegram-bot/data/what-to-eat.sqlite3
BACKUP=/var/backups/what-to-eat-bot/what-to-eat-$(date +%Y%m%d-%H%M%S).sqlite3
sudo systemctl stop what-to-eat-bot.service
sudo sqlite3 "$DB" ".backup '$BACKUP'"
sudo test -s "$BACKUP"
```

## 13. Update после `git pull`

```bash
cd /root/what-to-eat-telegram-bot
git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .
sudo systemd-run --wait --pipe --collect \
  --unit=what-to-eat-bot-migrate \
  --property=User=root \
  --property=WorkingDirectory=/root/what-to-eat-telegram-bot \
  --property=EnvironmentFile=/root/what-to-eat-telegram-bot/.env \
  /root/what-to-eat-telegram-bot/.venv/bin/python -m what_to_eat_bot.migrate
sudo systemctl start what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
sudo journalctl -u what-to-eat-bot.service -n 100 --no-pager
```

При ошибке остановите service, верните предыдущую application revision и восстановите SQLite из проверенного backup:

```bash
sudo systemctl stop what-to-eat-bot.service
sudo cp /var/backups/what-to-eat-bot/CHOSEN_BACKUP.sqlite3   /root/what-to-eat-telegram-bot/data/what-to-eat.sqlite3
sudo systemctl start what-to-eat-bot.service
```

## 14. Типичные ошибки

### `status=203/EXEC`

`ExecStart` или `.venv` path неверен. Проверьте:

```bash
sudo test -x /root/what-to-eat-telegram-bot/.venv/bin/python
```

### `Missing or invalid environment variable: BOT_TOKEN`

Проверьте имя variable и permissions EnvironmentFile, не печатая token:

```bash
sudo test -r /root/what-to-eat-telegram-bot/.env
```

### `readonly database` / `unable to open database file`

```bash
sudo chown -R root:root /root/what-to-eat-telegram-bot/data
sudo chmod 750 /root/what-to-eat-telegram-bot/data
```

### Telegram `getUpdates` conflict

Другой process использует тот же token. Остановите только известный unit/process. Проверьте unit:

```bash
sudo systemctl status what-to-eat-bot.service --no-pager
sudo systemctl show what-to-eat-bot.service -p MainPID
```

### Restart loop

```bash
sudo systemctl reset-failed what-to-eat-bot.service
sudo journalctl -u what-to-eat-bot.service -b --no-pager
```

Исправьте configuration/permissions, затем выполните `sudo systemctl restart what-to-eat-bot.service`.
