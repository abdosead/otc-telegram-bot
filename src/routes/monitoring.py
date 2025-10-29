from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta
from models.deal import Deal, db
from models.telegram_user import TelegramUser
from services.payment_monitor import PaymentMonitor
from sqlalchemy import func

monitoring_bp = Blueprint('monitoring', __name__)
logger = logging.getLogger(__name__)

# متغير عام لمراقب المدفوعات
payment_monitor = None

def set_payment_monitor(monitor):
    """تعيين مراقب المدفوعات"""
    global payment_monitor
    payment_monitor = monitor

@monitoring_bp.route('/monitoring/stats', methods=['GET'])
def get_monitoring_stats():
    """الحصول على إحصائيات المراقبة"""
    try:
        if payment_monitor:
            stats = payment_monitor.get_monitoring_stats()
        else:
            stats = {'error': 'Payment monitor not initialized'}
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting monitoring stats: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@monitoring_bp.route('/monitoring/deals', methods=['GET'])
def get_deals_stats():
    """الحصول على إحصائيات الصفقات"""
    try:
        # إحصائيات عامة
        total_deals = Deal.query.count()
        pending_deals = Deal.query.filter_by(status='pending').count()
        paid_deals = Deal.query.filter_by(status='paid').count()
        completed_deals = Deal.query.filter_by(status='completed').count()
        disputed_deals = Deal.query.filter_by(status='disputed').count()
        cancelled_deals = Deal.query.filter_by(status='cancelled').count()
        
        # إحصائيات مالية
        total_volume = db.session.query(func.sum(Deal.total_price)).filter(
            Deal.status.in_(['completed', 'paid'])
        ).scalar() or 0
        
        total_commission = db.session.query(func.sum(Deal.commission)).filter(
            Deal.status == 'completed'
        ).scalar() or 0
        
        # إحصائيات يومية (آخر 7 أيام)
        week_ago = datetime.utcnow() - timedelta(days=7)
        daily_stats = []
        
        for i in range(7):
            day = week_ago + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_deals = Deal.query.filter(
                Deal.created_at >= day_start,
                Deal.created_at < day_end
            ).count()
            
            day_volume = db.session.query(func.sum(Deal.total_price)).filter(
                Deal.created_at >= day_start,
                Deal.created_at < day_end,
                Deal.status.in_(['completed', 'paid'])
            ).scalar() or 0
            
            daily_stats.append({
                'date': day.strftime('%Y-%m-%d'),
                'deals': day_deals,
                'volume': float(day_volume)
            })
        
        # أفضل البائعين
        top_sellers = db.session.query(
            Deal.seller_id,
            func.count(Deal.id).label('deals_count'),
            func.sum(Deal.price).label('total_sales')
        ).filter(
            Deal.status == 'completed'
        ).group_by(Deal.seller_id).order_by(
            func.count(Deal.id).desc()
        ).limit(10).all()
        
        top_sellers_data = []
        for seller_id, deals_count, total_sales in top_sellers:
            user = TelegramUser.query.get(seller_id)
            top_sellers_data.append({
                'user_id': seller_id,
                'username': user.username if user else 'Unknown',
                'deals_count': deals_count,
                'total_sales': float(total_sales or 0)
            })
        
        stats = {
            'overview': {
                'total_deals': total_deals,
                'pending_deals': pending_deals,
                'paid_deals': paid_deals,
                'completed_deals': completed_deals,
                'disputed_deals': disputed_deals,
                'cancelled_deals': cancelled_deals,
                'total_volume': float(total_volume),
                'total_commission': float(total_commission)
            },
            'daily_stats': daily_stats,
            'top_sellers': top_sellers_data
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting deals stats: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@monitoring_bp.route('/monitoring/users', methods=['GET'])
def get_users_stats():
    """الحصول على إحصائيات المستخدمين"""
    try:
        total_users = TelegramUser.query.count()
        
        # المستخدمين النشطين (لهم صفقات في آخر 30 يوم)
        month_ago = datetime.utcnow() - timedelta(days=30)
        active_users = db.session.query(TelegramUser.id).join(Deal, 
            (TelegramUser.id == Deal.seller_id) | (TelegramUser.id == Deal.buyer_id)
        ).filter(Deal.created_at >= month_ago).distinct().count()
        
        # المستخدمين الجدد (آخر 7 أيام)
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users = TelegramUser.query.filter(
            TelegramUser.created_at >= week_ago
        ).count()
        
        # إحصائيات التسجيل اليومية
        daily_registrations = []
        for i in range(7):
            day = week_ago + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            day_registrations = TelegramUser.query.filter(
                TelegramUser.created_at >= day_start,
                TelegramUser.created_at < day_end
            ).count()
            
            daily_registrations.append({
                'date': day.strftime('%Y-%m-%d'),
                'registrations': day_registrations
            })
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'new_users': new_users,
            'daily_registrations': daily_registrations
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting users stats: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@monitoring_bp.route('/monitoring/force-check/<deal_id>', methods=['POST'])
def force_check_payment(deal_id):
    """فحص دفع صفقة محددة فوراً"""
    try:
        if not payment_monitor:
            return jsonify({'success': False, 'error': 'Payment monitor not available'}), 503
        
        # تشغيل الفحص في الخلفية
        import asyncio
        
        async def check_deal():
            return await payment_monitor.force_check_deal(deal_id)
        
        # تشغيل المهمة غير المتزامنة
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(check_deal())
        loop.close()
        
        if result:
            return jsonify({
                'success': True,
                'message': f'Payment check initiated for deal {deal_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Deal not found or check failed'
            }), 404
            
    except Exception as e:
        logger.error(f"Error force checking payment: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@monitoring_bp.route('/monitoring/recent-activity', methods=['GET'])
def get_recent_activity():
    """الحصول على النشاط الأخير"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        # أحدث الصفقات
        recent_deals = Deal.query.order_by(Deal.created_at.desc()).limit(limit).all()
        
        activity = []
        for deal in recent_deals:
            seller = TelegramUser.query.get(deal.seller_id)
            buyer = TelegramUser.query.get(deal.buyer_id) if deal.buyer_id else None
            
            activity.append({
                'id': deal.id,
                'type': 'deal',
                'title': deal.title,
                'status': deal.status,
                'price': float(deal.total_price),
                'seller': seller.username if seller else 'Unknown',
                'buyer': buyer.username if buyer else None,
                'created_at': deal.created_at.isoformat(),
                'updated_at': deal.updated_at.isoformat() if deal.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'activity': activity
        })
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@monitoring_bp.route('/monitoring/health', methods=['GET'])
def health_check():
    """فحص صحة النظام"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'payment_monitor': 'running' if payment_monitor and payment_monitor.is_running else 'stopped',
            'services': {
                'ccpayment': 'unknown',  # سيتم تحديثه بناءً على آخر فحص
                'telegram_bot': 'unknown'
            }
        }
        
        # فحص قاعدة البيانات
        try:
            db.session.execute('SELECT 1')
            health_status['database'] = 'connected'
        except:
            health_status['database'] = 'disconnected'
            health_status['status'] = 'unhealthy'
        
        # فحص مراقب المدفوعات
        if payment_monitor:
            monitor_stats = payment_monitor.get_monitoring_stats()
            health_status['services']['ccpayment'] = monitor_stats.get('ccpayment_status', 'unknown')
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

