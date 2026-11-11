import telebot
from telebot import types
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os
import re

TOKEN = '9274188079:AAGDENXlzH4vlYUQwLFoK0d0zVBLH7tbX-Q'
bot = telebot.TeleBot(TOKEN)

user_data = {}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'items_list': []}
    ask_item(chat_id)

def ask_item(chat_id):
    if isinstance(chat_id, types.Message):
        chat_id = chat_id.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {'items_list': []}
        
    bot.clear_step_handler_by_chat_id(chat_id)
    msg = bot.send_message(chat_id, 
        "🧾 **ប្រព័ន្ធបង្កើតវិក្កយបត្រ THE SAL**\n\n"
        "🛍️ សូមបញ្ចូល **មុខទំនិញ ចំនួន តម្លៃរាយ និងតម្លៃសរុប** តាមទម្រង់នេះ (អាច Paste ច្រើនជួរព្រមគ្នាបាន):\n"
        "`ឈ្មោះទំនិញ | ចំនួន | តម្លៃរាយ | តម្លៃសរុប`\n\n"
        "ឧទាហរណ៍:\n"
        "ប៊ូសចង្កូត | 1 | 15$ | 15$", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_item)

def process_item(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if chat_id not in user_data:
        user_data[chat_id] = {'items_list': []}
        
    for line in text.split('\n'):
        line = line.strip()
        if '|' in line:
            user_data[chat_id]['items_list'].append(line)
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("➕ បន្ថែមមុខទំនិញទៀត", callback_data="add_more"),
        types.InlineKeyboardButton("🧮 សរុបទឹកប្រាក់ (Auto Total)", callback_data="calculate_total")
    )
    
    current_items = "\n".join(user_data[chat_id]['items_list'])
    bot.send_message(chat_id, 
        f"✅ **ទំនិញដែលបានកត់ត្រា៖**\n{current_items}\n\n"
        "តើបងចង់ធ្វើអ្វីបន្តទៀត?", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    bot.clear_step_handler_by_chat_id(chat_id)
    
    if call.data == "add_more":
        bot.answer_callback_query(call.id, "សូមវាយបញ្ចូល ឬ Paste មុខទំនិញបន្ថែម៖")
        msg = bot.send_message(chat_id, "សូមវាយបញ្ចូលមុខទំនិញបន្ថែម៖\n`ឈ្មោះទំនិញ | ចំនួន | តម្លៃរាយ | តម្លៃសរុប`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_item)
        
    elif call.data == "calculate_total":
        bot.answer_callback_query(call.id, "កំពុងគណនាតម្លៃសរុប...")
        
        total_sum = 0.0
        if chat_id in user_data and 'items_list' in user_data[chat_id]:
            for item in user_data[chat_id]['items_list']:
                parts = [p.strip() for p in item.split('|')]
                if len(parts) > 3:
                    match = re.search(r'[\d\.]+', parts[3])
                    if match:
                        try:
                            total_sum += float(match.group())
                        except ValueError:
                            pass
                            
        user_data[chat_id]['total'] = f"{int(total_sum) if total_sum.is_integer() else total_sum}$"
        
        bot.send_message(chat_id, f"💵 **ទឹកប្រាក់សរុបគណនាបានស្វ័យប្រវត្តិ៖** `{user_data[chat_id]['total']}`", parse_mode="Markdown")
        
        msg = bot.send_message(chat_id, "👤 សូមបញ្ចូល **ឈ្មោះអតិថិជន**៖", parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_name)

def get_name(message):
    chat_id = message.chat.id
    user_data[chat_id]['name'] = message.text
    msg = bot.send_message(chat_id, "📞 សូមបញ្ចូល **លេខទូរស័ព្ទអ្នកទទួល**៖", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_phone)

def get_phone(message):
    chat_id = message.chat.id
    user_data[chat_id]['phone'] = message.text
    msg = bot.send_message(chat_id, "📍 សូមបញ្ចូល **ទីតាំងដឹកជញ្ជូន**៖", parse_mode="Markdown")
    bot.register_next_step_handler(msg, get_location)

def get_location(message):
    chat_id = message.chat.id
    user_data[chat_id]['location'] = message.text
    generate_invoice_image(chat_id)

def generate_invoice_image(chat_id):
    data = user_data[chat_id]
    current_date = "កាលបរិច្ឆេទ : " + datetime.now().strftime("%d / %m / %Y")

    try:
        img_path = os.path.join(BASE_DIR, "template.png")
        
        # ស្វែងរកហ្វូនខ្មែរ
        font_candidates = ["Battambang-Regular.ttf", "KhmerS4.ttf", "Khmer S4.ttf", "Battambang.ttf", "Siemreap.ttf"]
        font_path = None
        for fc in font_candidates:
            p = os.path.join(BASE_DIR, fc)
            if os.path.exists(p):
                font_path = p
                break
        
        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # កំណត់ Font តាមទំហំដែលបងចង់បាន
        try:
            font = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default()
            font_bold = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
            font_total = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
        except:
            font = font_bold = font_total = ImageFont.load_default()

        # 1. จัดรูปแบบรายการสินค้าทั้งหมดให้ออกมาเป็นข้อความต่อกัน
        items_lines = data.get('items_list', [])
        formatted_items = "\n".join(items_lines)

        # 2. សរសេរព័ត៌មានទំនិញតាមកូអរដោនេ (150, 450)
        draw.text((150, 450), formatted_items, fill="black", font=font)
        
        # 3. សរសេរឈ្មោះអតិថិជន លេខទូរស័ព្ទ និងទីតាំង តាមកូអរដោនេដែលបងបានកំណត់
        draw.text((200, 850), data.get('name', ''), fill="black", font=font)
        draw.text((250, 910), data.get('phone', ''), fill="blue", font=font)
        draw.text((250, 970), data.get('location', ''), fill="black", font=font)

        # 4. សរសេរទឹកប្រាក់សរុប និងកាលបរិច្ឆេទ (ផ្នែកខាងស្ដាំខាងក្រោម)
        width, height = img.size
        draw.text((width * 0.84, height * 0.822), data.get('total', ''), fill="red", font=font_total, anchor="mm")
        draw.text((width * 0.77, height * 0.876), current_date, fill="red", font=font, anchor="mm")

        output_filename = f"invoice_{chat_id}.png"
        output_path = os.path.join(BASE_DIR, output_filename)
        img.save(output_path)
        
        with open(output_path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption="🧾 នេះជារូបភាពវិក្កយបត្ររបស់អ្នកហាង THE SAL!")
            
        os.remove(output_path)
        
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ មានបញ្ហាក្នុងการបង្កើតរូបភាព៖ {str(e)}")

    user_data[chat_id] = {'items_list': []}
    ask_item(chat_id)

bot.infinity_polling()
