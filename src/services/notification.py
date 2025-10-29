import logging
import asyncio
from typing import Optional, Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.models.deal import Deal
from src.models.telegram_user import TelegramUser

logger = logging.getLogger(__name__)

class NotificationService:
    """خدمة إرسال الإشعارات للمستخدمين"""
    
    def __init__(self, bot_instance=None):
        self.bot_instance = bot_instance
    
    async def notify_payment_confirmed(self, deal: Deal):
        """إشعار تأكيد الدفع"""
        try:
            # إشعار البائع
            await self.notify_seller_payment_received(deal)
            
            # إشعار المشتري
            await self.notify_buyer_payment_confirmed(deal)
            
        except Exception as e:
            logger.error(f"Error sending payment confirmation notifications: {e}")
    
    async def notify_seller_payment_received(self, deal: Deal):
        """إشعار البائع باستلام الدفع"""
        try:
            if not self.bot_instance:
                return
            
            seller_text = f"""
💰 تم استلام الدفع!

📦 الصفقة: {deal.title}
💳 المبلغ: ${deal.total_price:.2f}
🔄 الحالة: تم تأكيد الدفع

⚡ الخطوة التالية:
قم بإرسال المنتج/الخدمة للمشتري، ثم اضغط "تأكيد الإرسال" لإشعار المشتري.

🔒 الأموال محفوظة بأمان حتى تأكيد المشتري للاستلام.
            """
            
            keyboard = [
                [InlineKeyboardButton("✅ تأكيد الإرسال", callback_data=f"confirm_delivery_{deal.id}")],
                [InlineKeyboardButton("📋 تفاصيل الصفقة", callback_data=f"view_deal_{deal.id}")],
                [InlineKeyboardButton("💬 التواصل مع المشتري", url=f"tg://user?id={deal.buyer_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.seller_id,
                text=seller_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error notifying seller of payment: {e}")
    
    async def notify_buyer_payment_confirmed(self, deal: Deal):
        """إشعار المشتري بتأكيد الدفع"""
        try:
            if not self.bot_instance:
                return
            
            buyer_text = f"""
✅ تم تأكيد دفعتك!

📦 الصفقة: {deal.title}
💳 المبلغ المدفوع: ${deal.total_price:.2f}
🔄 الحالة: في انتظار إرسال البائع

⏳ الخطوة التالية:
البائع سيقوم بإرسال المنتج/الخدمة قريباً. ستحصل على إشعار عندما يؤكد البائع الإرسال.

🔒 أموالك محمية ولن يتم تحريرها إلا بعد تأكيدك للاستلام.
            """
            
            keyboard = [
                [InlineKeyboardButton("📋 تفاصيل الصفقة", callback_data=f"view_deal_{deal.id}")],
                [InlineKeyboardButton("💬 التواصل مع البائع", url=f"tg://user?id={deal.seller_id}")],
                [InlineKeyboardButton("⚠️ فتح نزاع", callback_data=f"dispute_{deal.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.buyer_id,
                text=buyer_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error notifying buyer of payment confirmation: {e}")
    
    async def notify_payment_failed(self, deal: Deal):
        """إشعار فشل الدفع"""
        try:
            if not self.bot_instance or not deal.buyer_id:
                return
            
            failed_text = f"""
❌ فشل في الدفع

📦 الصفقة: {deal.title}
💳 المبلغ المطلوب: ${deal.total_price:.2f}

⚠️ لم يتم تأكيد دفعتك بعد. الأسباب المحتملة:
• لم يتم إرسال المبلغ بعد
• المبلغ غير صحيح
• الشبكة غير صحيحة
• تأخير في الشبكة

🔄 يمكنك المحاولة مرة أخرى أو التواصل مع الدعم.
            """
            
            keyboard = [
                [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data=f"buy_deal_{deal.id}")],
                [InlineKeyboardButton("📋 تفاصيل الصفقة", callback_data=f"view_deal_{deal.id}")],
                [InlineKeyboardButton("💬 الدعم الفني", url="https://t.me/your_support_bot")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.buyer_id,
                text=failed_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error notifying payment failure: {e}")
    
    async def notify_payment_reminder(self, deal: Deal):
        """تذكير بالدفع"""
        try:
            if not self.bot_instance or not deal.buyer_id:
                return
            
            reminder_text = f"""
⏰ تذكير بالدفع

📦 الصفقة: {deal.title}
💳 المبلغ المطلوب: ${deal.total_price:.2f}

⚠️ لم يتم تأكيد دفعتك بعد. إذا كنت قد دفعت بالفعل، قد تحتاج لبعض الوقت للتأكيد.

🔄 إذا لم تدفع بعد، يرجى إتمام الدفع قريباً لتجنب إلغاء الصفقة.
            """
            
            keyboard = [
                [InlineKeyboardButton("💳 إتمام الدفع", callback_data=f"buy_deal_{deal.id}")],
                [InlineKeyboardButton("📋 تفاصيل الصفقة", callback_data=f"view_deal_{deal.id}")],
                [InlineKeyboardButton("❌ إلغاء الصفقة", callback_data=f"cancel_deal_{deal.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.buyer_id,
                text=reminder_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error sending payment reminder: {e}")
    
    async def notify_delivery_confirmed(self, deal: Deal):
        """إشعار تأكيد الإرسال"""
        try:
            if not self.bot_instance or not deal.buyer_id:
                return
            
            delivery_text = f"""
📦 تم إرسال طلبك!

📦 الصفقة: {deal.title}
💳 المبلغ: ${deal.total_price:.2f}
🔄 الحالة: تم الإرسال من البائع

✅ الخطوة التالية:
بعد استلام المنتج/الخدمة والتأكد من جودتها، اضغط "تحرير الأموال" لإتمام الصفقة.

⚠️ إذا لم تستلم شيئاً أو كان هناك مشكلة، يمكنك فتح نزاع.
            """
            
            keyboard = [
                [InlineKeyboardButton("✅ تحرير الأموال", callback_data=f"release_funds_{deal.id}")],
                [InlineKeyboardButton("⚠️ فتح نزاع", callback_data=f"dispute_{deal.id}")],
                [InlineKeyboardButton("💬 التواصل مع البائع", url=f"tg://user?id={deal.seller_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.buyer_id,
                text=delivery_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error notifying delivery confirmation: {e}")
    
    async def notify_funds_released(self, deal: Deal):
        """إشعار تحرير الأموال"""
        try:
            # إشعار البائع
            await self.notify_seller_funds_released(deal)
            
            # إشعار المشتري
            await self.notify_buyer_transaction_completed(deal)
            
        except Exception as e:
            logger.error(f"Error sending funds release notifications: {e}")
    
    async def notify_seller_funds_released(self, deal: Deal):
        """إشعار البائع بتحرير الأموال"""
        try:
            if not self.bot_instance:
                return
            
            seller_text = f"""
🎉 تم إتمام الصفقة بنجاح!

📦 الصفقة: {deal.title}
💰 المبلغ المستلم: ${deal.price:.2f}
💵 العمولة المخصومة: ${deal.commission:.2f}

✅ تم تحرير الأموال وستصلك قريباً في محفظتك.

⭐ شكراً لاستخدام خدمة الوساطة الآمنة!
            """
            
            keyboard = [
                [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
                [InlineKeyboardButton("💰 إنشاء صفقة جديدة", callback_data="create_deal")],
                [InlineKeyboardButton("⭐ تقييم المشتري", callback_data=f"rate_user_{deal.buyer_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.seller_id,
                text=seller_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error notifying seller of funds release: {e}")
    
    async def notify_buyer_transaction_completed(self, deal: Deal):
        """إشعار المشتري بإتمام المعاملة"""
        try:
            if not self.bot_instance:
                return
            
            buyer_text = f"""
🎉 تم إتمام الصفقة بنجاح!

📦 الصفقة: {deal.title}
💳 المبلغ المدفوع: ${deal.total_price:.2f}

✅ تم تحرير الأموال للبائع وإتمام المعاملة بنجاح.

⭐ شكراً لاستخدام خدمة الوساطة الآمنة!
            """
            
            keyboard = [
                [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
                [InlineKeyboardButton("🛒 تصفح الصفقات", callback_data="browse_deals")],
                [InlineKeyboardButton("⭐ تقييم البائع", callback_data=f"rate_user_{deal.seller_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot_instance.application.bot.send_message(
                chat_id=deal.buyer_id,
                text=buyer_text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error notifying buyer of transaction completion: {e}")
    
    async def notify_dispute_created(self, deal: Deal, dispute_reason: str):
        """إشعار إنشاء نزاع"""
        try:
            # إشعار الطرف الآخر
            if deal.buyer_id:  # إذا كان هناك مشتري
                other_party = deal.seller_id if deal.buyer_id else deal.buyer_id
                
                dispute_text = f"""
⚠️ تم فتح نزاع

📦 الصفقة: {deal.title}
💳 المبلغ: ${deal.total_price:.2f}
📝 السبب: {dispute_reason}

🔒 تم تجميد الأموال حتى حل النزاع.
سيتم التواصل معك قريباً من فريق الدعم.

💬 يمكنك التواصل مع الطرف الآخر لحل المشكلة ودياً.
                """
                
                keyboard = [
                    [InlineKeyboardButton("📋 تفاصيل النزاع", callback_data=f"view_dispute_{deal.id}")],
                    [InlineKeyboardButton("💬 التواصل مع الدعم", url="https://t.me/your_support_bot")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await self.bot_instance.application.bot.send_message(
                    chat_id=other_party,
                    text=dispute_text,
                    reply_markup=reply_markup
                )
            
        except Exception as e:
            logger.error(f"Error notifying dispute creation: {e}")
    
    async def send_custom_notification(self, user_id: int, message: str, 
                                     keyboard: Optional[InlineKeyboardMarkup] = None):
        """إرسال إشعار مخصص"""
        try:
            if not self.bot_instance:
                return
            
            await self.bot_instance.application.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error sending custom notification: {e}")
    
    async def broadcast_message(self, user_ids: list, message: str, 
                              keyboard: Optional[InlineKeyboardMarkup] = None):
        """إرسال رسالة جماعية"""
        try:
            if not self.bot_instance:
                return
            
            for user_id in user_ids:
                try:
                    await self.bot_instance.application.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        reply_markup=keyboard
                    )
                    # تأخير قصير لتجنب حدود التليجرام
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error sending broadcast to user {user_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error in broadcast: {e}")

