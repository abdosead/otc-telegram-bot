from flask import Blueprint, request, jsonify
import logging
from models.dispute import Dispute, UserRating, SecurityLog, UserBan, db
from services.dispute_manager import DisputeManager

disputes_bp = Blueprint('disputes', __name__)
logger = logging.getLogger(__name__)

# متغير عام لمدير النزاعات
dispute_manager = None

def set_dispute_manager(manager):
    """تعيين مدير النزاعات"""
    global dispute_manager
    dispute_manager = manager

@disputes_bp.route('/disputes', methods=['POST'])
def create_dispute():
    """إنشاء نزاع جديد"""
    try:
        data = request.get_json()
        
        required_fields = ['deal_id', 'reporter_id', 'reason', 'description']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.create_dispute(
            deal_id=data['deal_id'],
            reporter_id=data['reporter_id'],
            reason=data['reason'],
            description=data['description'],
            evidence=data.get('evidence')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating dispute: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/disputes/<dispute_id>', methods=['GET'])
def get_dispute(dispute_id):
    """الحصول على تفاصيل نزاع"""
    try:
        dispute = Dispute.query.get(dispute_id)
        if not dispute:
            return jsonify({'success': False, 'error': 'Dispute not found'}), 404
        
        return jsonify({
            'success': True,
            'dispute': dispute.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting dispute: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/disputes', methods=['GET'])
def get_disputes():
    """الحصول على قائمة النزاعات"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        
        query = Dispute.query
        
        if status:
            query = query.filter_by(status=status)
        
        disputes = query.order_by(Dispute.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'disputes': [dispute.to_dict() for dispute in disputes.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': disputes.total,
                'pages': disputes.pages
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting disputes: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/disputes/<dispute_id>/resolve', methods=['POST'])
def resolve_dispute(dispute_id):
    """حل نزاع"""
    try:
        data = request.get_json()
        
        required_fields = ['admin_id', 'resolution']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.resolve_dispute(
            dispute_id=dispute_id,
            admin_id=data['admin_id'],
            resolution=data['resolution'],
            winner_id=data.get('winner_id')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error resolving dispute: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/ratings', methods=['POST'])
def add_rating():
    """إضافة تقييم"""
    try:
        data = request.get_json()
        
        required_fields = ['deal_id', 'rater_id', 'rated_id', 'rating']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.add_user_rating(
            deal_id=data['deal_id'],
            rater_id=data['rater_id'],
            rated_id=data['rated_id'],
            rating=data['rating'],
            comment=data.get('comment')
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error adding rating: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/users/<int:user_id>/ratings', methods=['GET'])
def get_user_ratings(user_id):
    """الحصول على تقييمات المستخدم"""
    try:
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.get_user_ratings(user_id)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting user ratings: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/bans', methods=['POST'])
def ban_user():
    """حظر مستخدم"""
    try:
        data = request.get_json()
        
        required_fields = ['user_id', 'admin_id', 'reason']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.ban_user(
            user_id=data['user_id'],
            admin_id=data['admin_id'],
            reason=data['reason'],
            description=data.get('description'),
            ban_type=data.get('ban_type', 'temporary'),
            duration_hours=data.get('duration_hours', 24)
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error banning user: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/bans/<int:ban_id>/lift', methods=['POST'])
def lift_ban(ban_id):
    """رفع الحظر"""
    try:
        data = request.get_json()
        
        required_fields = ['admin_id', 'reason']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.lift_ban(
            ban_id=ban_id,
            admin_id=data['admin_id'],
            reason=data['reason']
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error lifting ban: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/users/<int:user_id>/ban-status', methods=['GET'])
def check_ban_status(user_id):
    """فحص حالة حظر المستخدم"""
    try:
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        is_banned = dispute_manager.is_user_banned(user_id)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'is_banned': is_banned
        })
        
    except Exception as e:
        logger.error(f"Error checking ban status: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/users/<int:user_id>/suspicious-activity', methods=['GET'])
def check_suspicious_activity(user_id):
    """فحص النشاط المشبوه للمستخدم"""
    try:
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        result = dispute_manager.detect_suspicious_activity(user_id)
        
        return jsonify({
            'success': True,
            'analysis': result
        })
        
    except Exception as e:
        logger.error(f"Error checking suspicious activity: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/security-logs', methods=['GET'])
def get_security_logs():
    """الحصول على سجلات الأمان"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        severity = request.args.get('severity')
        event_type = request.args.get('event_type')
        
        query = SecurityLog.query
        
        if severity:
            query = query.filter_by(severity=severity)
        if event_type:
            query = query.filter_by(event_type=event_type)
        
        logs = query.order_by(SecurityLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'logs': [log.to_dict() for log in logs.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': logs.total,
                'pages': logs.pages
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting security logs: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/statistics', methods=['GET'])
def get_dispute_statistics():
    """الحصول على إحصائيات النزاعات"""
    try:
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        stats = dispute_manager.get_dispute_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting dispute statistics: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@disputes_bp.route('/reasons', methods=['GET'])
def get_dispute_reasons():
    """الحصول على أسباب النزاعات المتاحة"""
    try:
        if not dispute_manager:
            return jsonify({'success': False, 'error': 'Dispute manager not available'}), 503
        
        return jsonify({
            'success': True,
            'reasons': dispute_manager.dispute_reasons
        })
        
    except Exception as e:
        logger.error(f"Error getting dispute reasons: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

