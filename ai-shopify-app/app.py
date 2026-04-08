# -*- coding: utf-8 -*-
"""
AI Customer Service for Shopify Stores - 高级版本
功能：24/7自动客服、多语言支持、数据分析、错误恢复
作者：您的AI助手
"""

from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import requests
import os
import json
import time
from datetime import datetime, timedelta
import hashlib
from typing import Dict, List, Optional
import re

# ==================== 初始化 ====================
app = Flask(__name__)
CORS(app)  # 允许跨域请求
app.secret_key = os.getenv("SECRET_KEY", "ai-shopify-secret-key-2024")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# ==================== 配置 ====================
class Config:
    """系统配置"""
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-your-key-here")
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    
    # Shopify配置（未来集成用）
    SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY", "")
    SHOPIFY_PASSWORD = os.getenv("SHOPIFY_PASSWORD", "")
    SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "")
    
    # 系统设置
    MAX_TOKENS = 800  # AI回复最大长度
    TEMPERATURE = 0.7  # AI创造性 (0-1)
    TIMEOUT_SECONDS = 15  # API超时时间
    SESSION_EXPIRE_DAYS = 7  # 会话过期时间
    
    # 数据文件路径
    DATA_DIR = "data"
    CHATS_FILE = os.path.join(DATA_DIR, "chats.json")
    STATS_FILE = os.path.join(DATA_DIR, "stats.json")
    PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")

config = Config()

