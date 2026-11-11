import telebot
from telebot import types
from datetime import datetime
from html2image import Html2Image
import base64
import os
import re

TOKEN = '9274188079:AAGDENXlzH4vlYUQwLFoK0d0zVBLH7tbX-Q'
bot = telebot.TeleBot(TOKEN)

user_data = {}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
hti = Html2Image(output_path=BASE_DIR)

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
        
        with open(img_path, "rb") as image_file:
            bg_encoded = base64.b64encode(image_file.read()).decode('utf-8')
        bg_data_uri = f"data:image/png;base64,{bg_encoded}"
        
        font_css = "font-family: sans-serif;"
        if font_path:
            with open(font_path, "rb") as font_file:
                font_encoded = base64.b64encode(font_file.read()).decode('utf-8')
            font_data_uri = f"data:font/ttf;base64,{font_encoded}"
            font_css = f"""
            @font-face {{
                font-family: 'CustomKhmerFont';
                src: url('{font_data_uri}') format('truetype');
            }}
            body {{
                font-family: 'CustomKhmerFont', 'Khmer S4', 'KhmerS4', sans-serif;
            }}
            """
        
        from PIL import Image
        with Image.open(img_path) as img:
            width, height = img.size

        lines = data.get('items_list', [])
        rows_html = ""
        for line in lines[:12]:
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
            
            rows_html += f"""
            <tr>
                <td class="col-name"><span>{name}</span></td>
                <td class="col-qty"><span>{qty}</span></td>
                <td class="col-price"><span>{price}</span></td>
                <td class="col-total"><span>{total_item}</span></td>
            </tr>
            """
        
        remaining = 12 - len(lines[:12])
        for _ in range(remaining):
            rows_html += '<tr><td></td><td></td><td></td><td></td></tr>'

        html_content = f"""
        <!DOCTYPE html>
        <html lang="km">
        <head>
            <meta charset="UTF-8">
            <style>
                {font_css}
                body {{
                    margin: 0;
                    padding: 0;
                    width: {width}px;
                    height: {height}px;
                    background-image: url('{bg_data_uri}');
                    background-size: 100% 100%;
                    position: relative;
                }}
                .items-table {{
                    position: absolute;
                    top: {height * 0.3165}px;
                    left: {width * 0.14}px;
                    width: {width * 0.74}px;
                    border-collapse: collapse;
                    table-layout: fixed;
                }}
                .items-table tr {{
                    height: {height * 0.040}px;
                }}
                .items-table td {{
                    overflow: hidden;
                    white-space: nowrap;
                    text-overflow: ellipsis;
                }}
                .col-name {{ width: 52%; text-align: left; padding-left: 10px; font-size: {height * 0.016}px; font-weight: bold; }}
                .col-qty {{ width: 12%; text-align: center; font-size: {height * 0.016}px; font-weight: bold; }}
                .col-price {{ width: 18%; text-align: center; font-size: {height * 0.016}px; font-weight: bold; }}
                .col-total {{ width: 18%; text-align: center; font-size: {height * 0.016}px; font-weight: bold; }}
                
                .cust-name {{ position: absolute; top: {height * 0.818}px; left: {width * 0.23}px; font-size: {height * 0.018}px; font-weight: bold; color: blue; }}
                .cust-phone {{ position: absolute; top: {height * 0.852}px; left: {width * 0.23}px; font-size: {height * 0.018}px; font-weight: bold; color: blue; }}
                .cust-loc {{ position: absolute; top: {height * 0.885}px; left: {width * 0.23}px; font-size: {height * 0.018}px; font-weight: bold; color: blue; }}
                
                .invoice-total {{ position: absolute; top: {height * 0.822}px; left: {width * 0.84}px; transform: translate(-50%, -50%); font-size: {height * 0.023}px; font-weight: bold; color: red; }}
                .invoice-date {{ position: absolute; top: {height * 0.876}px; left: {width * 0.77}px; transform: translate(-50%, -50%); font-size: {height * 0.016}px; font-weight: bold; color: red; white-space: nowrap; }}
            </style>
        </head>
        <body>
            <table class="items-table">
                {rows_html}
            </table>
            
            <div class="cust-name">{data['name']}</div>
            <div class="cust-phone">{data['phone']}</div>
            <div class="cust-loc">{data['location']}</div>
            
            <div class="invoice-total">{data['total']}</div>
            <div class="invoice-date">{current_date}</div>
        </body>
        </html>
        """

        output_filename = f"invoice_{chat_id}.png"
        hti.screenshot(
            html_str=html_content,
            save_as=output_filename,
            size=(width, height)
        )
        
        output_path = os.path.join(BASE_DIR, output_filename)
        with open(output_path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption="🧾 នេះជារូបភាពវិក្កយបត្ររបស់អ្នកហាង THE SAL!")
            
        os.remove(output_path)
        
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ មានបញ្ហាក្នុងការបង្កើតរូបភាព៖ {str(e)}")

    user_data[chat_id] = {'items_list': []}
    ask_item(chat_id)

bot.infinity_polling()
