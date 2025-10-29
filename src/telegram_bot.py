import os
import sys
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask_sqlalchemy import SQLAlchemy
from models.telegram_user import TelegramUser, db as user_db
from models.deal import Deal, db as deal_db

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# إعداد قاعدة البيانات
DATABASE_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"

class OTCBot:
    def __init__(self, token, flask_app=None):
        self.token = token
        self.flask_app = flask_app
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        
    def setup_handlers(self):
        """إعداد معالجات الأوامر"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("create_deal", self.create_deal))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر /start"""
        user = update.effective_user
        
        # التحقق من وجود رابط صفقة في الأمر
        if context.args and context.args[0].startswith('deal_'):
            deal_id = context.args[0].replace('deal_', '')
            await self.show_deal_details(update, context, deal_id)
            return
        
        # حفظ أو تحديث بيانات المستخدم
        if self.flask_app:
            with self.flask_app.app_context():
                telegram_user = TelegramUser.query.filter_by(telegram_id=user.id).first()
                if not telegram_user:
                    telegram_user = TelegramUser(
                        telegram_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
                    user_db.session.add(telegram_user)
                    user_db.session.commit()
        
        # إنشاء لوحة التحكم الرئيسية
        keyboard = [
            [InlineKeyboardButton("🆕 إنشاء صفقة جديدة", callback_data="create_deal")],
            [InlineKeyboardButton("📋 صفقاتي", callback_data="my_deals")],
            [InlineKeyboardButton("💰 محفظتي", callback_data="wallet")],
            [InlineKeyboardButton("❓ المساعدة", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🔥 مرحباً بك في بوت OTC للوساطة الآمنة! 🔥

👋 أهلاً {user.first_name}!

هذا البوت يوفر خدمة وساطة آمنة للصفقات بين الأطراف مع ضمان الأمان والشفافية.

✨ الميزات الرئيسية:
• إنشاء صفقات آمنة مع عمولة 5%
• نظام دفع متكامل مع CCPayments
• حماية كاملة للمشترين والبائعين
• نظام إدارة النزاعات
• إشعارات فورية لجميع الأطراف

اختر من القائمة أدناه للبدء:
        """
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج أمر المساعدة"""
        help_text = """
📖 دليل استخدام بوت OTC للوساطة

🔸 كيفية إنشاء صفقة:
1. اضغط على "إنشاء صفقة جديدة"
2. أدخل عنوان الصفقة
3. أضف وصف مفصل
4. حدد السعر (سيتم إضافة 5% عمولة)
5. أرفق صور أو فيديوهات (اختياري)
6. احصل على رابط الصفقة لمشاركته

🔸 عملية الشراء:
1. المشتري يضغط على رابط الصفقة
2. يراجع التفاصيل والسعر النهائي
3. يوافق ويدفع للمحفظة المؤقتة
4. يضغط "تأكيد الدفع"
5. البوت يتحقق من الدفعة

🔸 إتمام الصفقة:
1. البائع يستلم إشعار بالدفع
2. يرسل المنتج/الخدمة للمشتري
3. المشتري يتأكد من الاستلام
4. يضغط "تحرير الأموال"
5. البائع يستلم المبلغ (بعد خصم العمولة)

🔸 في حالة النزاع:
• يمكن لأي طرف فتح نزاع
• فريق الدعم يتدخل للحل
• الأموال محمية حتى حل النزاع

للمساعدة الإضافية، تواصل مع الدعم الفني.
        """
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    
    async def create_deal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """بدء عملية إنشاء صفقة جديدة"""
        keyboard = [
            [InlineKeyboardButton("📝 بدء إنشاء الصفقة", callback_data="start_deal_creation")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = """
🆕 إنشاء صفقة جديدة

لإنشاء صفقة جديدة، ستحتاج إلى:
• عنوان واضح للصفقة
• وصف مفصل للمنتج/الخدمة
• السعر المطلوب (بالدولار)
• صور أو فيديوهات (اختياري)

ملاحظة: سيتم إضافة عمولة 5% على السعر المحدد.

اضغط "بدء إنشاء الصفقة" للمتابعة.
        """
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الأزرار"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "main_menu":
            await self.show_main_menu(query)
        elif query.data == "create_deal":
            await self.create_deal_callback(query, context)
        elif query.data == "start_deal_creation":
            await self.start_deal_creation(query, context)
        elif query.data == "my_deals":
            await self.show_my_deals(query, context)
        elif query.data == "wallet":
            await self.show_wallet(query, context)
        elif query.data == "help":
            await self.show_help(query)
        elif query.data.startswith("buy_deal_"):
            deal_id = query.data.replace("buy_deal_", "")
            await self.initiate_purchase(query, context, deal_id)
        elif query.data.startswith("confirm_payment_"):
            deal_id = query.data.replace("confirm_payment_", "")
            await self.confirm_payment_process(query, context, deal_id)
        elif query.data.startswith("release_funds_"):
            deal_id = query.data.replace("release_funds_", "")
            await self.release_funds_process(query, context, deal_id)
        elif query.data.startswith("dispute_"):
            deal_id = query.data.replace("dispute_", "")
            await self.create_dispute_process(query, context, deal_id)
        elif query.data.startswith("confirm_delivery_"):
            deal_id = query.data.replace("confirm_delivery_", "")
            await self.confirm_delivery_process(query, context, deal_id)
        elif query.data.startswith("pay_usdt_polygon_"):
            deal_id = query.data.replace("pay_usdt_polygon_", "")
            await self.process_payment(query, context, deal_id, "USDT", "POLYGON")
        elif query.data.startswith("pay_usdt_eth_"):
            deal_id = query.data.replace("pay_usdt_eth_", "")
            await self.process_payment(query, context, deal_id, "USDT", "ETH")
        elif query.data.startswith("pay_btc_"):
            deal_id = query.data.replace("pay_btc_", "")
            await self.process_payment(query, context, deal_id, "BTC", "BTC")
        elif query.data.startswith("pay_checkout_"):
            deal_id = query.data.replace("pay_checkout_", "")
            await self.create_checkout_page(query, context, deal_id)
    
    async def show_main_menu(self, query):
        """عرض القائمة الرئيسية"""
        keyboard = [
            [InlineKeyboardButton("🆕 إنشاء صفقة جديدة", callback_data="create_deal")],
            [InlineKeyboardButton("📋 صفقاتي", callback_data="my_deals")],
            [InlineKeyboardButton("💰 محفظتي", callback_data="wallet")],
            [InlineKeyboardButton("❓ المساعدة", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = """
🏠 القائمة الرئيسية

اختر الخدمة المطلوبة:
        """
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def create_deal_callback(self, query, context):
        """معالج إنشاء صفقة من الزر"""
        keyboard = [
            [InlineKeyboardButton("📝 بدء إنشاء الصفقة", callback_data="start_deal_creation")],
            [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = """
🆕 إنشاء صفقة جديدة

لإنشاء صفقة جديدة، ستحتاج إلى:
• عنوان واضح للصفقة
• وصف مفصل للمنتج/الخدمة
• السعر المطلوب (بالدولار)
• صور أو فيديوهات (اختياري)

ملاحظة: سيتم إضافة عمولة 5% على السعر المحدد.

اضغط "بدء إنشاء الصفقة" للمتابعة.
        """
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def start_deal_creation(self, query, context):
        """بدء عملية إنشاء الصفقة"""
        context.user_data['creating_deal'] = True
        context.user_data['deal_step'] = 'title'
        
        text = """
📝 إنشاء صفقة جديدة - الخطوة 1/4

أرسل عنوان الصفقة:
(مثال: بيع حساب إنستغرام - 10K متابع)
        """
        
        await query.edit_message_text(text)
    
    async def show_my_deals(self, query, context):
        """عرض صفقات المستخدم"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deals = Deal.query.filter_by(seller_id=user_id).all()
                
                if not deals:
                    text = "📋 لا توجد صفقات حالياً"
                else:
                    text = f"📋 صفقاتك ({len(deals)} صفقة):\n\n"
                    for deal in deals[:5]:  # عرض أول 5 صفقات
                        status_emoji = {
                            'pending': '⏳',
                            'paid': '💰',
                            'confirmed': '✅',
                            'completed': '🎉',
                            'disputed': '⚠️'
                        }.get(deal.status, '❓')
                        
                        text += f"{status_emoji} {deal.title}\n"
                        text += f"   السعر: ${deal.price} | الإجمالي: ${deal.total_price}\n"
                        text += f"   الحالة: {deal.status}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_wallet(self, query, context):
        """عرض معلومات المحفظة"""
        text = """
💰 محفظتي

هذه الميزة قيد التطوير...
سيتم إضافة:
• رصيد المحفظة
• تاريخ المعاملات
• إعدادات الدفع
        """
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    async def show_help(self, query):
        """عرض المساعدة"""
        help_text = """
📖 دليل استخدام بوت OTC للوساطة

🔸 كيفية إنشاء صفقة:
1. اضغط على "إنشاء صفقة جديدة"
2. أدخل عنوان الصفقة
3. أضف وصف مفصل
4. حدد السعر (سيتم إضافة 5% عمولة)
5. أرفق صور أو فيديوهات (اختياري)
6. احصل على رابط الصفقة لمشاركته

🔸 عملية الشراء:
1. المشتري يضغط على رابط الصفقة
2. يراجع التفاصيل والسعر النهائي
3. يوافق ويدفع للمحفظة المؤقتة
4. يضغط "تأكيد الدفع"
5. البوت يتحقق من الدفعة

🔸 إتمام الصفقة:
1. البائع يستلم إشعار بالدفع
2. يرسل المنتج/الخدمة للمشتري
3. المشتري يتأكد من الاستلام
4. يضغط "تحرير الأموال"
5. البائع يستلم المبلغ (بعد خصم العمولة)

للمساعدة الإضافية، تواصل مع الدعم الفني.
        """
        
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text, reply_markup=reply_markup)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الرسائل النصية"""
        if context.user_data.get('creating_deal'):
            await self.handle_deal_creation(update, context)
        else:
            # رسالة افتراضية
            keyboard = [[InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "استخدم الأزرار للتنقل في البوت، أو اكتب /start للعودة للقائمة الرئيسية.",
                reply_markup=reply_markup
            )
    
    async def handle_deal_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج إنشاء الصفقة خطوة بخطوة"""
        step = context.user_data.get('deal_step')
        user_id = update.effective_user.id
        
        if step == 'title':
            context.user_data['deal_title'] = update.message.text
            context.user_data['deal_step'] = 'description'
            
            await update.message.reply_text("""
📝 إنشاء صفقة جديدة - الخطوة 2/4

أرسل وصف مفصل للمنتج أو الخدمة:
(اشرح بالتفصيل ما تقدمه)
            """)
            
        elif step == 'description':
            context.user_data['deal_description'] = update.message.text
            context.user_data['deal_step'] = 'price'
            
            await update.message.reply_text("""
💰 إنشاء صفقة جديدة - الخطوة 3/4

أرسل السعر بالدولار (رقم فقط):
مثال: 100

ملاحظة: سيتم إضافة عمولة 5% على السعر المحدد.
            """)
            
        elif step == 'price':
            try:
                price = float(update.message.text)
                if price <= 0:
                    await update.message.reply_text("يرجى إدخال سعر صحيح أكبر من صفر.")
                    return
                
                commission = price * 0.05
                total_price = price + commission
                
                context.user_data['deal_price'] = price
                context.user_data['deal_commission'] = commission
                context.user_data['deal_total_price'] = total_price
                context.user_data['deal_step'] = 'media'
                
                await update.message.reply_text(f"""
📸 إنشاء صفقة جديدة - الخطوة 4/4

السعر الأساسي: ${price:.2f}
العمولة (5%): ${commission:.2f}
السعر الإجمالي: ${total_price:.2f}

أرسل صور أو فيديوهات للمنتج (اختياري)
أو اكتب "تخطي" للمتابعة بدون وسائط.
                """)
                
            except ValueError:
                await update.message.reply_text("يرجى إدخال رقم صحيح للسعر.")
                
        elif step == 'media':
            if update.message.text and update.message.text.lower() == 'تخطي':
                context.user_data['deal_media'] = None
            else:
                # معالجة الوسائط (الصور والفيديوهات)
                media_info = []
                if update.message.photo:
                    photo = update.message.photo[-1]  # أعلى جودة
                    media_info.append({
                        'type': 'photo',
                        'file_id': photo.file_id
                    })
                elif update.message.video:
                    media_info.append({
                        'type': 'video',
                        'file_id': update.message.video.file_id
                    })
                
                context.user_data['deal_media'] = json.dumps(media_info) if media_info else None
            
            # إنشاء الصفقة في قاعدة البيانات
            if self.flask_app:
                with self.flask_app.app_context():
                    deal = Deal(
                        seller_id=user_id,
                        title=context.user_data['deal_title'],
                        description=context.user_data['deal_description'],
                        price=context.user_data['deal_price'],
                        commission=context.user_data['deal_commission'],
                        total_price=context.user_data['deal_total_price'],
                        media_files=context.user_data.get('deal_media')
                    )
                    deal_db.session.add(deal)
                    deal_db.session.commit()
                    
                    deal_link = f"https://t.me/{context.bot.username}?start=deal_{deal.id}"
                    
                    keyboard = [
                        [InlineKeyboardButton("📋 عرض صفقاتي", callback_data="my_deals")],
                        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    success_text = f"""
✅ تم إنشاء الصفقة بنجاح!

📋 تفاصيل الصفقة:
العنوان: {deal.title}
السعر الأساسي: ${deal.price:.2f}
العمولة: ${deal.commission:.2f}
السعر الإجمالي: ${deal.total_price:.2f}

🔗 رابط الصفقة:
{deal_link}

شارك هذا الرابط مع المشتري لإتمام الصفقة.
                    """
                    
                    await update.message.reply_text(success_text, reply_markup=reply_markup)
            
            # مسح بيانات إنشاء الصفقة
            context.user_data.pop('creating_deal', None)
            context.user_data.pop('deal_step', None)
            for key in list(context.user_data.keys()):
                if key.startswith('deal_'):
                    context.user_data.pop(key, None)
    
    async def show_deal_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE, deal_id: str):
        """عرض تفاصيل الصفقة للمشتري المحتمل"""
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await update.message.reply_text("❌ الصفقة غير موجودة أو تم حذفها.")
                    return
                
                seller = TelegramUser.query.filter_by(telegram_id=deal.seller_id).first()
                seller_name = seller.first_name if seller else "غير معروف"
                
                # تحديد حالة الصفقة
                status_text = {
                    'pending': '⏳ في انتظار المشتري',
                    'paid': '💰 تم الدفع - في انتظار التأكيد',
                    'confirmed': '✅ تم التأكيد - في انتظار التحرير',
                    'completed': '🎉 مكتملة',
                    'disputed': '⚠️ نزاع مفتوح'
                }.get(deal.status, '❓ غير معروف')
                
                deal_text = f"""
📦 تفاصيل الصفقة

🏷️ العنوان: {deal.title}
📝 الوصف: {deal.description}

💰 السعر الأساسي: ${deal.price:.2f}
💵 العمولة (5%): ${deal.commission:.2f}
💳 السعر الإجمالي: ${deal.total_price:.2f}

👤 البائع: {seller_name}
📊 الحالة: {status_text}
📅 تاريخ الإنشاء: {deal.created_at.strftime('%Y-%m-%d %H:%M') if deal.created_at else 'غير محدد'}
                """
                
                keyboard = []
                user_id = update.effective_user.id
                
                # إذا كان المستخدم هو البائع
                if user_id == deal.seller_id:
                    if deal.status == 'paid':
                        keyboard.append([InlineKeyboardButton("✅ تأكيد إرسال المنتج", callback_data=f"confirm_delivery_{deal_id}")])
                    keyboard.append([InlineKeyboardButton("📋 إدارة الصفقة", callback_data="my_deals")])
                
                # إذا كان المستخدم مشتري محتمل أو المشتري الحالي
                elif deal.status == 'pending':
                    keyboard.append([InlineKeyboardButton("🛒 شراء الآن", callback_data=f"buy_deal_{deal_id}")])
                elif user_id == deal.buyer_id:
                    if deal.status == 'paid':
                        keyboard.append([InlineKeyboardButton("⏳ في انتظار تأكيد البائع", callback_data="waiting")])
                    elif deal.status == 'confirmed':
                        keyboard.append([InlineKeyboardButton("💰 تحرير الأموال", callback_data=f"release_funds_{deal_id}")])
                        keyboard.append([InlineKeyboardButton("⚠️ فتح نزاع", callback_data=f"dispute_{deal_id}")])
                
                keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # إرسال الوسائط إذا كانت متوفرة
                if deal.media_files:
                    try:
                        media_data = json.loads(deal.media_files)
                        for media in media_data:
                            if media['type'] == 'photo':
                                await context.bot.send_photo(
                                    chat_id=update.effective_chat.id,
                                    photo=media['file_id']
                                )
                            elif media['type'] == 'video':
                                await context.bot.send_video(
                                    chat_id=update.effective_chat.id,
                                    video=media['file_id']
                                )
                    except:
                        pass
                
                await update.message.reply_text(deal_text, reply_markup=reply_markup)
    
    async def initiate_purchase(self, query, context, deal_id):
        """بدء عملية الشراء"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                if deal.status != 'pending':
                    await query.edit_message_text("❌ هذه الصفقة غير متاحة للشراء حالياً.")
                    return
                
                if user_id == deal.seller_id:
                    await query.edit_message_text("❌ لا يمكنك شراء صفقتك الخاصة.")
                    return
                
                # إنشاء أزرار اختيار طريقة الدفع
                keyboard = [
                    [InlineKeyboardButton("💳 USDT (Polygon)", callback_data=f"pay_usdt_polygon_{deal_id}")],
                    [InlineKeyboardButton("💳 USDT (Ethereum)", callback_data=f"pay_usdt_eth_{deal_id}")],
                    [InlineKeyboardButton("₿ Bitcoin", callback_data=f"pay_btc_{deal_id}")],
                    [InlineKeyboardButton("🔄 صفحة دفع متقدمة", callback_data=f"pay_checkout_{deal_id}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                purchase_text = f"""
🛒 تأكيد الشراء

📦 المنتج: {deal.title}
💰 السعر الأساسي: ${deal.price:.2f}
💵 العمولة (5%): ${deal.commission:.2f}
💳 المبلغ الإجمالي: ${deal.total_price:.2f}

اختر طريقة الدفع المفضلة:

💡 ملاحظات مهمة:
• أموالك محمية في محفظة آمنة
• لن يتم تحرير الأموال إلا بعد تأكيد الاستلام
• يمكنك فتح نزاع في حالة وجود مشكلة
                """
                
                await query.edit_message_text(purchase_text, reply_markup=reply_markup)
    
    async def confirm_payment_process(self, query, context, deal_id):
        """تأكيد الدفع من المشتري"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                # تحديث الصفقة
                deal.buyer_id = user_id
                deal.status = 'paid'
                deal_db.session.commit()
                
                # إشعار المشتري
                await query.edit_message_text(f"""
✅ تم تأكيد الدفع بنجاح!

📦 الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

⏳ تم إشعار البائع، سيقوم بإرسال المنتج قريباً.
سيتم إشعارك عند تأكيد الإرسال.

🔒 أموالك محمية في محفظة البوت حتى تأكيد الاستلام.
                """)
                
                # إشعار البائع
                try:
                    seller = TelegramUser.query.filter_by(telegram_id=deal.seller_id).first()
                    buyer = TelegramUser.query.filter_by(telegram_id=user_id).first()
                    buyer_name = buyer.first_name if buyer else "مشتري"
                    
                    seller_keyboard = [
                        [InlineKeyboardButton("✅ تأكيد الإرسال", callback_data=f"confirm_delivery_{deal_id}")],
                        [InlineKeyboardButton("📋 عرض الصفقة", callback_data="my_deals")]
                    ]
                    seller_reply_markup = InlineKeyboardMarkup(seller_keyboard)
                    
                    await context.bot.send_message(
                        chat_id=deal.seller_id,
                        text=f"""
🔔 إشعار جديد - تم الدفع!

📦 الصفقة: {deal.title}
👤 المشتري: {buyer_name}
💰 المبلغ: ${deal.total_price:.2f}

✅ تم تأكيد الدفع من المشتري.
يرجى إرسال المنتج/الخدمة ثم الضغط على "تأكيد الإرسال".
                        """,
                        reply_markup=seller_reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to seller: {e}")
    
    async def release_funds_process(self, query, context, deal_id):
        """تحرير الأموال من المشتري"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                if deal.buyer_id != user_id:
                    await query.edit_message_text("❌ غير مصرح لك بهذا الإجراء.")
                    return
                
                if deal.status != 'confirmed':
                    await query.edit_message_text("❌ لا يمكن تحرير الأموال في هذه المرحلة.")
                    return
                
                # تحديث حالة الصفقة
                deal.status = 'completed'
                deal_db.session.commit()
                
                await query.edit_message_text(f"""
🎉 تم تحرير الأموال بنجاح!

📦 الصفقة: {deal.title}
💰 المبلغ المحرر: ${deal.price:.2f}
💵 العمولة: ${deal.commission:.2f}

✅ تم إتمام الصفقة بنجاح.
شكراً لاستخدام خدمة الوساطة الآمنة!
                """)
                
                # إشعار البائع
                try:
                    await context.bot.send_message(
                        chat_id=deal.seller_id,
                        text=f"""
🎉 تهانينا! تم إتمام الصفقة بنجاح

📦 الصفقة: {deal.title}
💰 المبلغ المستلم: ${deal.price:.2f}
💵 العمولة المخصومة: ${deal.commission:.2f}

✅ تم تحرير الأموال من المشتري.
المبلغ سيصل إلى محفظتك قريباً.
                        """
                    )
                except Exception as e:
                    logger.error(f"Error sending completion notification to seller: {e}")
    
    async def create_dispute_process(self, query, context, deal_id):
        """فتح نزاع على الصفقة"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                if user_id != deal.seller_id and user_id != deal.buyer_id:
                    await query.edit_message_text("❌ غير مصرح لك بهذا الإجراء.")
                    return
                
                # تحديث حالة الصفقة
                deal.status = 'disputed'
                deal_db.session.commit()
                
                await query.edit_message_text(f"""
⚠️ تم فتح نزاع على الصفقة

📦 الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

🔒 تم تجميد الأموال حتى حل النزاع.
سيتم التواصل معك من فريق الدعم قريباً.

📞 للمساعدة العاجلة، تواصل مع الدعم الفني.
                """)
                
                # إشعار الطرف الآخر
                other_party_id = deal.seller_id if user_id == deal.buyer_id else deal.buyer_id
                try:
                    await context.bot.send_message(
                        chat_id=other_party_id,
                        text=f"""
⚠️ تم فتح نزاع على إحدى صفقاتك

📦 الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

🔒 تم تجميد الأموال حتى حل النزاع.
سيتم التواصل معك من فريق الدعم قريباً.
                        """
                    )
                except Exception as e:
                    logger.error(f"Error sending dispute notification: {e}")
    
    async def confirm_delivery_process(self, query, context, deal_id):
        """تأكيد التسليم من البائع"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                if deal.seller_id != user_id:
                    await query.edit_message_text("❌ غير مصرح لك بهذا الإجراء.")
                    return
                
                if deal.status != 'paid':
                    await query.edit_message_text("❌ لا يمكن تأكيد التسليم في هذه المرحلة.")
                    return
                
                # تحديث حالة الصفقة
                deal.status = 'confirmed'
                deal_db.session.commit()
                
                await query.edit_message_text(f"""
✅ تم تأكيد التسليم بنجاح!

📦 الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

⏳ تم إشعار المشتري بالتسليم.
في انتظار تأكيد الاستلام وتحرير الأموال.
                """)
                
                # إشعار المشتري
                try:
                    buyer_keyboard = [
                        [InlineKeyboardButton("💰 تحرير الأموال", callback_data=f"release_funds_{deal_id}")],
                        [InlineKeyboardButton("⚠️ فتح نزاع", callback_data=f"dispute_{deal_id}")]
                    ]
                    buyer_reply_markup = InlineKeyboardMarkup(buyer_keyboard)
                    
                    await context.bot.send_message(
                        chat_id=deal.buyer_id,
                        text=f"""
📦 تم تأكيد إرسال المنتج!

🏷️ الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

✅ أكد البائع إرسال المنتج/الخدمة.
يرجى التحقق من الاستلام ثم:

• إذا كان كل شيء صحيح: اضغط "تحرير الأموال"
• إذا كان هناك مشكلة: اضغط "فتح نزاع"

🔒 أموالك محمية حتى تأكيد الاستلام.
                        """,
                        reply_markup=buyer_reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error sending delivery confirmation to buyer: {e}")
    
    async def process_payment(self, query, context, deal_id, coin_type, network):
        """معالجة الدفع بعملة محددة"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                try:
                    # استدعاء API لإنشاء عنوان الدفع
                    import requests
                    
                    api_url = f"http://localhost:5000/api/payments/create"
                    payload = {
                        'deal_id': deal_id,
                        'coin_type': coin_type,
                        'network': network
                    }
                    
                    response = requests.post(api_url, json=payload, timeout=10)
                    result = response.json()
                    
                    if result.get('success'):
                        payment_info = result['payment_info']
                        
                        payment_text = f"""
💳 تفاصيل الدفع - {coin_type} ({network})

📦 الصفقة: {deal.title}
💰 المبلغ: {payment_info['amount']} {payment_info['coin_name']}

📍 عنوان الدفع:
`{payment_info['address']}`

⚠️ تعليمات مهمة:
1. انسخ العنوان أعلاه بدقة
2. أرسل المبلغ المحدد بالضبط
3. تأكد من اختيار الشبكة الصحيحة: {network}
4. اضغط "تأكيد الدفع" بعد الإرسال

🔒 أموالك محمية حتى تأكيد الاستلام!
                        """
                        
                        keyboard = [
                            [InlineKeyboardButton("✅ تأكيد الدفع", callback_data=f"confirm_payment_{deal_id}")],
                            [InlineKeyboardButton("🔄 طريقة دفع أخرى", callback_data=f"buy_deal_{deal_id}")],
                            [InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')
                        
                    else:
                        await query.edit_message_text(f"❌ خطأ في إنشاء عنوان الدفع: {result.get('error', 'خطأ غير معروف')}")
                        
                except Exception as e:
                    logger.error(f"Error processing payment: {e}")
                    await query.edit_message_text("❌ خطأ في معالجة الدفع. يرجى المحاولة مرة أخرى.")
    
    async def create_checkout_page(self, query, context, deal_id):
        """إنشاء صفحة دفع متقدمة"""
        user_id = query.from_user.id
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                try:
                    # استدعاء API لإنشاء صفحة الدفع
                    import requests
                    
                    api_url = f"http://localhost:5000/api/payments/checkout"
                    payload = {
                        'deal_id': deal_id
                    }
                    
                    response = requests.post(api_url, json=payload, timeout=10)
                    result = response.json()
                    
                    if result.get('success'):
                        checkout_url = result['checkout_url']
                        
                        checkout_text = f"""
🔄 صفحة الدفع المتقدمة

📦 الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

🌐 تم إنشاء صفحة دفع خاصة بك حيث يمكنك:
• اختيار من بين 900+ عملة رقمية
• اختيار الشبكة المناسبة
• الحصول على أسعار صرف محدثة

👆 اضغط على الرابط أدناه لإتمام الدفع:
                        """
                        
                        keyboard = [
                            [InlineKeyboardButton("💳 فتح صفحة الدفع", url=checkout_url)],
                            [InlineKeyboardButton("✅ تأكيد الدفع", callback_data=f"confirm_payment_{deal_id}")],
                            [InlineKeyboardButton("🔙 العودة", callback_data=f"buy_deal_{deal_id}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(checkout_text, reply_markup=reply_markup)
                        
                    else:
                        await query.edit_message_text(f"❌ خطأ في إنشاء صفحة الدفع: {result.get('error', 'خطأ غير معروف')}")
                        
                except Exception as e:
                    logger.error(f"Error creating checkout page: {e}")
                    await query.edit_message_text("❌ خطأ في إنشاء صفحة الدفع. يرجى المحاولة مرة أخرى.")
    
    def run(self):
        """تشغيل البوت"""
        logger.info("بدء تشغيل البوت...")
        self.application.run_polling()

if __name__ == "__main__":
    # يجب وضع توكن البوت هنا
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("يرجى وضع توكن البوت في المتغير BOT_TOKEN")
        sys.exit(1)
    
    bot = OTCBot(BOT_TOKEN)
    bot.run()


    async def handle_dispute(self, query, context):
        """معالج فتح النزاعات"""
        user_id = query.from_user.id
        deal_id = query.data.split('_')[1]
        
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if not deal:
                    await query.edit_message_text("❌ الصفقة غير موجودة.")
                    return
                
                # التحقق من أن المستخدم طرف في الصفقة
                if user_id not in [deal.seller_id, deal.buyer_id]:
                    await query.edit_message_text("❌ غير مسموح لك بفتح نزاع على هذه الصفقة.")
                    return
                
                # عرض أسباب النزاع
                keyboard = [
                    [InlineKeyboardButton("لم أستلم المنتج", callback_data=f"dispute_reason_not_received_{deal_id}")],
                    [InlineKeyboardButton("المنتج مختلف", callback_data=f"dispute_reason_wrong_item_{deal_id}")],
                    [InlineKeyboardButton("المنتج تالف", callback_data=f"dispute_reason_damaged_item_{deal_id}")],
                    [InlineKeyboardButton("المنتج مزيف", callback_data=f"dispute_reason_fake_item_{deal_id}")],
                    [InlineKeyboardButton("مشكلة في الدفع", callback_data=f"dispute_reason_payment_issue_{deal_id}")],
                    [InlineKeyboardButton("البائع لا يرد", callback_data=f"dispute_reason_seller_unresponsive_{deal_id}")],
                    [InlineKeyboardButton("محاولة احتيال", callback_data=f"dispute_reason_scam_attempt_{deal_id}")],
                    [InlineKeyboardButton("أخرى", callback_data=f"dispute_reason_other_{deal_id}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data=f"view_deal_{deal_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                dispute_text = f"""
⚠️ فتح نزاع

📦 الصفقة: {deal.title}
💰 المبلغ: ${deal.total_price:.2f}

اختر سبب النزاع:
                """
                
                await query.edit_message_text(dispute_text, reply_markup=reply_markup)
    
    async def handle_dispute_reason(self, query, context):
        """معالج اختيار سبب النزاع"""
        user_id = query.from_user.id
        data_parts = query.data.split('_')
        reason = data_parts[2]
        deal_id = data_parts[3]
        
        # حفظ بيانات النزاع في حالة المستخدم
        if not hasattr(self, 'user_states'):
            self.user_states = {}
        
        self.user_states[user_id] = {
            'state': 'waiting_dispute_description',
            'data': {
                'deal_id': deal_id,
                'reason': reason
            }
        }
        
        reason_names = {
            'not_received': 'لم أستلم المنتج/الخدمة',
            'wrong_item': 'المنتج مختلف عن المطلوب',
            'damaged_item': 'المنتج تالف أو معطوب',
            'fake_item': 'المنتج مزيف أو غير أصلي',
            'payment_issue': 'مشكلة في الدفع',
            'seller_unresponsive': 'البائع لا يرد',
            'buyer_unresponsive': 'المشتري لا يرد',
            'scam_attempt': 'محاولة احتيال',
            'other': 'أخرى'
        }
        
        await query.edit_message_text(f"""
⚠️ فتح نزاع

السبب المختار: {reason_names.get(reason, 'غير معروف')}

يرجى كتابة وصف مفصل للمشكلة:
• ما الذي حدث بالضبط؟
• ما هي الأدلة المتوفرة؟
• ما هو الحل المطلوب؟

اكتب رسالة نصية مع التفاصيل.
        """)
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الرسائل النصية"""
        user_id = update.effective_user.id
        
        # فحص حالة المستخدم
        if hasattr(self, 'user_states') and user_id in self.user_states:
            user_state = self.user_states[user_id]
            
            if user_state['state'] == 'waiting_dispute_description':
                # إنشاء النزاع
                description = update.message.text
                deal_id = user_state['data']['deal_id']
                reason = user_state['data']['reason']
                
                if self.flask_app and hasattr(self, 'dispute_manager'):
                    result = self.dispute_manager.create_dispute(
                        deal_id=deal_id,
                        reporter_id=user_id,
                        reason=reason,
                        description=description
                    )
                    
                    if result['success']:
                        await update.message.reply_text(f"""
✅ تم فتح النزاع بنجاح!

📋 رقم النزاع: {result['dispute_id']}
⚠️ تم إشعار الطرف الآخر وفريق الدعم.

🔒 تم تجميد الأموال حتى حل النزاع.
سيتم التواصل معك قريباً من فريق الدعم.

💬 يمكنك أيضاً محاولة التواصل مع الطرف الآخر لحل المشكلة ودياً.
                        """)
                    else:
                        await update.message.reply_text(f"❌ خطأ في فتح النزاع: {result['error']}")
                
                # مسح حالة المستخدم
                del self.user_states[user_id]
                return
        
        # معالجة رسائل إنشاء الصفقة (الكود الموجود مسبقاً)
        # ... باقي الكود
    
    async def handle_rate_user(self, query, context):
        """معالج تقييم المستخدمين"""
        user_id = query.from_user.id
        rated_user_id = int(query.data.split('_')[2])
        
        # البحث عن صفقة مكتملة بين المستخدمين
        if self.flask_app:
            with self.flask_app.app_context():
                deal = Deal.query.filter(
                    ((Deal.seller_id == user_id) & (Deal.buyer_id == rated_user_id)) |
                    ((Deal.seller_id == rated_user_id) & (Deal.buyer_id == user_id)),
                    Deal.status == 'completed'
                ).first()
                
                if not deal:
                    await query.edit_message_text("❌ لا توجد صفقات مكتملة مع هذا المستخدم.")
                    return
                
                # عرض خيارات التقييم
                keyboard = [
                    [InlineKeyboardButton("⭐⭐⭐⭐⭐ ممتاز", callback_data=f"rating_5_{rated_user_id}_{deal.id}")],
                    [InlineKeyboardButton("⭐⭐⭐⭐ جيد جداً", callback_data=f"rating_4_{rated_user_id}_{deal.id}")],
                    [InlineKeyboardButton("⭐⭐⭐ جيد", callback_data=f"rating_3_{rated_user_id}_{deal.id}")],
                    [InlineKeyboardButton("⭐⭐ مقبول", callback_data=f"rating_2_{rated_user_id}_{deal.id}")],
                    [InlineKeyboardButton("⭐ ضعيف", callback_data=f"rating_1_{rated_user_id}_{deal.id}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="main_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                rated_user = TelegramUser.query.filter_by(telegram_id=rated_user_id).first()
                rated_user_name = rated_user.first_name if rated_user else "المستخدم"
                
                await query.edit_message_text(f"""
⭐ تقييم المستخدم

👤 المستخدم: {rated_user_name}
📦 الصفقة: {deal.title}

اختر التقييم المناسب:
                """, reply_markup=reply_markup)
    
    async def handle_rating_selection(self, query, context):
        """معالج اختيار التقييم"""
        user_id = query.from_user.id
        data_parts = query.data.split('_')
        rating = int(data_parts[1])
        rated_user_id = int(data_parts[2])
        deal_id = data_parts[3]
        
        if self.flask_app and hasattr(self, 'dispute_manager'):
            result = self.dispute_manager.add_user_rating(
                deal_id=deal_id,
                rater_id=user_id,
                rated_id=rated_user_id,
                rating=rating
            )
            
            if result['success']:
                await query.edit_message_text(f"""
✅ تم إضافة التقييم بنجاح!

⭐ التقييم: {rating}/5
👤 للمستخدم: {rated_user_id}

شكراً لك على تقييمك، هذا يساعد في تحسين جودة الخدمة.
                """)
            else:
                await query.edit_message_text(f"❌ خطأ في إضافة التقييم: {result['error']}")
    
    def setup_dispute_handlers(self):
        """إعداد معالجات النزاعات والتقييمات"""
        # إضافة معالجات النزاعات والتقييمات
        self.application.add_handler(CallbackQueryHandler(self.handle_dispute, pattern=r'^dispute_\d+$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_dispute_reason, pattern=r'^dispute_reason_'))
        self.application.add_handler(CallbackQueryHandler(self.handle_rate_user, pattern=r'^rate_user_'))
        self.application.add_handler(CallbackQueryHandler(self.handle_rating_selection, pattern=r'^rating_'))
        
        # إعداد مدير النزاعات
        from services.dispute_manager import DisputeManager
        from routes.disputes import set_dispute_manager
        
        self.dispute_manager = DisputeManager(self.flask_app, self)
        set_dispute_manager(self.dispute_manager)
        
        # تهيئة حالات المستخدمين
        self.user_states = {}