# ==================== 数据管理 ====================
class DataManager:
    """管理聊天数据和统计"""
    
    @staticmethod
    def ensure_data_dir():
        """确保数据目录存在"""
        if not os.path.exists(config.DATA_DIR):
            os.makedirs(config.DATA_DIR)
    
    @staticmethod
    def load_chats() -> Dict:
        """加载聊天记录"""
        DataManager.ensure_data_dir()
        if os.path.exists(config.CHATS_FILE):
            try:
                with open(config.CHATS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"chats": [], "total": 0}
        return {"chats": [], "total": 0}
    
    @staticmethod
    def save_chat(user_id: str, message: str, response: str, lang: str = "en"):
        """保存单条聊天记录"""
        DataManager.ensure_data_dir()
        chats_data = DataManager.load_chats()
        
        chat_record = {
            "id": hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:12],
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "message": message[:500],  # 限制长度
            "response": response[:1000],
            "language": lang,
            "length": len(message) + len(response)
        }
        
        chats_data["chats"].append(chat_record)
        chats_data["total"] = len(chats_data["chats"])
        
        # 只保留最近1000条记录
        if len(chats_data["chats"]) > 1000:
            chats_data["chats"] = chats_data["chats"][-1000:]
        
        with open(config.CHATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chats_data, f, ensure_ascii=False, indent=2)
        
        # 更新统计
        DataManager.update_stats(chat_record)
    
    @staticmethod
    def update_stats(chat_record: Dict):
        """更新统计数据"""
        DataManager.ensure_data_dir()
        
        if os.path.exists(config.STATS_FILE):
            with open(config.STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = {
                "total_chats": 0,
                "total_messages": 0,
                "total_words": 0,
                "languages": {"en": 0, "es": 0, "fr": 0, "de": 0, "zh": 0},
                "categories": {
                    "order": 0, "shipping": 0, "return": 0, 
                    "product": 0, "policy": 0, "other": 0
                },
                "response_times": [],
                "last_updated": datetime.now().isoformat()
            }
        
        # 更新基本统计
        stats["total_chats"] += 1
        stats["total_messages"] += 2  # 问题和回答
        stats["total_words"] += len(chat_record["message"].split()) + len(chat_record["response"].split())
        
        # 更新语言统计
        lang = chat_record.get("language", "en")
        if lang in stats["languages"]:
            stats["languages"][lang] += 1
        else:
            stats["languages"][lang] = 1
        
        # 更新分类统计（智能分类）
        category = DataManager.categorize_message(chat_record["message"])
        stats["categories"][category] += 1
        
        stats["last_updated"] = datetime.now().isoformat()
        
        with open(config.STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def categorize_message(message: str) -> str:
        """智能分类客户问题"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["order", "track", "delivery", "ship", "where is"]):
            return "order"
        elif any(word in message_lower for word in ["return", "refund", "exchange", "send back"]):
            return "return"
        elif any(word in message_lower for word in ["ship", "delivery", "shipping", "time", "cost"]):
            return "shipping"
        elif any(word in message_lower for word in ["product", "size", "color", "available", "stock"]):
            return "product"
        elif any(word in message_lower for word in ["policy", "hours", "contact", "store", "business"]):
            return "policy"
        else:
            return "other"

# ==================== AI对话引擎 ====================
class AIChatEngine:
    """AI对话引擎 - 处理所有AI对话"""
    
    # 多语言系统提示词
    SYSTEM_PROMPTS = {
        "en": """You are a professional e-commerce customer service assistant for Shopify stores.

CORE RESPONSIBILITIES:
1. ORDER MANAGEMENT: Check order status, provide tracking info, update delivery estimates
2. RETURN & REFUNDS: Explain return policies, process returns, handle refund requests
3. SHIPPING INFORMATION: Provide shipping costs, delivery times, international shipping info
4. PRODUCT SUPPORT: Answer product questions, check availability, provide specifications
5. STORE POLICIES: Explain business hours, contact info, privacy policies

COMMUNICATION STYLE:
- Polite and professional tone
- Clear and concise answers
- Proactive problem-solving
- Empathetic and understanding

SPECIAL INSTRUCTIONS:
- Always ask for order numbers when tracking orders
- Provide accurate shipping estimates based on destination
- Offer alternatives when products are out of stock
- Escalate complex issues to human support when needed

EXAMPLE RESPONSES:
Customer: "Where is my order #12345?"
You: "I'll check the status of order #12345 for you. [Checking]... Your order is currently 'In Transit' with estimated delivery on Friday. Tracking number: UPS-789XYZ."

Customer: "How do I return an item?"
You: "Our return policy allows returns within 30 days of delivery. Items must be unused with original packaging. Would you like me to send you the return form and instructions?"

Customer: "Do you ship to Germany?"
You: "Yes! We ship worldwide. Shipping to Germany takes 5-7 business days with a flat rate of $15. Duties and taxes may apply upon delivery."

IMPORTANT: If you don't have specific information, politely ask for details or direct to appropriate resources.""",
        
        "es": """Eres un asistente de servicio al cliente profesional para tiendas Shopify.

RESPONSABILIDADES PRINCIPALES:
1. GESTIÓN DE PEDIDOS: Verificar estado de pedidos, proporcionar información de seguimiento
2. DEVOLUCIONES Y REEMBOLSOS: Explicar políticas de devolución, procesar devoluciones
3. INFORMACIÓN DE ENVÍO: Proporcionar costos y tiempos de entrega
4. SOPORTE DE PRODUCTOS: Responder preguntas sobre productos, verificar disponibilidad
5. POLÍTICAS DE LA TIENDA: Explicar horarios de atención, información de contacto

IMPORTANTE: Sé claro, profesional y servicial en todas las respuestas.""",
        
        "fr": """Vous êtes un assistant de service client professionnel pour les boutiques Shopify.

RESPONSABILITÉS PRINCIPALES:
1. GESTION DES COMMANDES: Vérifier le statut des commandes, fournir le suivi
2. RETOURS ET REMBOURSEMENTS: Expliquer les politiques de retour
3. INFORMATIONS D'EXPÉDITION: Fournir les délais et coûts de livraison
4. SUPPORT PRODUIT: Répondre aux questions sur les produits
5. POLITIQUES DE LA BOUTIQUE: Expliquer les heures d'ouverture, contacts

IMPORTANT: Soyez clair, professionnel et serviable dans toutes les réponses."""
    }
    
    @staticmethod
    def detect_language(text: str) -> str:
        """自动检测语言"""
        # 简单语言检测
        if re.search(r'[áéíóúñ]', text, re.IGNORECASE):
            return "es"  # 西班牙语
        elif re.search(r'[àâçéèêëîïôùû]', text, re.IGNORECASE):
            return "fr"  # 法语
        elif re.search(r'[äöüß]', text, re.IGNORECASE):
            return "de"  # 德语
        elif re.search(r'[\u4e00-\u9fff]', text):
            return "zh"  # 中文
        else:
            return "en"  # 默认英语
    
    @staticmethod
    def get_system_prompt(language: str = "en") -> str:
        """获取对应语言的系统提示词"""
        return AIChatEngine.SYSTEM_PROMPTS.get(language, AIChatEngine.SYSTEM_PROMPTS["en"])
    
    @staticmethod
    def chat_with_ai(message: str, language: str = "en", retry_count: int = 2) -> Dict:
        """与AI对话（带重试机制）"""
        start_time = time.time()
        
        # 测试模式（如果没有设置API密钥）
        if config.DEEPSEEK_API_KEY.startswith("sk-your-key"):
            return {
                "success": True,
                "response": AIChatEngine.get_mock_response(message, language),
                "response_time": round(time.time() - start_time, 2),
                "tokens_used": 50,
                "model": "mock-mode"
            }
        
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": AIChatEngine.get_system_prompt(language)},
                {"role": "user", "content": message}
            ],
            "temperature": config.TEMPERATURE,
            "max_tokens": config.MAX_TOKENS,
            "stream": False
        }
        
        for attempt in range(retry_count + 1):
            try:
                response = requests.post(
                    config.DEEPSEEK_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=config.TIMEOUT_SECONDS
                )
                
                if response.status_code == 200:
                    data = response.json()
                    ai_response = data["choices"][0]["message"]["content"]
                    
                    return {
                        "success": True,
                        "response": ai_response,
                        "response_time": round(time.time() - start_time, 2),
                        "tokens_used": data.get("usage", {}).get("total_tokens", 0),
                        "model": data.get("model", "deepseek-chat")
                    }
                else:
                    if attempt < retry_count:
                        time.sleep(1)  # 等待后重试
                        continue
                    else:
                        return {
                            "success": False,
                            "response": "Sorry, I'm having trouble connecting to the AI service. Please try again in a moment.",
                            "error": f"API Error: {response.status_code}",
                            "response_time": round(time.time() - start_time, 2)
                        }
                        
            except requests.exceptions.Timeout:
                if attempt < retry_count:
                    continue
                return {
                    "success": False,
                    "response": "The request timed out. Please try again.",
                    "error": "Timeout",
                    "response_time": round(time.time() - start_time, 2)
                }
            except Exception as e:
                if attempt < retry_count:
                    continue
                return {
                    "success": False,
                    "response": "An error occurred. Please try again later.",
                    "error": str(e),
                    "response_time": round(time.time() - start_time, 2)
                }
    
    @staticmethod
    def get_mock_response(message: str, language: str = "en") -> str:
        """模拟AI回复（用于测试）"""
        message_lower = message.lower()
        
        responses_en = {
            "order": "I can help you track your order. Please provide your order number for specific details.",
            "track": "To track your order, please share your order number or tracking code.",
            "shipping": "Standard shipping: 5-7 business days. Express: 2-3 days. International: 7-14 days.",
            "return": "Our return policy: 30-day return window, items must be unused with original packaging.",
            "refund": "Refunds are processed within 5-7 business days after we receive the returned item.",
            "product": "I can help with product questions. Which product are you interested in?",
            "size": "We offer sizes XS to XXL. Please check our size guide for specific measurements.",
            "color": "Available colors vary by product. Which product would you like to check?",
            "price": "Prices are shown on the product pages. Is there a specific product you're asking about?",
            "stock": "I can check availability. Which product and size/color are you looking for?",
            "policy": "Store hours: Mon-Fri 9AM-6PM EST. Contact: support@store.com or call (555) 123-4567.",
            "hours": "We're available 24/7 via this chat! Phone support: Mon-Fri 9AM-6PM EST.",
            "default": "I'm here to help with order tracking, returns, shipping info, and product questions. What would you like to know?"
        }
        
        # 简单关键词匹配
        for keyword, response in responses_en.items():
            if keyword in message_lower:
                return response
        
        return responses_en["default"]

