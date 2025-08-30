import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
from flask import Flask, request
import threading
import time
import os
import secrets
import string
import socket

# إعدادات البوت - تأكد من صحة التوكن
TELEGRAM_BOT_TOKEN = "8275879185:AAFlth2Zuk2PdpNHWgTpanw6Q3F6NMNTsOs"
ADMIN_ID = 6079905042  # ID المالك

# تهيئة البوت
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# قاموس لتخزين معلومات المستخدمين
user_sessions = {}

# قائمة بالمستخدمين المفعلين
activated_users = set()

# قاموس لتخزين الروابط الفريدة
unique_links = {}

# تحميل البيانات المحفوظة إذا وجدت
def load_data():
    global activated_users
    try:
        if os.path.exists('activated_users.json'):
            with open('activated_users.json', 'r') as f:
                activated_users = set(json.load(f))
        print(f"تم تحميل {len(activated_users)} مستخدم مفعل")
    except Exception as e:
        print(f"خطأ في تحميل البيانات: {e}")
        activated_users = set()

# حفظ البيانات
def save_data():
    try:
        with open('activated_users.json', 'w') as f:
            json.dump(list(activated_users), f)
        print(f"تم حفظ {len(activated_users)} مستخدم مفعل")
    except Exception as e:
        print(f"خطأ في حفظ البيانات: {e}")

# تحميل البيانات عند البدء
load_data()

# إنشاء رمز فريد للرابط
def generate_unique_token(length=16):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# تطبيق Flask لمعالجة طلبات الويب
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! Use /location/<token> to share your location."

