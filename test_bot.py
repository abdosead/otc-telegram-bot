#!/usr/bin/env python3
"""
ملف اختبار شامل لبوت OTC
يتضمن اختبارات لجميع الوظائف الأساسية
"""

import os
import sys
import json
import time
import asyncio
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# إضافة مسار المشروع
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# استيراد النماذج والخدمات
from src.models.telegram_user import TelegramUser, db as user_db
from src.models.deal import Deal, db as deal_db
from src.models.dispute import Dispute, UserRating, SecurityLog, UserBan, db as dispute_db
from src.services.dispute_manager import DisputeManager
from src.services.payment_monitor import PaymentMonitor
from src.services.ccpayment import CCPaymentService
from src.telegram_bot import OTCBot
from src.main import app

class TestOTCBot(unittest.TestCase):
    """اختبارات البوت الأساسية"""
    
    def setUp(self):
        """إعداد البيئة للاختبار"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with self.app.app_context():
            user_db.create_all()
            deal_db.create_all()
            dispute_db.create_all()
        
        # إنشاء بوت وهمي للاختبار
        self.bot_token = "TEST_TOKEN"
        self.bot = OTCBot(self.bot_token, self.app)
    
    def tearDown(self):
        """تنظيف البيانات بعد الاختبار"""
        with self.app.app_context():
            user_db.drop_all()
            deal_db.drop_all()
            dispute_db.drop_all()
    
    def test_user_registration(self):
        """اختبار تسجيل المستخدمين"""
        with self.app.app_context():
            # إنشاء مستخدم جديد
            user = TelegramUser(
                telegram_id=123456789,
                username="test_user",
                first_name="Test",
                last_name="User"
            )
            user_db.session.add(user)
            user_db.session.commit()
            
            # التحقق من حفظ البيانات
            saved_user = TelegramUser.query.filter_by(telegram_id=123456789).first()
            self.assertIsNotNone(saved_user)
            self.assertEqual(saved_user.username, "test_user")
            self.assertEqual(saved_user.first_name, "Test")
    
    def test_deal_creation(self):
        """اختبار إنشاء الصفقات"""
        with self.app.app_context():
            # إنشاء صفقة جديدة
            deal = Deal(
                seller_id=123456789,
                title="iPhone 15 Pro",
                description="جهاز جديد بالكرتونة",
                price=1000.0,
                commission=50.0,
                total_price=1050.0
            )
            deal_db.session.add(deal)
            deal_db.session.commit()
            
            # التحقق من حفظ البيانات
            saved_deal = Deal.query.filter_by(title="iPhone 15 Pro").first()
            self.assertIsNotNone(saved_deal)
            self.assertEqual(saved_deal.seller_id, 123456789)
            self.assertEqual(saved_deal.price, 1000.0)
            self.assertEqual(saved_deal.status, 'pending')
    
    def test_deal_purchase_flow(self):
        """اختبار تدفق الشراء"""
        with self.app.app_context():
            # إنشاء صفقة
            deal = Deal(
                seller_id=123456789,
                title="Test Product",
                description="Test Description",
                price=100.0,
                commission=5.0,
                total_price=105.0
            )
            deal_db.session.add(deal)
            deal_db.session.commit()
            
            # محاكاة الشراء
            deal.buyer_id = 987654321
            deal.status = 'paid'
            deal_db.session.commit()
            
            # التحقق من تحديث الحالة
            updated_deal = Deal.query.get(deal.id)
            self.assertEqual(updated_deal.status, 'paid')
            self.assertEqual(updated_deal.buyer_id, 987654321)
    
    def test_dispute_creation(self):
        """اختبار إنشاء النزاعات"""
        with self.app.app_context():
            # إنشاء صفقة أولاً
            deal = Deal(
                seller_id=123456789,
                title="Test Product",
                description="Test Description",
                price=100.0,
                commission=5.0,
                total_price=105.0,
                buyer_id=987654321,
                status='paid'
            )
            deal_db.session.add(deal)
            deal_db.session.commit()
            
            # إنشاء مدير النزاعات
            dispute_manager = DisputeManager(self.app)
            
            # إنشاء نزاع
            result = dispute_manager.create_dispute(
                deal_id=deal.id,
                reporter_id=987654321,
                reason='not_received',
                description='لم أستلم المنتج بعد'
            )
            
            self.assertTrue(result['success'])
            self.assertIn('dispute_id', result)
            
            # التحقق من حفظ النزاع
            dispute = Dispute.query.get(result['dispute_id'])
            self.assertIsNotNone(dispute)
            self.assertEqual(dispute.reason, 'not_received')
    
    def test_user_rating(self):
        """اختبار تقييم المستخدمين"""
        with self.app.app_context():
            # إنشاء صفقة مكتملة
            deal = Deal(
                seller_id=123456789,
                title="Test Product",
                description="Test Description",
                price=100.0,
                commission=5.0,
                total_price=105.0,
                buyer_id=987654321,
                status='completed'
            )
            deal_db.session.add(deal)
            deal_db.session.commit()
            
            # إنشاء مدير النزاعات
            dispute_manager = DisputeManager(self.app)
            
            # إضافة تقييم
            result = dispute_manager.add_user_rating(
                deal_id=deal.id,
                rater_id=987654321,
                rated_id=123456789,
                rating=5,
                comment='بائع ممتاز'
            )
            
            self.assertTrue(result['success'])
            
            # التحقق من حفظ التقييم
            rating = UserRating.query.filter_by(deal_id=deal.id).first()
            self.assertIsNotNone(rating)
            self.assertEqual(rating.rating, 5)
    
    def test_security_logging(self):
        """اختبار تسجيل الأحداث الأمنية"""
        with self.app.app_context():
            dispute_manager = DisputeManager(self.app)
            
            # تسجيل حدث أمني
            dispute_manager.log_security_event(
                user_id=123456789,
                event_type='login',
                description='User logged in',
                severity='info'
            )
            
            # التحقق من حفظ السجل
            log = SecurityLog.query.filter_by(user_id=123456789).first()
            self.assertIsNotNone(log)
            self.assertEqual(log.event_type, 'login')
    
    def test_user_ban_system(self):
        """اختبار نظام حظر المستخدمين"""
        with self.app.app_context():
            dispute_manager = DisputeManager(self.app)
            
            # حظر مستخدم
            result = dispute_manager.ban_user(
                user_id=123456789,
                admin_id=999999999,
                reason='spam',
                description='إرسال رسائل مزعجة',
                ban_type='temporary',
                duration_hours=24
            )
            
            self.assertTrue(result['success'])
            
            # التحقق من الحظر
            is_banned = dispute_manager.is_user_banned(123456789)
            self.assertTrue(is_banned)
    
    def test_suspicious_activity_detection(self):
        """اختبار كشف النشاط المشبوه"""
        with self.app.app_context():
            dispute_manager = DisputeManager(self.app)
            
            # إنشاء عدة نزاعات للمستخدم
            for i in range(4):
                deal = Deal(
                    seller_id=123456789,
                    title=f"Test Product {i}",
                    description="Test Description",
                    price=100.0,
                    commission=5.0,
                    total_price=105.0,
                    buyer_id=987654321 + i,
                    status='disputed'
                )
                deal_db.session.add(deal)
                deal_db.session.commit()
                
                dispute = Dispute(
                    id=f"dispute_{i}",
                    deal_id=deal.id,
                    reporter_id=987654321 + i,
                    reported_id=123456789,
                    reason='scam_attempt',
                    description='محاولة احتيال'
                )
                dispute_db.session.add(dispute)
            
            dispute_db.session.commit()
            
            # كشف النشاط المشبوه
            analysis = dispute_manager.detect_suspicious_activity(123456789)
            
            self.assertEqual(analysis['risk_level'], 'high')
            self.assertGreaterEqual(analysis['disputes_count'], 3)

class TestCCPaymentIntegration(unittest.TestCase):
    """اختبارات تكامل CCPayments"""
    
    def setUp(self):
        """إعداد البيئة للاختبار"""
        self.ccpayment = CCPaymentService(
            app_id="test_app_id",
            app_secret="test_app_secret"
        )
    
    @patch('requests.post')
    def test_create_deposit_address(self, mock_post):
        """اختبار إنشاء عنوان الإيداع"""
        # محاكاة استجابة API
        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 10000,
            'msg': 'success',
            'data': {
                'address': '0x1234567890abcdef',
                'memo': '',
                'qr_code': 'data:image/png;base64,iVBOR...'
            }
        }
        mock_post.return_value = mock_response
        
        # اختبار إنشاء العنوان
        result = self.ccpayment.create_deposit_address(
            order_id="test_order_123",
            token_id="USDT",
            network="Polygon",
            amount=100.0
        )
        
        self.assertTrue(result['success'])
        self.assertIn('address', result)
    
    @patch('requests.post')
    def test_get_deposit_record(self, mock_post):
        """اختبار الحصول على سجل الإيداع"""
        # محاكاة استجابة API
        mock_response = Mock()
        mock_response.json.return_value = {
            'code': 10000,
            'msg': 'success',
            'data': {
                'status': 'success',
                'amount': 100.0,
                'tx_id': '0xabcdef1234567890'
            }
        }
        mock_post.return_value = mock_response
        
        # اختبار الحصول على السجل
        result = self.ccpayment.get_deposit_record("test_order_123")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'success')

class TestPerformance(unittest.TestCase):
    """اختبارات الأداء"""
    
    def setUp(self):
        """إعداد البيئة للاختبار"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with self.app.app_context():
            user_db.create_all()
            deal_db.create_all()
            dispute_db.create_all()
    
    def test_database_performance(self):
        """اختبار أداء قاعدة البيانات"""
        with self.app.app_context():
            # قياس وقت إنشاء 100 صفقة
            start_time = time.time()
            
            for i in range(100):
                deal = Deal(
                    seller_id=123456789 + i,
                    title=f"Product {i}",
                    description=f"Description {i}",
                    price=100.0 + i,
                    commission=5.0,
                    total_price=105.0 + i
                )
                deal_db.session.add(deal)
            
            deal_db.session.commit()
            end_time = time.time()
            
            creation_time = end_time - start_time
            print(f"وقت إنشاء 100 صفقة: {creation_time:.2f} ثانية")
            
            # يجب أن يكون الوقت أقل من ثانية واحدة
            self.assertLess(creation_time, 1.0)
    
    def test_query_performance(self):
        """اختبار أداء الاستعلامات"""
        with self.app.app_context():
            # إنشاء بيانات للاختبار
            for i in range(1000):
                deal = Deal(
                    seller_id=123456789 + (i % 10),
                    title=f"Product {i}",
                    description=f"Description {i}",
                    price=100.0 + i,
                    commission=5.0,
                    total_price=105.0 + i,
                    status='pending' if i % 2 == 0 else 'completed'
                )
                deal_db.session.add(deal)
            
            deal_db.session.commit()
            
            # قياس وقت الاستعلام
            start_time = time.time()
            
            # استعلام معقد
            results = Deal.query.filter(
                Deal.status == 'pending',
                Deal.price > 500.0
            ).order_by(Deal.created_at.desc()).limit(50).all()
            
            end_time = time.time()
            query_time = end_time - start_time
            
            print(f"وقت الاستعلام المعقد: {query_time:.4f} ثانية")
            print(f"عدد النتائج: {len(results)}")
            
            # يجب أن يكون الوقت أقل من 0.1 ثانية
            self.assertLess(query_time, 0.1)

def run_tests():
    """تشغيل جميع الاختبارات"""
    print("🧪 بدء اختبارات بوت OTC")
    print("=" * 50)
    
    # إنشاء مجموعة الاختبارات
    test_suite = unittest.TestSuite()
    
    # إضافة اختبارات البوت الأساسية
    test_suite.addTest(unittest.makeSuite(TestOTCBot))
    
    # إضافة اختبارات CCPayments
    test_suite.addTest(unittest.makeSuite(TestCCPaymentIntegration))
    
    # إضافة اختبارات الأداء
    test_suite.addTest(unittest.makeSuite(TestPerformance))
    
    # تشغيل الاختبارات
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # طباعة النتائج
    print("\n" + "=" * 50)
    print("📊 نتائج الاختبارات:")
    print(f"✅ اختبارات نجحت: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ اختبارات فشلت: {len(result.failures)}")
    print(f"🚨 أخطاء: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ الاختبارات الفاشلة:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\n🚨 الأخطاء:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

