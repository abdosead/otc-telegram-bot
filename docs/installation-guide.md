# دليل التثبيت والإعداد الشامل

## مقدمة

يوفر هذا الدليل تعليمات مفصلة خطوة بخطوة لتثبيت وإعداد بوت OTC للوساطة الآمنة. سواء كنت مطوراً مبتدئاً أو خبيراً، ستجد في هذا الدليل كل ما تحتاجه لتشغيل البوت بنجاح.

## متطلبات النظام

### متطلبات الأجهزة الدنيا

للتشغيل الأساسي (أقل من 100 مستخدم):

- معالج: 1 CPU Core

- ذاكرة الوصول العشوائي: 512 MB

- مساحة التخزين: 1 GB

- اتصال إنترنت مستقر

للتشغيل المتوسط (100-1000 مستخدم):

- معالج: 2 CPU Cores

- ذاكرة الوصول العشوائي: 2 GB

- مساحة التخزين: 5 GB

- اتصال إنترنت عالي السرعة

للتشغيل المكثف (أكثر من 1000 مستخدم):

- معالج: 4+ CPU Cores

- ذاكرة الوصول العشوائي: 4+ GB

- مساحة التخزين: 20+ GB

- اتصال إنترنت مخصص

### متطلبات البرمجيات

#### نظم التشغيل المدعومة

- Ubuntu 20.04 LTS أو أحدث (مُوصى به)

- CentOS 8 أو أحدث

- Debian 11 أو أحدث

- Windows 10/11 (للتطوير فقط)

- macOS 12 أو أحدث (للتطوير فقط)

#### إصدارات Python المدعومة

- Python 3.11.0 أو أحدث (مُوصى به)

- Python 3.10.x (مدعوم)

- Python 3.9.x (مدعوم مع قيود)

#### قواعد البيانات المدعومة

- SQLite 3.35+ (للتطوير والاستخدام الخفيف)

- PostgreSQL 13+ (مُوصى به للإنتاج)

- MySQL 8.0+ (مدعوم)

## التثبيت على Ubuntu/Debian

### الخطوة 1: تحديث النظام

```bash
# تحديث قائمة الحزم
sudo apt update

# ترقية الحزم المثبتة
sudo apt upgrade -y

# تثبيت الأدوات الأساسية
sudo apt install -y curl wget git build-essential
```

### الخطوة 2: تثبيت Python 3.11

```bash
# إضافة مستودع deadsnakes للحصول على أحدث إصدارات Python
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# تثبيت Python 3.11 والأدوات المساعدة
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# التحقق من التثبيت
python3.11 --version
```

### الخطوة 3: تثبيت قاعدة البيانات (PostgreSQL)

```bash
# تثبيت PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# بدء خدمة PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# إنشاء قاعدة بيانات ومستخدم للبوت
sudo -u postgres psql << EOF
CREATE DATABASE otc_bot;
CREATE USER otc_user WITH PASSWORD 'Abdo2468#@';
GRANT ALL PRIVILEGES ON DATABASE otc_bot TO otc_user;
ALTER USER otc_user CREATEDB;
\q
EOF
```

### الخطوة 4: تحميل وإعداد المشروع

```bash
# إنشاء مجلد للمشروع
sudo mkdir -p /opt/otc-bot
sudo chown $USER:$USER /opt/otc-bot
cd /opt/otc-bot

# تحميل المشروع (استبدل الرابط بالرابط الفعلي)
git clone https://github.com/abdosead/dezzen.git .

# إنشاء البيئة الافتراضية
python3.11 -m venv venv

# تفعيل البيئة الافتراضية
source venv/bin/activate

# ترقية pip
pip install --upgrade pip

# تثبيت المتطلبات
pip install -r requirements.txt
```

### الخطوة 5: إعداد متغيرات البيئة

```bash
# نسخ ملف الإعدادات المثال
cp .env.example .env

# تحرير ملف الإعدادات
nano .env
```

أضف المعلومات التالية في ملف `.env`:

