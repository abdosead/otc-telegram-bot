import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
from src.models.deal import Deal, db
from src.services.ccpayment import get_ccpayment_service
from src.services.notification import NotificationService

logger = logging.getLogger(__name__)

class PaymentMonitor:
    """خدمة مراقبة المدفوعات والتحقق التلقائي"""
    
    def __init__(self, flask_app, bot_instance=None):
        self.flask_app = flask_app
        self.bot_instance = bot_instance
        self.notification_service = NotificationService(bot_instance)
        self.ccpayment = None
        self.is_running = False
        self.check_interval = 30  # ثانية
        
    def initialize_ccpayment(self):
        """تهيئة خدمة CCPayment"""
        try:
            self.ccpayment = get_ccpayment_service()
            logger.info("CCPayment service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CCPayment service: {e}")
            self.ccpayment = None
    
    async def start_monitoring(self):
        """بدء مراقبة المدفوعات"""
        if self.is_running:
            logger.warning("Payment monitor is already running")
            return
        
        self.is_running = True
        logger.info("Starting payment monitoring service...")
        
        # تهيئة CCPayment
        self.initialize_ccpayment()
        
        while self.is_running:
            try:
                await self.check_pending_payments()
                await self.check_expired_payments()
                await self.cleanup_old_records()
                
                # انتظار قبل الفحص التالي
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in payment monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    def stop_monitoring(self):
        """إيقاف مراقبة المدفوعات"""
        self.is_running = False
        logger.info("Payment monitoring service stopped")
    
    async def check_pending_payments(self):
        """فحص المدفوعات المعلقة"""
        if not self.ccpayment:
            return
        
        try:
            with self.flask_app.app_context():
                # الحصول على الصفقات المعلقة التي لها معلومات دفع
                pending_deals = Deal.query.filter(
                    Deal.status == 'pending',
                    Deal.payment_id.isnot(None)
                ).all()
                
                for deal in pending_deals:
                    await self.verify_deal_payment(deal)
                    
        except Exception as e:
            logger.error(f"Error checking pending payments: {e}")
    
    async def verify_deal_payment(self, deal: Deal):
        """التحقق من دفع صفقة محددة"""
        try:
            # الحصول على معلومات الدفع
            result = self.ccpayment.get_deposit_record(deal.id)
            
            if result['success']:
                payment_status = result.get('status', 'unknown')
                
                if payment_status == 'success' and deal.status == 'pending':
                    # تحديث حالة الصفقة
                    deal.status = 'paid'
                    
                    # تحديث معلومات المعاملة
                    if deal.payment_id:
                        try:
                            payment_info = json.loads(deal.payment_id)
                            payment_info['tx_id'] = result.get('tx_id')
                            payment_info['confirmed_amount'] = result.get('amount')
                            payment_info['confirmation_time'] = datetime.utcnow().isoformat()
                            deal.payment_id = json.dumps(payment_info)
                        except:
                            pass
                    
                    db.session.commit()
                    
                    # إرسال إشعارات
                    await self.notification_service.notify_payment_confirmed(deal)
                    
                    logger.info(f"Payment confirmed for deal {deal.id}")
                    
                elif payment_status == 'failed':
                    # معالجة الدفع الفاشل
                    await self.handle_failed_payment(deal)
                    
        except Exception as e:
            logger.error(f"Error verifying payment for deal {deal.id}: {e}")
    
    async def handle_failed_payment(self, deal: Deal):
        """معالجة الدفع الفاشل"""
        try:
            logger.info(f"Handling failed payment for deal {deal.id}")
            
            # إرسال إشعار للمشتري
            await self.notification_service.notify_payment_failed(deal)
            
            # يمكن إضافة منطق إضافي هنا مثل:
            # - إعادة إنشاء عنوان دفع جديد
            # - إرسال تذكير
            # - إلغاء الصفقة بعد فترة معينة
            
        except Exception as e:
            logger.error(f"Error handling failed payment for deal {deal.id}: {e}")
    
    async def check_expired_payments(self):
        """فحص المدفوعات المنتهية الصلاحية"""
        try:
            with self.flask_app.app_context():
                # الصفقات المعلقة لأكثر من ساعة
                expiry_time = datetime.utcnow() - timedelta(hours=1)
                
                expired_deals = Deal.query.filter(
                    Deal.status == 'pending',
                    Deal.created_at < expiry_time,
                    Deal.payment_id.isnot(None)
                ).all()
                
                for deal in expired_deals:
                    await self.handle_expired_payment(deal)
                    
        except Exception as e:
            logger.error(f"Error checking expired payments: {e}")
    
    async def handle_expired_payment(self, deal: Deal):
        """معالجة المدفوعات المنتهية الصلاحية"""
        try:
            logger.info(f"Handling expired payment for deal {deal.id}")
            
            # إرسال تذكير للمشتري
            await self.notification_service.notify_payment_reminder(deal)
            
            # يمكن إضافة منطق إضافي مثل:
            # - إلغاء الصفقة بعد 24 ساعة
            # - إرسال تذكير نهائي
            
        except Exception as e:
            logger.error(f"Error handling expired payment for deal {deal.id}: {e}")
    
    async def cleanup_old_records(self):
        """تنظيف السجلات القديمة"""
        try:
            with self.flask_app.app_context():
                # حذف الصفقات الملغاة القديمة (أكثر من أسبوع)
                cleanup_time = datetime.utcnow() - timedelta(days=7)
                
                old_deals = Deal.query.filter(
                    Deal.status == 'cancelled',
                    Deal.created_at < cleanup_time
                ).all()
                
                for deal in old_deals:
                    db.session.delete(deal)
                
                if old_deals:
                    db.session.commit()
                    logger.info(f"Cleaned up {len(old_deals)} old cancelled deals")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
    
    async def force_check_deal(self, deal_id: str):
        """فحص صفقة محددة فوراً"""
        try:
            with self.flask_app.app_context():
                deal = Deal.query.get(deal_id)
                if deal:
                    await self.verify_deal_payment(deal)
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error force checking deal {deal_id}: {e}")
            return False
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات المراقبة"""
        try:
            with self.flask_app.app_context():
                stats = {
                    'is_running': self.is_running,
                    'check_interval': self.check_interval,
                    'pending_payments': Deal.query.filter(
                        Deal.status == 'pending',
                        Deal.payment_id.isnot(None)
                    ).count(),
                    'paid_deals': Deal.query.filter(Deal.status == 'paid').count(),
                    'completed_deals': Deal.query.filter(Deal.status == 'completed').count(),
                    'disputed_deals': Deal.query.filter(Deal.status == 'disputed').count(),
                    'total_deals': Deal.query.count(),
                    'ccpayment_status': 'connected' if self.ccpayment else 'disconnected'
                }
                return stats
                
        except Exception as e:
            logger.error(f"Error getting monitoring stats: {e}")
            return {'error': str(e)}

class PaymentValidator:
    """فئة للتحقق من صحة المدفوعات"""
    
    @staticmethod
    def validate_payment_amount(expected_amount: float, received_amount: float, 
                              tolerance: float = 0.01) -> bool:
        """التحقق من صحة مبلغ الدفع"""
        difference = abs(expected_amount - received_amount)
        return difference <= tolerance
    
    @staticmethod
    def validate_payment_currency(expected_currency: str, received_currency: str) -> bool:
        """التحقق من صحة العملة"""
        return expected_currency.upper() == received_currency.upper()
    
    @staticmethod
    def validate_payment_network(expected_network: str, received_network: str) -> bool:
        """التحقق من صحة الشبكة"""
        return expected_network.upper() == received_network.upper()
    
    @staticmethod
    def is_payment_recent(payment_time: datetime, max_age_hours: int = 24) -> bool:
        """التحقق من أن الدفع حديث"""
        age = datetime.utcnow() - payment_time
        return age.total_seconds() <= max_age_hours * 3600

