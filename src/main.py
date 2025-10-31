import os
import sys
import threading
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from routes.user import user_bp
from routes.deals import deals_bp
from routes.payments import payments_bp
from routes.monitoring import monitoring_bp, set_payment_monitor
from routes.disputes import disputes_bp, set_dispute_manager
from telegram_bot import OTCBot
from services.payment_monitor import PaymentMonitor
from services.dispute_manager import DisputeManager

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'
CORS(app)

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(deals_bp, url_prefix='/api')
app.register_blueprint(payments_bp, url_prefix='/api')
app.register_blueprint(monitoring_bp, url_prefix='/api')
app.register_blueprint(disputes_bp, url_prefix='/api')

# إعداد قاعدة البيانات
db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database')
os.makedirs(db_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(db_dir, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# متغير البوت العام
bot_instance = None

# API endpoints للصفقات
@app.route('/api/deals', methods=['GET'])
def get_deals():
    """الحصول على جميع الصفقات"""
    from models.deal import Deal
    deals = Deal.query.all()
    return jsonify([deal.to_dict() for deal in deals])

@app.route('/api/deals/<deal_id>', methods=['GET'])
def get_deal(deal_id):
    """الحصول على صفقة محددة"""
    from models.deal import Deal
    deal = Deal.query.get_or_404(deal_id)
    return jsonify(deal.to_dict())

@app.route('/api/deals/<deal_id>/status', methods=['PUT'])
def update_deal_status(deal_id):
    """تحديث حالة الصفقة"""
    from models.deal import Deal
    deal = Deal.query.get_or_404(deal_id)
    data = request.get_json()
    
    if 'status' in data:
        deal.status = data['status']
        if 'buyer_id' in data:
            deal.buyer_id = data['buyer_id']
        if 'payment_id' in data:
            deal.payment_id = data['payment_id']
        
        db.session.commit()
        return jsonify(deal.to_dict())
    
    return jsonify({'error': 'Status is required'}), 400

@app.route('/api/users', methods=['GET'])
def get_users():
    """الحصول على جميع المستخدمين"""
    from models.telegram_user import TelegramUser
    users = TelegramUser.query.all()
    return jsonify([user.to_dict() for user in users])

# إعداد البوت
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

def start_bot():
    """تشغيل البوت في thread منفصل"""
    global bot_instance
    if BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE':
        bot_instance = OTCBot(BOT_TOKEN, app)
        
        # إنشاء مراقب المدفوعات
        payment_monitor = PaymentMonitor(app, bot_instance)
        set_payment_monitor(payment_monitor)
        
        # إنشاء مدير النزاعات
        dispute_manager = DisputeManager(app, bot_instance)
        set_dispute_manager(dispute_manager)
        
        # إعداد معالجات النزاعات في البوت
        bot_instance.setup_dispute_handlers()
        
        # تشغيل مراقب المدفوعات في الخلفية
        import asyncio
        
        async def start_monitoring():
            await payment_monitor.start_monitoring()
        
        # تشغيل المراقب في thread منفصل
        def run_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_monitoring())
        
        monitor_thread = threading.Thread(target=run_monitor, daemon=True)
        monitor_thread.start()
        
        # تشغيل البوت
        bot_instance.run()
    else:
        print("تحذير: لم يتم تعيين توكن البوت. البوت لن يعمل.")

# تشغيل البوت في thread منفصل
if BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE':
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    if '--init-db' in sys.argv:
        with app.app_context():
            print("Creating database tables...")
            db.create_all()
            print("Database tables created successfully!")
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)