@app.route('/location/<token>')
def get_location(token):
    # التحقق من صحة الرمز واستخراج user_id
    if token not in unique_links:
        return "الرابط غير صالح أو منتهي الصلاحية. يرجى طلب رابط جديد من البوت."
    
    user_id = unique_links[token]['user_id']
    timestamp = unique_links[token]['timestamp']
    
    # التحقق من أن الرابط لا يزال صالحًا (10 دقائق)
    if time.time() - timestamp > 600:  # 10 دقائق
        del unique_links[token]
        return "انتهت صلاحية الرابط. يرجى طلب رابط جديد من البوت."
    
    # التحقق من أن المستخدم مفعل
    if int(user_id) not in activated_users and int(user_id) != ADMIN_ID:
        return "غير مصرح لك باستخدام هذا البوت. يرجى التواصل مع المسؤول."
    
    # إذا كان المستخدم قد منح إذن الموقع مسبقًا
    if str(user_id) in user_sessions and user_sessions[str(user_id)].get('location_granted', False):
        # إرسال الموقع إلى Telegram
        lat = user_sessions[str(user_id)]['latitude']
        lon = user_sessions[str(user_id)]['longitude']
        
        try:
            bot.send_message(
                user_id, 
                f"تم الحصول على موقعك:\nخط العرض: {lat}\nخط الطول: {lon}"
            )
            bot.send_location(user_id, lat, lon)
        except Exception as e:
            print(f"خطأ في إرسال الرسالة: {e}")
        
        return "تم إرسال موقعك إلى Telegram. يمكنك إغلاق هذه الصفحة."
    
    # إذا لم يمنح المستخدم إذن الموقع بعد
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>الحصول على الموقع</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script>
            function getLocation() {{
                if (navigator.geolocation) {{
                    navigator.geolocation.getCurrentPosition(showPosition, showError, {{
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0
                    }});
                }} else {{
                    document.getElementById("status").innerHTML = "المتصفح لا يدعم خاصية تحديد الموقع.";
                }}
            }}
            
            function showPosition(position) {{
                var lat = position.coords.latitude;
                var lon = position.coords.longitude;
                
                document.getElementById("status").innerHTML = "جارٍ إرسال الموقع...";
                
                // إرسال البيانات إلى الخادم
                fetch('/save_location/{token}', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        latitude: lat,
                        longitude: lon,
                        granted: true
                    }})
                }})
                .then(response => response.text())
                .then(data => {{
                    document.getElementById("status").innerHTML = "✓ تم إرسال موقعك بنجاح! يمكنك إغلاق هذه الصفحة.";
                }})
                .catch((error) => {{
                    console.error('Error:', error);
                    document.getElementById("status").innerHTML = "حدث خطأ في إرسال البيانات.";
                }});
            }}
            
            function showError(error) {{
                let message = "";
                switch(error.code) {{
                    case error.PERMISSION_DENIED:
                        message = "تم رفض طلب الحصول على الموقع. يرجى منح الإذن.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        message = "معلومات الموقع غير متوفرة.";
                        break;
                    case error.TIMEOUT:
                        message = "انتهت مهلة طلب الحصول على الموقع.";
                        break;
                    case error.UNKNOWN_ERROR:
                        message = "حدث خطأ غير معروف.";
                        break;
                }}
                document.getElementById("status").innerHTML = message;
                
                // زر لإعادة المحاولة
                document.getElementById("retry").style.display = "block";
            }}
        </script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                text-align: center;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                color: white;
            }}
            .container {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
                max-width: 500px;
                width: 100%;
            }}
            h2 {{
                margin-top: 0;
                margin-bottom: 20px;
            }}
            #status {{
                margin: 20px 0;
                padding: 15px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                font-size: 16px;
            }}
            button {{
                background: #4CAF50;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                margin-top: 15px;
                transition: background 0.3s;
            }}
            button:hover {{
                background: #45a049;
            }}
            .hidden {{
                display: none;
            }}
        </style>
    </head>
    <body onload="getLocation()">
        <div class="container">
            <h2>📍 مشاركة الموقع</h2>
            <div id="status">جاري طلب إذن الوصول إلى موقعك...</div>
            <button id="retry" class="hidden" onclick="getLocation()">إعادة المحاولة</button>
        </div>
    </body>
    </html>
    '''

@app.route('/save_location/<token>', methods=['POST'])
def save_location(token):
    try:
        # التحقق من صحة الرمز
        if token not in unique_links:
            return "الرابط غير صالح أو منتهي الصلاحية.", 400
        
        user_id = unique_links[token]['user_id']
        
        data = request.get_json()
        if data:
            user_sessions[str(user_id)] = {
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'location_granted': data['granted']
            }
            
            # إرسال الموقع إلى Telegram
            try:
                bot.send_message(
                    user_id, 
                    f"📍 تم الحصول على موقعك:\n• خط العرض: {data['latitude']}\n• خط الطول: {data['longitude']}"
                )
                bot.send_location(user_id, data['latitude'], data['longitude'])
            except Exception as e:
                print(f"خطأ في إرسال الموقع: {e}")
            
            # حذف الرابط بعد استخدامه
            del unique_links[token]
            
            return "تم حفظ الموقع بنجاح!"
        else:
            return "لم يتم استلام بيانات صحيحة.", 400
    except Exception as e:
        print(f"Error saving location: {e}")
        return "حدث خطأ في معالجة البيانات.", 500

# تشغيل خادم Flask في خيط منفصل
def run_flask():
    port = 5000  # استخدام المنفذ 5000 بدلاً من 80
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

# بدء تشغيل خادم Flask في خيط منفصل
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# انتظار حتى يبدأ الخادم
time.sleep(2)

# الحصول على IP السيرفر
try:
    hostname = socket.gethostname()
    server_ip = socket.gethostbyname(hostname)
except:
    server_ip = "172.245.154.102"  # استخدام IP السيرفر مباشرة

public_url = f"http://{server_ip}:5000"

print(f"Server is running at: {public_url}")
print(f"Location endpoint: {public_url}/location/<token>")

# معالجة الأمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # التحقق من صلاحية المستخدم
    if user_id not in activated_users and user_id != ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "❌ غير مصرح لك باستخدام هذا البوت.\nيرجى التواصل مع المسؤول للحصول على صلاحية."
        )
        return
    
    # إنشاء زر عادي (ليس زر ويب)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📍 الحصول على موقع", callback_data="get_location"))
    
    # إذا كان المستخدم هو المسؤول، إضافة لوحة التحكم
    if user_id == ADMIN_ID:
        markup.add(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel")
        )
    
    bot.send_message(
        message.chat.id,
        f"مرحبًا {message.from_user.first_name}! 👋\n\nاضغط على الزر أدناه للحصول على رابط مشاركة الموقع.",
        reply_markup=markup
    )

# معالجة الضغط على الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    user_id = call.from_user.id
    
    if call.data == "get_location":
        # التحقق من صلاحية المستخدم
        if user_id not in activated_users and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "غير مصرح لك باستخدام هذا البوت")
            return
            
        try:
            # إنشاء رمز فريد للرابط
            token = generate_unique_token()
            unique_links[token] = {
                'user_id': user_id,
                'timestamp': time.time()
            }
            
            # إرسال الرابط الفريد للمستخدم
            location_url = f"{public_url}/location/{token}"
            bot.send_message(
                call.message.chat.id,
                f"🔗 اضغط على الرابط أدناه لمشاركة موقعك:\n\n{location_url}\n\n"
                f"⏰ هذا الرابط صالح لمدة 10 دقائق فقط.\n"
                f"سيتم إرسال موقعك تلقائيًا إلى هذه المحادثة بعد منح الإذن."
            )
            
            # تأكيد استلام الطلب
            bot.answer_callback_query(call.id, "تم إنشاء رابط جديد لمشاركة الموقع")
        except Exception as e:
            print(f"Error handling location request: {e}")
            bot.answer_callback_query(call.id, "حدث خطأ، يرجى المحاولة مرة أخرى")
    
    elif call.data == "admin_panel":
        # التحقق من أن المستخدم هو المسؤول
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "غير مصرح لك بالوصول إلى لوحة التحكم")
            return
            
        # عرض لوحة تحكم المسؤول
        show_admin_panel(call.message)
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("admin_"):
        # التحقق من أن المستخدم هو المسؤول
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "غير مصرح لك بهذا الإجراء")
            return
            
        # معالجة أوامر المسؤول
        if call.data == "admin_activate":
            ask_for_user_id(call.message, "activate")
        elif call.data == "admin_deactivate":
            ask_for_user_id(call.message, "deactivate")
        elif call.data == "admin_list":
            show_activated_users(call.message)
        elif call.data == "admin_back":
            send_welcome(call.message)
        
        bot.answer_callback_query(call.id)

# عرض لوحة تحكم المسؤول
def show_admin_panel(message):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ تفعيل مستخدم", callback_data="admin_activate"),
        InlineKeyboardButton("❌ إلغاء التفعيل", callback_data="admin_deactivate")
    )
    markup.row(InlineKeyboardButton("📋 قائمة المستخدمين", callback_data="admin_list"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_back"))
    
    bot.send_message(
        message.chat.id,
        "👑 لوحة تحكم المسؤول\n\nاختر الإجراء الذي تريد تنفيذه:",
        reply_markup=markup
    )

# طلب معرف المستخدم للتفعيل/إلغاء التفعيل
def ask_for_user_id(message, action_type):
    sent_msg = bot.send_message(
        message.chat.id,
        "أرسل معرف المستخدم الذي تريد تفعيله/إلغاء تفعيله:"
    )
    
    # تسجيل دالة الاستجابة للخطوة التالية
    bot.register_next_step_handler(sent_msg, process_user_id, action_type)

# معالجة معرف المستخدم
def process_user_id(message, action_type):
    try:
        target_user_id = int(message.text)
        
        if action_type == "activate":
            activated_users.add(target_user_id)
            bot.send_message(message.chat.id, f"✅ تم تفعيل المستخدم {target_user_id} بنجاح.")
        else:
            if target_user_id in activated_users:
                activated_users.remove(target_user_id)
                bot.send_message(message.chat.id, f"❌ تم إلغاء تفعيل المستخدم {target_user_id} بنجاح.")
            else:
                bot.send_message(message.chat.id, "هذا المستخدم غير مفعل أصلاً.")
        
        # حفظ التغييرات
        save_data()
        
        # العودة إلى لوحة التحكم
        show_admin_panel(message)
        
    except ValueError:
        bot.send_message(message.chat.id, "معرف المستخدم غير صحيح. يرجى إرسال رقم صحيح.")
        show_admin_panel(message)

# عرض قائمة المستخدمين المفعلين
def show_activated_users(message):
    if not activated_users:
        bot.send_message(message.chat.id, "لا يوجد مستخدمين مفعلين حالياً.")
    else:
        users_list = "\n".join([f"• {user_id}" for user_id in activated_users])
        bot.send_message(
            message.chat.id,
            f"📋 قائمة المستخدمين المفعلين:\n\n{users_list}\n\nإجمالي عددهم: {len(activated_users)}"
        )
    
    # العودة إلى لوحة التحكم
    show_admin_panel(message)

# معالجة الرسائل النصية
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    
    # إذا كان المستخدم هو المسؤول، يمكنه إرسال أوامر نصية أيضاً
    if user_id == ADMIN_ID and message.text.isdigit():
        # إذا أرسل المسؤول رقمًا، افترض أنه يريد تفعيل مستخدم
        target_user_id = int(message.text)
        activated_users.add(target_user_id)
        save_data()
        bot.send_message(message.chat.id, f"✅ تم تفعيل المستخدم {target_user_id} بنجاح.")
    else:
        # إذا كان المستخدم العادي يرسل رسالة نصية
        if user_id not in activated_users and user_id != ADMIN_ID:
            bot.send_message(
                message.chat.id,
                "❌ غير مصرح لك باستخدام هذا البوت.\nيرجى التواصل مع المسؤول للحصول على صلاحية."
            )
        else:
            bot.send_message(
                message.chat.id,
                "استخدم الأزرار للتفاعل مع البوت."
            )

# دالة لتنظيف الروابط المنتهية الصلاحية (تعمل في الخلفية)
def clean_expired_links():
    while True:
        try:
            current_time = time.time()
            expired_tokens = [token for token, data in unique_links.items() 
                             if current_time - data['timestamp'] > 600]  # 10 دقائق
            
            for token in expired_tokens:
                del unique_links[token]
                
            time.sleep(60)  # التحقق كل دقيقة
        except:
            time.sleep(60)

# بدء عملية تنظيف الروابط المنتهية في خلفية
cleaner_thread = threading.Thread(target=clean_expired_links)
cleaner_thread.daemon = True
cleaner_thread.start()

# تشغيل البوت
if __name__ == "__main__":
    print("Bot is running...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Error: {e}")
        print("تأكد من صحة توكن البوت وقم بتشغيل البوت مرة أخرى")