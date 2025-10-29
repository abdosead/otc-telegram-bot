from flask import Blueprint, request, jsonify
from models.deal import Deal, db
from models.telegram_user import TelegramUser

deals_bp = Blueprint('deals', __name__)

@deals_bp.route('/deals', methods=['GET'])
def get_all_deals():
    """الحصول على جميع الصفقات"""
    try:
        deals = Deal.query.all()
        return jsonify({
            'success': True,
            'deals': [deal.to_dict() for deal in deals]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@deals_bp.route('/deals/<deal_id>', methods=['GET'])
def get_deal_details(deal_id):
    """الحصول على تفاصيل صفقة محددة"""
    try:
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        # الحصول على بيانات البائع
        seller = TelegramUser.query.filter_by(telegram_id=deal.seller_id).first()
        buyer = None
        if deal.buyer_id:
            buyer = TelegramUser.query.filter_by(telegram_id=deal.buyer_id).first()
        
        deal_data = deal.to_dict()
        deal_data['seller_info'] = seller.to_dict() if seller else None
        deal_data['buyer_info'] = buyer.to_dict() if buyer else None
        
        return jsonify({
            'success': True,
            'deal': deal_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@deals_bp.route('/deals/<deal_id>/status', methods=['PUT'])
def update_deal_status(deal_id):
    """تحديث حالة الصفقة"""
    try:
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'success': False, 'error': 'Status is required'}), 400
        
        # تحديث الحالة
        deal.status = data['status']
        
        # تحديث معرف المشتري إذا تم توفيره
        if 'buyer_id' in data:
            deal.buyer_id = data['buyer_id']
        
        # تحديث معرف الدفعة إذا تم توفيره
        if 'payment_id' in data:
            deal.payment_id = data['payment_id']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deal': deal.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@deals_bp.route('/deals/user/<int:user_id>', methods=['GET'])
def get_user_deals(user_id):
    """الحصول على صفقات مستخدم محدد"""
    try:
        # صفقات كبائع
        seller_deals = Deal.query.filter_by(seller_id=user_id).all()
        # صفقات كمشتري
        buyer_deals = Deal.query.filter_by(buyer_id=user_id).all()
        
        return jsonify({
            'success': True,
            'seller_deals': [deal.to_dict() for deal in seller_deals],
            'buyer_deals': [deal.to_dict() for deal in buyer_deals]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@deals_bp.route('/deals/<deal_id>/confirm_payment', methods=['POST'])
def confirm_payment(deal_id):
    """تأكيد الدفع من المشتري"""
    try:
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        data = request.get_json()
        buyer_id = data.get('buyer_id')
        payment_id = data.get('payment_id')
        
        if not buyer_id:
            return jsonify({'success': False, 'error': 'Buyer ID is required'}), 400
        
        # تحديث حالة الصفقة
        deal.buyer_id = buyer_id
        deal.status = 'paid'
        if payment_id:
            deal.payment_id = payment_id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment confirmed successfully',
            'deal': deal.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@deals_bp.route('/deals/<deal_id>/release_funds', methods=['POST'])
def release_funds(deal_id):
    """تحرير الأموال من المشتري"""
    try:
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        data = request.get_json()
        buyer_id = data.get('buyer_id')
        
        if not buyer_id or deal.buyer_id != buyer_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        if deal.status != 'confirmed':
            return jsonify({'success': False, 'error': 'Deal must be confirmed first'}), 400
        
        # تحديث حالة الصفقة
        deal.status = 'completed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Funds released successfully',
            'deal': deal.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@deals_bp.route('/deals/<deal_id>/dispute', methods=['POST'])
def create_dispute(deal_id):
    """فتح نزاع على الصفقة"""
    try:
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        data = request.get_json()
        user_id = data.get('user_id')
        reason = data.get('reason', '')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'User ID is required'}), 400
        
        # التحقق من أن المستخدم طرف في الصفقة
        if user_id != deal.seller_id and user_id != deal.buyer_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # تحديث حالة الصفقة
        deal.status = 'disputed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Dispute created successfully',
            'deal': deal.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

