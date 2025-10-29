from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Dispute(db.Model):
    """نموذج النزاعات"""
    __tablename__ = 'disputes'
    
    id = db.Column(db.String(36), primary_key=True)
    deal_id = db.Column(db.String(36), db.ForeignKey('deals.id'), nullable=False)
    reporter_id = db.Column(db.Integer, nullable=False)  # من فتح النزاع
    reported_id = db.Column(db.Integer, nullable=False)  # المبلغ عنه
    
    # تفاصيل النزاع
    reason = db.Column(db.String(50), nullable=False)  # سبب النزاع
    description = db.Column(db.Text, nullable=False)  # وصف مفصل
    evidence = db.Column(db.Text)  # أدلة (روابط صور، ملفات، إلخ)
    
    # حالة النزاع
    status = db.Column(db.String(20), default='open')  # open, investigating, resolved, closed
    priority = db.Column(db.String(10), default='medium')  # low, medium, high, urgent
    
    # معلومات الحل
    resolution = db.Column(db.Text)  # تفاصيل الحل
    resolved_by = db.Column(db.Integer)  # معرف المشرف الذي حل النزاع
    resolved_at = db.Column(db.DateTime)
    
    # معلومات إضافية
    admin_notes = db.Column(db.Text)  # ملاحظات المشرف
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, id, deal_id, reporter_id, reported_id, reason, description, evidence=None):
        self.id = id
        self.deal_id = deal_id
        self.reporter_id = reporter_id
        self.reported_id = reported_id
        self.reason = reason
        self.description = description
        self.evidence = evidence
    
    def to_dict(self):
        """تحويل النزاع إلى قاموس"""
        return {
            'id': self.id,
            'deal_id': self.deal_id,
            'reporter_id': self.reporter_id,
            'reported_id': self.reported_id,
            'reason': self.reason,
            'description': self.description,
            'evidence': self.evidence,
            'status': self.status,
            'priority': self.priority,
            'resolution': self.resolution,
            'resolved_by': self.resolved_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'admin_notes': self.admin_notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UserRating(db.Model):
    """نموذج تقييمات المستخدمين"""
    __tablename__ = 'user_ratings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deal_id = db.Column(db.String(36), db.ForeignKey('deals.id'), nullable=False)
    rater_id = db.Column(db.Integer, nullable=False)  # من قام بالتقييم
    rated_id = db.Column(db.Integer, nullable=False)  # المقيم
    
    # التقييم
    rating = db.Column(db.Integer, nullable=False)  # من 1 إلى 5
    comment = db.Column(db.Text)  # تعليق اختياري
    
    # معلومات إضافية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, deal_id, rater_id, rated_id, rating, comment=None):
        self.deal_id = deal_id
        self.rater_id = rater_id
        self.rated_id = rated_id
        self.rating = rating
        self.comment = comment
    
    def to_dict(self):
        """تحويل التقييم إلى قاموس"""
        return {
            'id': self.id,
            'deal_id': self.deal_id,
            'rater_id': self.rater_id,
            'rated_id': self.rated_id,
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat()
        }

class SecurityLog(db.Model):
    """نموذج سجل الأمان"""
    __tablename__ = 'security_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    
    # نوع الحدث
    event_type = db.Column(db.String(50), nullable=False)  # login, suspicious_activity, fraud_attempt, etc.
    severity = db.Column(db.String(10), default='info')  # info, warning, error, critical
    
    # تفاصيل الحدث
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45))  # IPv4 أو IPv6
    user_agent = db.Column(db.Text)
    additional_data = db.Column(db.Text)  # JSON data
    
    # معلومات إضافية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, event_type, description, severity='info', ip_address=None, user_agent=None, additional_data=None):
        self.user_id = user_id
        self.event_type = event_type
        self.description = description
        self.severity = severity
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.additional_data = additional_data
    
    def to_dict(self):
        """تحويل السجل إلى قاموس"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'severity': self.severity,
            'description': self.description,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'additional_data': self.additional_data,
            'created_at': self.created_at.isoformat()
        }

class UserBan(db.Model):
    """نموذج حظر المستخدمين"""
    __tablename__ = 'user_bans'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    banned_by = db.Column(db.Integer, nullable=False)  # معرف المشرف
    
    # تفاصيل الحظر
    reason = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    ban_type = db.Column(db.String(20), default='temporary')  # temporary, permanent
    
    # مدة الحظر
    banned_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # null للحظر الدائم
    
    # حالة الحظر
    is_active = db.Column(db.Boolean, default=True)
    lifted_by = db.Column(db.Integer)  # من رفع الحظر
    lifted_at = db.Column(db.DateTime)
    lift_reason = db.Column(db.Text)
    
    def __init__(self, user_id, banned_by, reason, description=None, ban_type='temporary', expires_at=None):
        self.user_id = user_id
        self.banned_by = banned_by
        self.reason = reason
        self.description = description
        self.ban_type = ban_type
        self.expires_at = expires_at
    
    def is_expired(self):
        """فحص انتهاء صلاحية الحظر"""
        if self.ban_type == 'permanent' or not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self):
        """تحويل الحظر إلى قاموس"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'banned_by': self.banned_by,
            'reason': self.reason,
            'description': self.description,
            'ban_type': self.ban_type,
            'banned_at': self.banned_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'lifted_by': self.lifted_by,
            'lifted_at': self.lifted_at.isoformat() if self.lifted_at else None,
            'lift_reason': self.lift_reason
        }

