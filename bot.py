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
        font_candidates = ["KhmerS4.ttf", "Khmer S4.ttf", "Battambang-Regular.ttf"]
        font_path = None
        for fc in font_candidates:
            p = os.path.join(BASE_DIR, fc)
            if os.path.exists(p):
                font_path = p
                break
        
        img = Image.open(img_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size

        try:
            # 🛠️ បង្កើនទំហំ Font មុខទំនិញឱ្យធំជាងមុនបន្តិច (ពី 0.016 មក 0.0175)
            font_item = ImageFont.truetype(font_path, int(height * 0.0175)) if font_path else ImageFont.load_default()
            font_cust = ImageFont.truetype(font_path, int(height * 0.018)) if font_path else ImageFont.load_default()
            font_total = ImageFont.truetype(font_path, int(height * 0.023)) if font_path else ImageFont.load_default()
            font_date = ImageFont.truetype(font_path, int(height * 0.016)) if font_path else ImageFont.load_default()
        except:
            font_item = font_cust = font_total = font_date = ImageFont.load_default()

        start_y = height * 0.330
        row_height = height * 0.040
        col_name_x = width * 0.15
        col_qty_x = width * 0.60
        col_price_x = width * 0.73
        col_total_x = width * 0.89

        lines = data.get('items_list', [])
        for i, line in enumerate(lines[:12]):
            parts = [p.strip() for p in line.split('|')]
            name = parts[0] if len(parts) > 0 else ""
            qty = parts[1] if len(parts) > 1 else ""
            price = parts[2] if len(parts) > 2 else ""
            
            total_item = ""
            if len(parts) > 3:
                match = re.search(r'[\d\.]+', parts[3])
                if match:
                    total_item = f"{match.group()}$"
                else:
                    total_item = parts[3]
            
            y = start_y + (i * row_height) + (row_height * 0.5)
            draw.text((col_name_x, y), name, fill="black", font=font_item, anchor="lm")
            draw.text((col_qty_x, y), qty, fill="black", font=font_item, anchor="mm")
            draw.text((col_price_x, y), price, fill="black", font=font_item, anchor="mm")
            draw.text((col_total_x, y), total_item, fill="black", font=font_item, anchor="mm")

        cust_x = width * 0.23
        draw.text((cust_x, height * 0.818), data.get('name', ''), fill="blue", font=font_cust)
        draw.text((cust_x, height * 0.852), data.get('phone', ''), fill="blue", font=font_cust)
        draw.text((cust_x, height * 0.885), data.get('location', ''), fill="blue", font=font_cust)

        draw.text((width * 0.84, height * 0.822), data.get('total', ''), fill="red", font=font_total, anchor="mm")
        draw.text((width * 0.77, height * 0.876), current_date, fill="red", font=font_date, anchor="mm")

        output_filename = f"invoice_{chat_id}.png"
        output_path = os.path.join(BASE_DIR, output_filename)
        img.save(output_path)
        
        with open(output_path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption="🧾 នេះជារូបភាពវិក្កយបត្ររបស់អ្នកហាង THE SAL!")
            
        os.remove(output_path)
        
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ មានបញ្ហាក្នុងការបង្កើតរូបភាព៖ {str(e)}")

    user_data[chat_id] = {'items_list': []}
    ask_item(chat_id)

bot.infinity_polling()
