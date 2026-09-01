Репозиторий уже клонирован на сервер.

# Deployment на Ubuntu/Debian с systemd

Ниже используется:

- repository: `/opt/what-to-eat-bot`;
- service user/group: `whattoeat`;
- environment file: `/etc/what-to-eat-bot.env`;
- SQLite: `/var/lib/what-to-eat-bot/what-to-eat.sqlite3`;
- unit: `what-to-eat-bot.service`.

Если repository находится в другом месте, согласованно измените `WorkingDirectory`, `ExecStart` и команды. systemd не разворачивает shell variables в этих полях.

## 1. System prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3 git
python3 --version
```

Нужен Python 3.12+. Если версия distribution старше, установите поддерживаемый Python 3.12/3.13 из доверенного для вашей инфраструктуры repository и используйте его далее.

## 2. Непривилегированный пользователь

```bash
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin whattoeat || true
sudo chown -R whattoeat:whattoeat /opt/what-to-eat-bot
```

Service не запускается от root.

## 3. Virtual environment и dependencies

```bash
cd /opt/what-to-eat-bot
sudo -u whattoeat python3 -m venv .venv
sudo -u whattoeat .venv/bin/python -m pip install --upgrade pip
sudo -u whattoeat .venv/bin/python -m pip install -r requirements.txt
sudo -u whattoeat .venv/bin/python -m pip install -e .
```

## 4. Защищённый EnvironmentFile

```bash
sudo install -m 600 -o whattoeat -g whattoeat /dev/null /etc/what-to-eat-bot.env
sudoedit /etc/what-to-eat-bot.env
```

Содержимое без кавычек вокруг значений:

```dotenv
BOT_TOKEN=token_from_botfather
DATABASE_PATH=/var/lib/what-to-eat-bot/what-to-eat.sqlite3
LOG_LEVEL=INFO
INVITE_TTL_HOURS=72
BOT_USERNAME=bot_username_without_at
```

Не вставляйте token в unit, command history или repository. Проверка permissions:

```bash
sudo stat -c '%a %U %G %n' /etc/what-to-eat-bot.env
```

Ожидается `600 whattoeat whattoeat`.

## 5. Writable data directory

```bash
sudo install -d -m 750 -o whattoeat -g whattoeat /var/lib/what-to-eat-bot
```

## 6. Migrations

```bash
sudo systemd-run --wait --pipe --collect \
  --unit=what-to-eat-bot-migrate \
  --property=User=whattoeat \
  --property=WorkingDirectory=/opt/what-to-eat-bot \
  --property=EnvironmentFile=/etc/what-to-eat-bot.env \
  /opt/what-to-eat-bot/.venv/bin/python -m what_to_eat_bot.migrate
sudo -u whattoeat test -w /var/lib/what-to-eat-bot
```

Migration запускается как transient oneshot unit с защищённым EnvironmentFile; token не вставляется в command line.

## 7. Установка unit

Проверьте paths в template, затем:

```bash
sudo install -m 644 deploy/what-to-eat-bot.service /etc/systemd/system/what-to-eat-bot.service
sudo systemctl daemon-reload
```

Если доступно:

```bash
sudo systemd-analyze verify /etc/systemd/system/what-to-eat-bot.service
```

## 8. Enable и start

Перед запуском убедитесь, что другой process с тем же Telegram token не выполняет polling.

```bash
sudo systemctl enable --now what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
```

## 9. Logs и диагностика

```bash
sudo journalctl -u what-to-eat-bot.service -n 200 --no-pager
sudo journalctl -u what-to-eat-bot.service -f
```

JSON logs не содержат token.

## 10. Управление

```bash
sudo systemctl restart what-to-eat-bot.service
sudo systemctl stop what-to-eat-bot.service
sudo systemctl start what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
```

Не используйте `pkill python`: это может остановить посторонние services.

## 11. Backup SQLite перед update

```bash
sudo install -d -m 750 -o whattoeat -g whattoeat /var/backups/what-to-eat-bot
DB=/var/lib/what-to-eat-bot/what-to-eat.sqlite3
BACKUP=/var/backups/what-to-eat-bot/what-to-eat-$(date +%Y%m%d-%H%M%S).sqlite3
sudo systemctl stop what-to-eat-bot.service
sudo -u whattoeat sqlite3 "$DB" ".backup '$BACKUP'"
sudo -u whattoeat test -s "$BACKUP"
```

## 12. Update после `git pull`

```bash
cd /opt/what-to-eat-bot
sudo -u whattoeat git pull --ff-only
sudo -u whattoeat .venv/bin/python -m pip install -r requirements.txt
sudo -u whattoeat .venv/bin/python -m pip install -e .
sudo systemd-run --wait --pipe --collect \
  --unit=what-to-eat-bot-migrate \
  --property=User=whattoeat \
  --property=WorkingDirectory=/opt/what-to-eat-bot \
  --property=EnvironmentFile=/etc/what-to-eat-bot.env \
  /opt/what-to-eat-bot/.venv/bin/python -m what_to_eat_bot.migrate
sudo systemctl start what-to-eat-bot.service
sudo systemctl status what-to-eat-bot.service --no-pager
sudo journalctl -u what-to-eat-bot.service -n 100 --no-pager
```

При ошибке остановите service, верните предыдущую application revision и восстановите SQLite из проверенного backup:

```bash
sudo systemctl stop what-to-eat-bot.service
sudo -u whattoeat cp /var/backups/what-to-eat-bot/CHOSEN_BACKUP.sqlite3   /var/lib/what-to-eat-bot/what-to-eat.sqlite3
sudo systemctl start what-to-eat-bot.service
```

## 13. Типичные ошибки

### `status=203/EXEC`

`ExecStart` или `.venv` path неверен. Проверьте:

```bash
sudo -u whattoeat test -x /opt/what-to-eat-bot/.venv/bin/python
```

### `Missing or invalid environment variable: BOT_TOKEN`

Проверьте имя variable и permissions EnvironmentFile, не печатая token:

```bash
sudo -u whattoeat test -r /etc/what-to-eat-bot.env
```

### `readonly database` / `unable to open database file`

```bash
sudo chown -R whattoeat:whattoeat /var/lib/what-to-eat-bot
sudo chmod 750 /var/lib/what-to-eat-bot
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
