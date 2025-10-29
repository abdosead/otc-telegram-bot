from flask import Blueprint, request, jsonify
import json
import logging
from models.deal import Deal, db
from models.telegram_user import TelegramUser
from services.ccpayment import get_ccpayment_service, DEFAULT_COINS

payments_bp = Blueprint('payments', __name__)
logger = logging.getLogger(__name__)

@payments_bp.route('/payments/create', methods=['POST'])
def create_payment():
    """إنشاء عنوان دفع لصفقة"""
    try:
        data = request.get_json()
        deal_id = data.get('deal_id')
        coin_type = data.get('coin_type', 'USDT')  # افتراضي USDT
        network = data.get('network', 'POLYGON')  # افتراضي Polygon
        
        if not deal_id:
            return jsonify({'success': False, 'error': 'Deal ID is required'}), 400
        
        # الحصول على الصفقة
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        if deal.status != 'pending':
            return jsonify({'success': False, 'error': 'Deal is not available for payment'}), 400
        
        # الحصول على معلومات العملة
        coin_info = DEFAULT_COINS.get(coin_type)
        if not coin_info:
            return jsonify({'success': False, 'error': 'Unsupported coin type'}), 400
        
        if network not in coin_info['networks']:
            return jsonify({'success': False, 'error': 'Unsupported network for this coin'}), 400
        
        # إنشاء عنوان الدفع
        ccpayment = get_ccpayment_service()
        result = ccpayment.create_deposit_address(
            order_id=deal_id,
            coin_id=coin_info['coin_id'],
            amount=deal.total_price
        )
        
        if result['success']:
            # تحديث الصفقة بمعلومات الدفع
            payment_info = {
                'address': result['address'],
                'amount': result['amount'],
                'coin_name': result['coin_name'],
                'network': result['network'],
                'coin_type': coin_type
            }
            
            deal.payment_id = json.dumps(payment_info)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'payment_info': payment_info,
                'deal_id': deal_id
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@payments_bp.route('/payments/checkout', methods=['POST'])
def create_checkout():
    """إنشاء صفحة دفع مع خيار اختيار العملة"""
    try:
        data = request.get_json()
        deal_id = data.get('deal_id')
        
        if not deal_id:
            return jsonify({'success': False, 'error': 'Deal ID is required'}), 400
        
        # الحصول على الصفقة
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        if deal.status != 'pending':
            return jsonify({'success': False, 'error': 'Deal is not available for payment'}), 400
        
        # إنشاء صفحة الدفع
        ccpayment = get_ccpayment_service()
        result = ccpayment.create_checkout_page(
            order_id=deal_id,
            amount=deal.total_price,
            return_url=f"https://t.me/{request.host}/success",
            cancel_url=f"https://t.me/{request.host}/cancel"
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'checkout_url': result['checkout_url'],
                'deal_id': deal_id
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating checkout: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@payments_bp.route('/payments/status/<deal_id>', methods=['GET'])
def check_payment_status(deal_id):
    """التحقق من حالة الدفع"""
    try:
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        # التحقق من حالة الدفع عبر CCPayment
        ccpayment = get_ccpayment_service()
        result = ccpayment.get_deposit_record(deal_id)
        
        if result['success']:
            payment_status = result.get('status', 'unknown')
            
            # تحديث حالة الصفقة حسب حالة الدفع
            if payment_status == 'success' and deal.status == 'pending':
                deal.status = 'paid'
                db.session.commit()
            
            return jsonify({
                'success': True,
                'payment_status': payment_status,
                'deal_status': deal.status,
                'amount': result.get('amount'),
                'tx_id': result.get('tx_id')
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@payments_bp.route('/payments/webhook', methods=['POST'])
def handle_webhook():
    """معالج webhook من CCPayment"""
    try:
        # الحصول على البيانات
        webhook_data = request.get_json()
        signature = request.headers.get('X-CC-Signature', '')
        
        if not webhook_data:
            return jsonify({'error': 'No data received'}), 400
        
        # التحقق من التوقيع
        ccpayment = get_ccpayment_service()
        if not ccpayment.verify_webhook(webhook_data, signature):
            logger.warning("Invalid webhook signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # معالجة البيانات
        order_id = webhook_data.get('orderId')
        status = webhook_data.get('status')
        amount = webhook_data.get('amount')
        tx_id = webhook_data.get('txId')
        
        if not order_id:
            return jsonify({'error': 'Order ID missing'}), 400
        
        # الحصول على الصفقة
        deal = Deal.query.get(order_id)
        if not deal:
            logger.warning(f"Deal not found for order_id: {order_id}")
            return jsonify({'error': 'Deal not found'}), 404
        
        # تحديث حالة الصفقة
        if status == 'success':
            if deal.status == 'pending':
                deal.status = 'paid'
                
                # تحديث معلومات المعاملة
                if deal.payment_id:
                    try:
                        payment_info = json.loads(deal.payment_id)
                        payment_info['tx_id'] = tx_id
                        payment_info['confirmed_amount'] = amount
                        deal.payment_id = json.dumps(payment_info)
                    except:
                        pass
                
                db.session.commit()
                
                # إرسال إشعار للبوت (يمكن تطويره لاحقاً)
                logger.info(f"Payment confirmed for deal {order_id}")
                
        elif status == 'failed':
            logger.info(f"Payment failed for deal {order_id}")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@payments_bp.route('/payments/withdraw', methods=['POST'])
def create_withdrawal():
    """إنشاء طلب سحب للبائع"""
    try:
        data = request.get_json()
        deal_id = data.get('deal_id')
        seller_address = data.get('seller_address')
        coin_type = data.get('coin_type', 'USDT')
        network = data.get('network', 'POLYGON')
        
        if not all([deal_id, seller_address]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        # الحصول على الصفقة
        deal = Deal.query.get(deal_id)
        if not deal:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        if deal.status != 'completed':
            return jsonify({'success': False, 'error': 'Deal is not completed'}), 400
        
        # الحصول على معلومات العملة
        coin_info = DEFAULT_COINS.get(coin_type)
        if not coin_info:
            return jsonify({'success': False, 'error': 'Unsupported coin type'}), 400
        
        # إنشاء طلب السحب (المبلغ بعد خصم العمولة)
        withdrawal_amount = deal.price  # المبلغ الأساسي بدون العمولة
        
        ccpayment = get_ccpayment_service()
        result = ccpayment.create_withdrawal(
            coin_id=coin_info['coin_id'],
            chain=network,
            address=seller_address,
            amount=withdrawal_amount,
            order_id=f"{deal_id}_withdrawal"
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'withdrawal_id': result['withdrawal_id'],
                'status': result['status'],
                'amount': withdrawal_amount
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Error creating withdrawal: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@payments_bp.route('/payments/coins', methods=['GET'])
def get_supported_coins():
    """الحصول على قائمة العملات المدعومة"""
    try:
        ccpayment = get_ccpayment_service()
        result = ccpayment.get_supported_coins()
        
        if result['success']:
            return jsonify({
                'success': True,
                'coins': result['coins'],
                'default_coins': DEFAULT_COINS
            })
        else:
            # في حالة فشل الحصول على القائمة من API، إرجاع القائمة الافتراضية
            return jsonify({
                'success': True,
                'coins': [],
                'default_coins': DEFAULT_COINS,
                'note': 'Using default coin list'
            })
            
    except Exception as e:
        logger.error(f"Error getting supported coins: {str(e)}")
        return jsonify({
            'success': True,
            'coins': [],
            'default_coins': DEFAULT_COINS,
            'note': 'Using default coin list due to API error'
        })

