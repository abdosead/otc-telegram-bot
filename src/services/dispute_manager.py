import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from src.models.dispute import Dispute, UserRating, SecurityLog, UserBan, db
from src.models.deal import Deal
from src.models.telegram_user import TelegramUser
from src.services.notification import NotificationService

logger = logging.getLogger(__name__)

class DisputeManager:
    """مدير النزاعات والأمان"""
    
    def __init__(self, flask_app, bot_instance=None):
        self.flask_app = flask_app
        self.bot_instance = bot_instance
        self.notification_service = NotificationService(bot_instance)
        
        # أسباب النزاعات المتاحة
        self.dispute_reasons = {
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
    
    def create_dispute(self, deal_id: str, reporter_id: int, reason: str, 
                      description: str, evidence: Optional[str] = None) -> Dict[str, Any]:
        """إنشاء نزاع جديد"""
        try:
            with self.flask_app.app_context():
                # التحقق من وجود الصفقة
                deal = Deal.query.get(deal_id)
                if not deal:
                    return {'success': False, 'error': 'Deal not found'}
                
                # التحقق من أن المستخدم طرف في الصفقة
                if reporter_id not in [deal.seller_id, deal.buyer_id]:
                    return {'success': False, 'error': 'User is not part of this deal'}
                
                # تحديد الطرف المبلغ عنه
                reported_id = deal.buyer_id if reporter_id == deal.seller_id else deal.seller_id
                
                # التحقق من عدم وجود نزاع مفتوح بالفعل
                existing_dispute = Dispute.query.filter_by(
                    deal_id=deal_id,
                    status='open'
                ).first()
                
                if existing_dispute:
                    return {'success': False, 'error': 'Dispute already exists for this deal'}
                
                # إنشاء النزاع
                dispute_id = str(uuid.uuid4())
                dispute = Dispute(
                    id=dispute_id,
                    deal_id=deal_id,
                    reporter_id=reporter_id,
                    reported_id=reported_id,
                    reason=reason,
                    description=description,
                    evidence=evidence
                )
                
                # تحديث حالة الصفقة
                deal.status = 'disputed'
                
                db.session.add(dispute)
                db.session.commit()
                
                # تسجيل الحدث
                self.log_security_event(
                    user_id=reporter_id,
                    event_type='dispute_created',
                    description=f'User created dispute for deal {deal_id}',
                    severity='warning'
                )
                
                # إرسال إشعارات
                self.notification_service.notify_dispute_created(deal, reason)
                
                return {
                    'success': True,
                    'dispute_id': dispute_id,
                    'message': 'Dispute created successfully'
                }
                
        except Exception as e:
            logger.error(f"Error creating dispute: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def resolve_dispute(self, dispute_id: str, admin_id: int, resolution: str, 
                       winner_id: Optional[int] = None) -> Dict[str, Any]:
        """حل النزاع"""
        try:
            with self.flask_app.app_context():
                dispute = Dispute.query.get(dispute_id)
                if not dispute:
                    return {'success': False, 'error': 'Dispute not found'}
                
                if dispute.status != 'open':
                    return {'success': False, 'error': 'Dispute is not open'}
                
                # تحديث النزاع
                dispute.status = 'resolved'
                dispute.resolution = resolution
                dispute.resolved_by = admin_id
                dispute.resolved_at = datetime.utcnow()
                
                # تحديث حالة الصفقة
                deal = Deal.query.get(dispute.deal_id)
                if deal:
                    if winner_id == deal.buyer_id:
                        # المشتري ربح - إرجاع الأموال
                        deal.status = 'refunded'
                    elif winner_id == deal.seller_id:
                        # البائع ربح - تحرير الأموال
                        deal.status = 'completed'
                    else:
                        # حل وسط أو إلغاء
                        deal.status = 'cancelled'
                
                db.session.commit()
                
                # تسجيل الحدث
                self.log_security_event(
                    user_id=admin_id,
                    event_type='dispute_resolved',
                    description=f'Admin resolved dispute {dispute_id}',
                    severity='info'
                )
                
                return {
                    'success': True,
                    'message': 'Dispute resolved successfully'
                }
                
        except Exception as e:
            logger.error(f"Error resolving dispute: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def add_user_rating(self, deal_id: str, rater_id: int, rated_id: int, 
                       rating: int, comment: Optional[str] = None) -> Dict[str, Any]:
        """إضافة تقييم للمستخدم"""
        try:
            with self.flask_app.app_context():
                # التحقق من صحة التقييم
                if rating < 1 or rating > 5:
                    return {'success': False, 'error': 'Rating must be between 1 and 5'}
                
                # التحقق من وجود الصفقة
                deal = Deal.query.get(deal_id)
                if not deal or deal.status != 'completed':
                    return {'success': False, 'error': 'Deal not found or not completed'}
                
                # التحقق من أن المستخدم طرف في الصفقة
                if rater_id not in [deal.seller_id, deal.buyer_id]:
                    return {'success': False, 'error': 'User is not part of this deal'}
                
                # التحقق من عدم وجود تقييم سابق
                existing_rating = UserRating.query.filter_by(
                    deal_id=deal_id,
                    rater_id=rater_id,
                    rated_id=rated_id
                ).first()
                
                if existing_rating:
                    return {'success': False, 'error': 'Rating already exists'}
                
                # إنشاء التقييم
                user_rating = UserRating(
                    deal_id=deal_id,
                    rater_id=rater_id,
                    rated_id=rated_id,
                    rating=rating,
                    comment=comment
                )
                
                db.session.add(user_rating)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': 'Rating added successfully'
                }
                
        except Exception as e:
            logger.error(f"Error adding rating: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def get_user_ratings(self, user_id: int) -> Dict[str, Any]:
        """الحصول على تقييمات المستخدم"""
        try:
            with self.flask_app.app_context():
                ratings = UserRating.query.filter_by(rated_id=user_id).all()
                
                if not ratings:
                    return {
                        'success': True,
                        'average_rating': 0,
                        'total_ratings': 0,
                        'ratings': []
                    }
                
                total_rating = sum(r.rating for r in ratings)
                average_rating = total_rating / len(ratings)
                
                return {
                    'success': True,
                    'average_rating': round(average_rating, 2),
                    'total_ratings': len(ratings),
                    'ratings': [r.to_dict() for r in ratings]
                }
                
        except Exception as e:
            logger.error(f"Error getting user ratings: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def ban_user(self, user_id: int, admin_id: int, reason: str, 
                description: Optional[str] = None, ban_type: str = 'temporary',
                duration_hours: Optional[int] = 24) -> Dict[str, Any]:
        """حظر مستخدم"""
        try:
            with self.flask_app.app_context():
                # التحقق من عدم وجود حظر نشط
                existing_ban = UserBan.query.filter_by(
                    user_id=user_id,
                    is_active=True
                ).first()
                
                if existing_ban and not existing_ban.is_expired():
                    return {'success': False, 'error': 'User is already banned'}
                
                # حساب تاريخ انتهاء الحظر
                expires_at = None
                if ban_type == 'temporary' and duration_hours:
                    expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
                
                # إنشاء الحظر
                ban = UserBan(
                    user_id=user_id,
                    banned_by=admin_id,
                    reason=reason,
                    description=description,
                    ban_type=ban_type,
                    expires_at=expires_at
                )
                
                db.session.add(ban)
                db.session.commit()
                
                # تسجيل الحدث
                self.log_security_event(
                    user_id=admin_id,
                    event_type='user_banned',
                    description=f'Admin banned user {user_id} for {reason}',
                    severity='warning'
                )
                
                return {
                    'success': True,
                    'message': f'User banned successfully ({ban_type})'
                }
                
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def lift_ban(self, ban_id: int, admin_id: int, reason: str) -> Dict[str, Any]:
        """رفع الحظر"""
        try:
            with self.flask_app.app_context():
                ban = UserBan.query.get(ban_id)
                if not ban:
                    return {'success': False, 'error': 'Ban not found'}
                
                if not ban.is_active:
                    return {'success': False, 'error': 'Ban is not active'}
                
                # رفع الحظر
                ban.is_active = False
                ban.lifted_by = admin_id
                ban.lifted_at = datetime.utcnow()
                ban.lift_reason = reason
                
                db.session.commit()
                
                # تسجيل الحدث
                self.log_security_event(
                    user_id=admin_id,
                    event_type='ban_lifted',
                    description=f'Admin lifted ban for user {ban.user_id}',
                    severity='info'
                )
                
                return {
                    'success': True,
                    'message': 'Ban lifted successfully'
                }
                
        except Exception as e:
            logger.error(f"Error lifting ban: {e}")
            return {'success': False, 'error': 'Internal server error'}
    
    def is_user_banned(self, user_id: int) -> bool:
        """فحص ما إذا كان المستخدم محظور"""
        try:
            with self.flask_app.app_context():
                active_ban = UserBan.query.filter_by(
                    user_id=user_id,
                    is_active=True
                ).first()
                
                if not active_ban:
                    return False
                
                # فحص انتهاء صلاحية الحظر
                if active_ban.is_expired():
                    active_ban.is_active = False
                    db.session.commit()
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error checking user ban status: {e}")
            return False
    
    def log_security_event(self, user_id: int, event_type: str, description: str,
                          severity: str = 'info', ip_address: Optional[str] = None,
                          user_agent: Optional[str] = None, additional_data: Optional[str] = None):
        """تسجيل حدث أمني"""
        try:
            with self.flask_app.app_context():
                security_log = SecurityLog(
                    user_id=user_id,
                    event_type=event_type,
                    description=description,
                    severity=severity,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    additional_data=additional_data
                )
                
                db.session.add(security_log)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
    
    def detect_suspicious_activity(self, user_id: int) -> Dict[str, Any]:
        """كشف النشاط المشبوه"""
        try:
            with self.flask_app.app_context():
                # فحص عدد النزاعات في آخر 30 يوم
                month_ago = datetime.utcnow() - timedelta(days=30)
                
                disputes_count = Dispute.query.filter(
                    (Dispute.reporter_id == user_id) | (Dispute.reported_id == user_id),
                    Dispute.created_at >= month_ago
                ).count()
                
                # فحص معدل التقييمات السيئة
                bad_ratings = UserRating.query.filter(
                    UserRating.rated_id == user_id,
                    UserRating.rating <= 2
                ).count()
                
                total_ratings = UserRating.query.filter_by(rated_id=user_id).count()
                bad_rating_ratio = bad_ratings / max(total_ratings, 1)
                
                # فحص الصفقات الملغاة
                cancelled_deals = Deal.query.filter(
                    (Deal.seller_id == user_id) | (Deal.buyer_id == user_id),
                    Deal.status == 'cancelled',
                    Deal.created_at >= month_ago
                ).count()
                
                # تحديد مستوى المخاطر
                risk_level = 'low'
                risk_factors = []
                
                if disputes_count >= 3:
                    risk_level = 'high'
                    risk_factors.append(f'Multiple disputes ({disputes_count})')
                
                if bad_rating_ratio >= 0.5 and total_ratings >= 5:
                    risk_level = 'high'
                    risk_factors.append(f'High bad rating ratio ({bad_rating_ratio:.2f})')
                
                if cancelled_deals >= 5:
                    risk_level = 'medium'
                    risk_factors.append(f'Multiple cancelled deals ({cancelled_deals})')
                
                return {
                    'user_id': user_id,
                    'risk_level': risk_level,
                    'risk_factors': risk_factors,
                    'disputes_count': disputes_count,
                    'bad_rating_ratio': bad_rating_ratio,
                    'cancelled_deals': cancelled_deals
                }
                
        except Exception as e:
            logger.error(f"Error detecting suspicious activity: {e}")
            return {'error': str(e)}
    
    def get_dispute_statistics(self) -> Dict[str, Any]:
        """الحصول على إحصائيات النزاعات"""
        try:
            with self.flask_app.app_context():
                total_disputes = Dispute.query.count()
                open_disputes = Dispute.query.filter_by(status='open').count()
                resolved_disputes = Dispute.query.filter_by(status='resolved').count()
                
                # إحصائيات الأسباب
                reason_stats = {}
                for reason_key, reason_name in self.dispute_reasons.items():
                    count = Dispute.query.filter_by(reason=reason_key).count()
                    reason_stats[reason_name] = count
                
                return {
                    'total_disputes': total_disputes,
                    'open_disputes': open_disputes,
                    'resolved_disputes': resolved_disputes,
                    'reason_statistics': reason_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting dispute statistics: {e}")
            return {'error': str(e)}