```
# إعدادات البوت الأساسية
BOT_TOKEN=your_telegram_bot_token_here
SECRET_KEY=generate_a_secure_random_key_here

# إعدادات قاعدة البيانات
DATABASE_URL=postgresql://otc_user:secure_password_here@localhost/otc_bot

# إعدادات CCPayments
CCPAYMENT_APP_ID=your_ccpayment_app_id
CCPAYMENT_APP_SECRET=your_ccpayment_app_secret
CCPAYMENT_API_URL=https://ccpayment.com/ccpayment/v2

# إعدادات الأمان
ADMIN_USER_IDS=123456789,987654321
SUPPORT_BOT_USERNAME=your_support_bot

# إعدادات المراقبة
PAYMENT_CHECK_INTERVAL=30
LOG_LEVEL=INFO

# إعدادات العمولة
COMMISSION_RATE=0.05
```

### الخطوة 6: تهيئة قاعدة البيانات

```bash
# تشغيل البوت لإنشاء الجداول
python src/main.py --init-db

# أو تشغيل سكريبت التهيئة المنفصل
python scripts/init_database.py
```

### الخطوة 7: إعداد خدمة systemd

```bash
# إنشاء ملف الخدمة
sudo nano /etc/systemd/system/otc-bot.service
```

أضف المحتوى التالي:

```
[Unit]
Description=OTC Trading Bot
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=otc-bot
Group=otc-bot
WorkingDirectory=/opt/otc-bot
Environment=PATH=/opt/otc-bot/venv/bin
ExecStart=/opt/otc-bot/venv/bin/python src/main.py
Restart=always
RestartSec=10

# إعدادات الأمان
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/otc-bot

[Install]
WantedBy=multi-user.target
```

```bash
# إنشاء مستخدم مخصص للبوت
sudo useradd -r -s /bin/false otc-bot
sudo chown -R otc-bot:otc-bot /opt/otc-bot

# تفعيل وبدء الخدمة
sudo systemctl daemon-reload
sudo systemctl enable otc-bot
sudo systemctl start otc-bot

# التحقق من حالة الخدمة
sudo systemctl status otc-bot
```

## التثبيت على CentOS/RHEL

### الخطوة 1: تحديث النظام

```bash
# تحديث النظام
sudo dnf update -y

# تثبيت الأدوات الأساسية
sudo dnf install -y curl wget git gcc gcc-c++ make
```

### الخطوة 2: تثبيت Python 3.11

```bash
# تفعيل مستودع EPEL
sudo dnf install -y epel-release

# تثبيت Python 3.11
sudo dnf install -y python3.11 python3.11-pip python3.11-devel

# إنشاء رابط رمزي
sudo ln -sf /usr/bin/python3.11 /usr/local/bin/python3
```

### الخطوة 3: تثبيت PostgreSQL

```bash
# تثبيت PostgreSQL
sudo dnf install -y postgresql postgresql-server postgresql-contrib

# تهيئة قاعدة البيانات
sudo postgresql-setup --initdb

# بدء الخدمة
sudo systemctl start postgresql
sudo systemctl enable postgresql

# إعداد المصادقة
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = 'localhost'/" /var/lib/pgsql/data/postgresql.conf
sudo sed -i "s/ident/md5/g" /var/lib/pgsql/data/pg_hba.conf

# إعادة تشغيل PostgreSQL
sudo systemctl restart postgresql
```

باقي الخطوات مشابهة لتوزيعة Ubuntu مع تعديل أوامر إدارة الحزم.

## التثبيت على Windows (للتطوير)

### الخطوة 1: تثبيت Python

