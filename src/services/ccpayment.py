import os
import json
import time
import hashlib
import hmac
import requests
from typing import Dict, Any, Optional

class CCPaymentService:
    """خدمة التكامل مع CCPayment API"""
    
    def __init__(self, app_id: str, app_secret: str, base_url: str = "https://ccpayment.com"):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url
        self.api_url = f"{base_url}/ccpayment/v1"
        
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """توليد التوقيع المطلوب للـ API"""
        # ترتيب المعاملات أبجدياً
        sorted_params = sorted(params.items())
        
        # إنشاء query string
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        # إضافة app_secret
        sign_string = f"{query_string}&{self.app_secret}"
        
        # إنشاء SHA256 hash
        signature = hashlib.sha256(sign_string.encode()).hexdigest()
        
        return signature
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """إرسال طلب إلى CCPayment API"""
        # إضافة معاملات أساسية
        data['appId'] = self.app_id
        data['timestamp'] = int(time.time())
        
        # توليد التوقيع
        signature = self._generate_signature(data)
        data['sign'] = signature
        
        # إرسال الطلب
        url = f"{self.api_url}/{endpoint}"
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'OTC-Bot/1.0'
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"CCPayment API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from CCPayment: {str(e)}")
    
    def create_deposit_address(self, order_id: str, coin_id: int, amount: float, 
                             fiat_id: Optional[int] = None) -> Dict[str, Any]:
        """إنشاء عنوان إيداع لصفقة محددة"""
        data = {
            'orderId': order_id,
            'coinId': coin_id,
            'price': str(amount)
        }
        
        if fiat_id:
            data['fiatId'] = fiat_id
        
        try:
            result = self._make_request('merchant/createDepositAddress', data)
            
            if result.get('code') == 10000:  # نجح الطلب
                return {
                    'success': True,
                    'data': result.get('data', {}),
                    'address': result.get('data', {}).get('address'),
                    'amount': result.get('data', {}).get('amount'),
                    'coin_name': result.get('data', {}).get('coinName'),
                    'network': result.get('data', {}).get('network')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', 'Unknown error'),
                    'code': result.get('code')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_checkout_page(self, order_id: str, amount: float, 
                           return_url: str = None, cancel_url: str = None) -> Dict[str, Any]:
        """إنشاء صفحة دفع حيث يختار العميل العملة"""
        data = {
            'orderId': order_id,
            'price': str(amount)
        }
        
        if return_url:
            data['returnUrl'] = return_url
        if cancel_url:
            data['cancelUrl'] = cancel_url
        
        try:
            result = self._make_request('merchant/createCheckoutPage', data)
            
            if result.get('code') == 10000:
                return {
                    'success': True,
                    'data': result.get('data', {}),
                    'checkout_url': result.get('data', {}).get('checkoutUrl'),
                    'order_id': result.get('data', {}).get('orderId')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', 'Unknown error'),
                    'code': result.get('code')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_deposit_record(self, order_id: str) -> Dict[str, Any]:
        """الحصول على سجل الإيداع لصفقة محددة"""
        data = {
            'orderId': order_id
        }
        
        try:
            result = self._make_request('merchant/getDepositRecord', data)
            
            if result.get('code') == 10000:
                return {
                    'success': True,
                    'data': result.get('data', {}),
                    'status': result.get('data', {}).get('status'),
                    'amount': result.get('data', {}).get('amount'),
                    'tx_id': result.get('data', {}).get('txId')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', 'Unknown error'),
                    'code': result.get('code')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_withdrawal(self, coin_id: int, chain: str, address: str, 
                         amount: float, order_id: str) -> Dict[str, Any]:
        """إنشاء طلب سحب (إرسال أموال للبائع)"""
        data = {
            'coinId': coin_id,
            'chain': chain,
            'address': address,
            'amount': str(amount),
            'orderId': order_id
        }
        
        try:
            result = self._make_request('merchant/createNetworkWithdrawal', data)
            
            if result.get('code') == 10000:
                return {
                    'success': True,
                    'data': result.get('data', {}),
                    'withdrawal_id': result.get('data', {}).get('withdrawalId'),
                    'status': result.get('data', {}).get('status')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', 'Unknown error'),
                    'code': result.get('code')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_webhook(self, data: Dict[str, Any], signature: str) -> bool:
        """التحقق من صحة webhook من CCPayment"""
        try:
            # إعادة إنشاء التوقيع
            expected_signature = self._generate_signature(data)
            
            # مقارنة التوقيعات
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception:
            return False
    
    def get_supported_coins(self) -> Dict[str, Any]:
        """الحصول على قائمة العملات المدعومة"""
        try:
            # هذا endpoint قد يختلف حسب وثائق CCPayment
            result = self._make_request('common/getCoinList', {})
            
            if result.get('code') == 10000:
                return {
                    'success': True,
                    'coins': result.get('data', [])
                }
            else:
                return {
                    'success': False,
                    'error': result.get('msg', 'Unknown error')
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# إعدادات افتراضية للعملات الشائعة
DEFAULT_COINS = {
    'USDT': {
        'coin_id': 1280,  # قد تحتاج لتحديث هذا حسب CCPayment
        'networks': ['POLYGON', 'ETH', 'BSC', 'TRX']
    },
    'BTC': {
        'coin_id': 1,
        'networks': ['BTC']
    },
    'ETH': {
        'coin_id': 2,
        'networks': ['ETH']
    }
}

def get_ccpayment_service() -> CCPaymentService:
    """إنشاء instance من خدمة CCPayment"""
    app_id = os.getenv('CCPAYMENT_APP_ID', 'your_app_id_here')
    app_secret = os.getenv('CCPAYMENT_APP_SECRET', 'your_app_secret_here')
    
    if app_id == 'your_app_id_here' or app_secret == 'your_app_secret_here':
        raise Exception("CCPayment credentials not configured. Please set CCPAYMENT_APP_ID and CCPAYMENT_APP_SECRET environment variables.")
    
    return CCPaymentService(app_id, app_secret)