# ==================== 路由定义 ====================
@app.route('/')
def home():
    """首页 - 显示聊天界面"""
    # 生成用户ID（如果不存在）
    if 'user_id' not in session:
        session['user_id'] = hashlib.md5(str(time.time()).encode()).hexdigest()[:10]
        session.permanent = True
    
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天消息 - 主接口"""
    start_time = time.time()
    
    try:
        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided",
                "response": "Please provide a message."
            }), 400
        
        message = data.get('message', '').strip()
        if not message:
            return jsonify({
                "success": False,
                "error": "Empty message",
                "response": "Please type a message."
            }), 400
        
        # 获取用户ID
        user_id = session.get('user_id', 'anonymous')
        
        # 检测语言
        language = AIChatEngine.detect_language(message)
        
        # 与AI对话
        ai_result = AIChatEngine.chat_with_ai(message, language)
        
        # 保存聊天记录
        if ai_result.get("success"):
            DataManager.save_chat(user_id, message, ai_result["response"], language)
        
        # 准备响应
        response_data = {
            "success": ai_result.get("success", False),
            "response": ai_result.get("response", "Error processing request"),
            "language": language,
            "response_time": ai_result.get("response_time", round(time.time() - start_time, 2)),
            "tokens_used": ai_result.get("tokens_used", 0),
            "model": ai_result.get("model", "unknown"),
            "user_id": user_id[:6] + "..."  # 部分用户ID用于显示
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "response": "System error occurred. Please try again.",
            "error": str(e),
            "response_time": round(time.time() - start_time, 2)
        }), 500

@app.route('/api/stats')
def get_stats():
    """获取系统统计数据"""
    try:
        if os.path.exists(config.STATS_FILE):
            with open(config.STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = {
                "total_chats": 0,
                "total_messages": 0,
                "total_words": 0,
                "languages": {"en": 0},
                "categories": {
                    "order": 0, "shipping": 0, "return": 0,
                    "product": 0, "policy": 0, "other": 0
                },
                "system_status": "active",
                "last_updated": datetime.now().isoformat()
            }
        
        # 添加实时数据
        chats_data = DataManager.load_chats()
        recent_chats = chats_data.get("chats", [])[-10:]  # 最近10条
        
        stats.update({
            "recent_chats_count": len(recent_chats),
            "recent_chats": recent_chats,
            "server_time": datetime.now().isoformat(),
            "api_status": "operational",
            "version": "2.0.0"
        })
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "system_status": "error"
        }), 500

@app.route('/api/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "features": [
            "ai_chat", "multilingual", "data_analytics", 
            "error_recovery", "session_management"
        ]
    })

@app.route('/api/admin/summary')
def admin_summary():
    """管理员摘要（保护性接口）"""
    # 简单认证（未来可以加强）
    auth_key = request.args.get('key', '')
    if auth_key != os.getenv("ADMIN_KEY", "admin123"):
        return jsonify({"error": "Unauthorized"}), 403
    
    chats_data = DataManager.load_chats()
    
    summary = {
        "total_conversations": chats_data.get("total", 0),
        "today": len([c for c in chats_data.get("chats", []) 
                     if datetime.fromisoformat(c["timestamp"]).date() == datetime.now().date()]),
        "this_week": len([c for c in chats_data.get("chats", []) 
                         if datetime.fromisoformat(c["timestamp"]) > datetime.now() - timedelta(days=7)]),
        "avg_response_length": 0,
        "busiest_hour": "9:00-10:00 AM",  # 简化版本
        "system_uptime": str(timedelta(days=1)),  # 示例
        "memory_usage": "128MB",  # 示例
        "last_backup": datetime.now().isoformat()
    }
    
    return jsonify(summary)

@app.route('/api/shopify/products')
def shopify_products():
    """Shopify产品接口（模拟）"""
    # 这里可以集成真正的Shopify API
    products = [
        {
            "id": 1,
            "title": "Premium T-Shirt",
            "price": "$29.99",
            "available": True,
            "sizes": ["S", "M", "L", "XL"],
            "colors": ["Black", "White", "Blue"]
        },
        {
            "id": 2,
            "title": "Wireless Headphones",
            "price": "$89.99",
            "available": True,
            "colors": ["Black", "Silver"]
        },
        {
            "id": 3,
            "title": "Yoga Mat",
            "price": "$39.99",
            "available": False,
            "note": "Restocking next week"
        }
    ]
    
    return jsonify({
        "status": "success",
        "store": "demo-shop.myshopify.com",
        "products": products,
        "total_products": len(products),
        "integration": "simulated"  # 显示这是模拟数据
    })

@app.route('/test')
def test_page():
    """测试页面"""
    return """
    <h1>AI客服系统测试</h1>
    <p>系统运行正常！</p>
    <ul>
        <li><a href="/">主聊天界面</a></li>
        <li><a href="/api/stats">统计数据</a></li>
        <li><a href="/api/health">健康检查</a></li>
        <li><a href="/api/shopify/products">产品数据</a></li>
    </ul>
    <p>当前时间: {}</p>
    """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ==================== 错误处理 ====================
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found", "path": request.path}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error", "message": str(error)}), 500

# ==================== 启动应用 ====================
if __name__ == '__main__':
    # 确保数据目录存在
    DataManager.ensure_data_dir()
    
    # 打印启动信息
    print("=" * 60)
    print("🚀 AI Shopify Customer Service - 高级版")
    print("=" * 60)
    print("📊 功能特色:")
    print("  • 真正的AI对话 (DeepSeek API)")
    print("  • 多语言自动检测 (英/西/法/德/中)")
    print("  • 智能数据统计与分析")
    print("  • 对话历史记录保存")
    print("  • 错误恢复与重试机制")
    print("  • Shopify数据集成")
    print("  • 管理员监控界面")
    print("")
    print("💰 商业模式:")
    print("  • 目标客户: Shopify店主")
    print("  • 月费: $99 (免费试用30天)")
    print("  • 价值: 每月节省20+小时客服时间")
    print("")
    print("🌐 访问地址: http://localhost:5000")
    print("📈 统计数据: http://localhost:5000/api/stats")
    print("🩺 健康检查: http://localhost:5000/api/health")
    print("=" * 60)
    
    # 启动Flask应用
    app.run(
        debug=True,
        host='0.0.0.0', 
        port=5000,
        threaded=True  # 支持多线程
    )