1. قم بتحميل Python 3.11 من [python.org](https://python.org)

1. شغل المثبت واختر "Add Python to PATH"

1. اختر "Install for all users" إذا أردت

### الخطوة 2: تثبيت Git

1. قم بتحميل Git من [git-scm.com](https://git-scm.com)

1. شغل المثبت واتبع التعليمات الافتراضية

### الخطوة 3: إعداد المشروع

```
# فتح Command Prompt كمدير
# إنشاء مجلد المشروع
mkdir C:\otc-bot
cd C:\otc-bot

# تحميل المشروع
git clone https://github.com/your-username/otc-bot.git .

# إنشاء البيئة الافتراضية
python -m venv venv

# تفعيل البيئة الافتراضية
venv\Scripts\activate

# تثبيت المتطلبات
pip install -r requirements.txt
```

### الخطوة 4: إعداد قاعدة البيانات

للتطوير على Windows، يُنصح باستخدام SQLite:

```
# نسخ ملف الإعدادات
copy .env.example .env

# تحرير الملف باستخدام Notepad
notepad .env
```

أضف في ملف `.env`:

```
DATABASE_URL=sqlite:///database/app.db
BOT_TOKEN=your_bot_token_here
# باقي الإعدادات...
```

## إعداد Nginx كـ Reverse Proxy

### تثبيت Nginx

```bash
# Ubuntu/Debian
sudo apt install -y nginx

# CentOS/RHEL
sudo dnf install -y nginx
```

### إعداد التكوين

```bash
# إنشاء ملف التكوين
sudo nano /etc/nginx/sites-available/otc-bot
```

أضف المحتوى التالي:

```
server {
    listen 80;
    server_name your-domain.com;

    # إعادة توجيه HTTP إلى HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # إعدادات SSL
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # إعدادات الأمان
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Proxy للتطبيق
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # إعدادات WebSocket (إذا لزم الأمر)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # إعدادات الملفات الثابتة
    location /static/ {
        alias /opt/otc-bot/src/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# تفعيل التكوين
sudo ln -s /etc/nginx/sites-available/otc-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## إعداد SSL مع Let's Encrypt

```bash
# تثبيت Certbot
sudo apt install -y certbot python3-certbot-nginx

# الحصول على شهادة SSL
sudo certbot --nginx -d your-domain.com

# إعداد التجديد التلقائي
sudo crontab -e
# أضف السطر التالي:
# 0 12 * * * /usr/bin/certbot renew --quiet
```

## إعداد المراقبة والسجلات

### إعداد Logrotate

```bash
# إنشاء ملف تكوين logrotate
sudo nano /etc/logrotate.d/otc-bot
```

```
/opt/otc-bot/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 otc-bot otc-bot
    postrotate
        systemctl reload otc-bot
    endscript
}
```

### إعداد مراقبة النظام

```bash
# تثبيت htop لمراقبة الموارد
sudo apt install -y htop

# تثبيت netstat لمراقبة الشبكة
sudo apt install -y net-tools

# إنشاء سكريبت مراقبة
nano /opt/otc-bot/scripts/monitor.sh
```

```bash
#!/bin/bash
# سكريبت مراقبة بسيط للبوت

LOG_FILE="/opt/otc-bot/logs/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# فحص حالة الخدمة
if systemctl is-active --quiet otc-bot; then
    echo "[$DATE] OTC Bot is running" >> $LOG_FILE
else
    echo "[$DATE] ERROR: OTC Bot is not running!" >> $LOG_FILE
    # إعادة تشغيل الخدمة
    systemctl restart otc-bot
fi

# فحص استخدام الذاكرة
MEMORY_USAGE=$(ps -o pid,ppid,cmd,%mem,%cpu --sort=-%mem -C python | head -n 2 | tail -n 1 | awk '{print $4}')
echo "[$DATE] Memory usage: ${MEMORY_USAGE}%" >> $LOG_FILE

# فحص مساحة القرص
DISK_USAGE=$(df -h /opt/otc-bot | tail -n 1 | awk '{print $5}')
echo "[$DATE] Disk usage: $DISK_USAGE" >> $LOG_FILE
```

```bash
# جعل السكريبت قابل للتنفيذ
chmod +x /opt/otc-bot/scripts/monitor.sh

# إضافة مهمة cron لتشغيل المراقبة كل 5 دقائق
sudo crontab -e
# أضف السطر التالي:
# */5 * * * * /opt/otc-bot/scripts/monitor.sh
```

## النسخ الاحتياطي

### إعداد نسخ احتياطي لقاعدة البيانات

```bash
# إنشاء سكريبت النسخ الاحتياطي
nano /opt/otc-bot/scripts/backup.sh
```

```bash
#!/bin/bash
# سكريبت النسخ الاحتياطي

BACKUP_DIR="/opt/otc-bot/backups"
DATE=$(date '+%Y%m%d_%H%M%S')
DB_NAME="otc_bot"
DB_USER="otc_user"

# إنشاء مجلد النسخ الاحتياطي
mkdir -p $BACKUP_DIR

# نسخ احتياطي لقاعدة البيانات
pg_dump -U $DB_USER -h localhost $DB_NAME > $BACKUP_DIR/db_backup_$DATE.sql

# نسخ احتياطي للملفات المرفوعة
tar -czf $BACKUP_DIR/files_backup_$DATE.tar.gz /opt/otc-bot/uploads/

# حذف النسخ الاحتياطية الأقدم من 30 يوم
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
# جعل السكريبت قابل للتنفيذ
chmod +x /opt/otc-bot/scripts/backup.sh

# إضافة مهمة cron للنسخ الاحتياطي اليومي
sudo crontab -e
# أضف السطر التالي:
# 0 2 * * * /opt/otc-bot/scripts/backup.sh
```

## اختبار التثبيت

### اختبار الاتصال بقاعدة البيانات

```bash
cd /opt/otc-bot
source venv/bin/activate
python -c "
from src.models.telegram_user import TelegramUser, db
from src.main import app
with app.app_context():
    try:
        db.create_all()
        print('✅ Database connection successful')
    except Exception as e:
        print(f'❌ Database error: {e}')
"
```

### اختبار البوت

```bash
# تشغيل البوت في وضع الاختبار
python src/main.py --test

# أو تشغيل الاختبارات الآلية
python test_bot.py
```

### اختبار API

```bash
# اختبار صحة النظام
curl http://localhost:5000/api/monitoring/health

# اختبار إحصائيات النظام
curl http://localhost:5000/api/monitoring/stats
```

## استكشاف مشاكل التثبيت

### مشاكل Python

**خطأ: python3.11: command not found**

```bash
# تأكد من تثبيت Python 3.11
which python3.11
# إذا لم يكن مثبتاً، أعد تثبيته
sudo apt install -y python3.11
```

**خطأ: No module named 'venv'**

```bash
# تثبيت حزمة venv
sudo apt install -y python3.11-venv
```

### مشاكل قاعدة البيانات

**خطأ: could not connect to server**

```bash
# تحقق من حالة PostgreSQL
sudo systemctl status postgresql

# إعادة تشغيل الخدمة
sudo systemctl restart postgresql

# فحص السجلات
sudo journalctl -u postgresql
```

**خطأ: authentication failed**

```bash
# إعادة تعيين كلمة مرور المستخدم
sudo -u postgres psql
ALTER USER otc_user WITH PASSWORD 'new_password';
\q
```

### مشاكل الأذونات

**خطأ: Permission denied**

```bash
# تصحيح أذونات الملفات
sudo chown -R otc-bot:otc-bot /opt/otc-bot
sudo chmod -R 755 /opt/otc-bot
sudo chmod 600 /opt/otc-bot/.env
```

### مشاكل الشبكة

**خطأ: Connection refused**

```bash
# فحص المنافذ المفتوحة
sudo netstat -tlnp | grep :5000

# فحص جدار الحماية
sudo ufw status
sudo ufw allow 5000
```

## الخطوات التالية

بعد إتمام التثبيت بنجاح:

1. **إعداد البوت في التليجرام**: راجع دليل إعداد البوت

1. **تكوين CCPayments**: راجع دليل إعداد المدفوعات

1. **اختبار النظام**: قم بإجراء صفقة تجريبية

1. **مراقبة الأداء**: راقب السجلات والإحصائيات

1. **النسخ الاحتياطي**: تأكد من عمل النسخ الاحتياطي التلقائي

للحصول على مساعدة إضافية، راجع باقي الوثائق في مجلد `docs/` أو تواصل مع فريق الدعم.

---

**ملاحظة**: هذا الدليل يغطي التثبيت الأساسي. للبيئات الإنتاجية الكبيرة، قد تحتاج لإعدادات إضافية مثل Load Balancing وClustering.

