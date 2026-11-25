import base64
from datetime import datetime
import hashlib
import hmac
import os
import re
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
import telebot
from telebot import types

TOKEN = "9274188079:AAGDENXlzH4vlYUQwLFoK0d0zVBLH7tbX-Q"
bot = telebot.TeleBot(TOKEN)

# ==========================================
# ⚙️ ABA PayWay Sandbox Credentials
# ==========================================
ABA_MERCHANT_ID = os.environ.get("ABA_MERCHANT_ID", "ec480930")
ABA_PUBLIC_KEY = os.environ.get(
    "ABA_PUBLIC_KEY", "50FB3A0D89567C8E6D7D765315F639921D7B2465"
)
ABA_RSA_PRIVATE_KEY = os.environ.get(
    "ABA_RSA_PRIVATE_KEY",
    """-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQDlzpS7MLtLoz62CBi2Yo77W2CwT0XLLeeuxS/2BNnYOTC5HEZt
iPgePI3OTd/jpqZS9tZDAEGnxen7U4gtRA5AKM+ONbPaV2X4jcX/PcOEcb2DsFfI
YDRF3VGbcnjJmkw0d0eusYj/AeyNucVuSqzJTE3j7ZRigQxdI9ZEgFaL6wIDAQAB
AoGAUjB7EyPPqLKeyB3HMNu5BX7d6tC/RnaJiQEvMQ71FpcFrP7G1YAKNU407Vb+
vv2oOL3dTaM22Bk5oNB0QLQ5X91yQu+N7TTNCOjBxbV2fhRxKbpg4UE54HmpInjY
G4Jn2jlSlmxEHoNWxnLwYW+MRX1K1psZjo8VXDoeuq7q3XECQQD3AH3exdYKdoNd
8n3evnSsisaMGy70Am30z9d/snjxJi54CsjjTa9KX9sANKQEhMEcs/nfQm5bzYQN
7hbQJ56JAkEA7i27NHCPC5YsgN7kUlZQq1qq7cBVSk1p6D/AaOwUUnqQQZzcYawd
quNM/WdetFGLxITICOEUMcjowNup/reZ0wJBANITBfrBcjDF6SavBiS7AUp6YTFq
MT3xDwnG97aw2THoUl9gdMj2Gl78NavwGYuKSSAbZipfOrMzkNu0Ioz5FVkCQFQX
22f5cdfybsYVbGHRzeuiOIV3CeYRDRqOH74r1EUGtxYjbwAhR9xFIrK5o4tg20tI
YmQYLAwj1mH5bLzdUDcCQDcQx+VTQvDCafhMaZIx0rgT0YZFdRozPlEN1Bwz3eED
rHSyL1gQGnENbA0BU0ZuICOFE+cdTuNOJpAF+CgMs/s=
-----END RSA PRIVATE KEY-----""",
)

ABA_PURCHASE_URL = os.environ.get(
    "ABA_PURCHASE_URL",
    "https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/purchase",
)
ABA_CHECK_URL = os.environ.get(
    "ABA_CHECK_URL",
    "https://checkout-sandbox.payway.com.kh/api/payment-gateway/v1/payments/check-transaction",
)

user_data = {}
transactions_store = {}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_number(text):
  if not text:
    return None
  match = re.search(r"[\d]+(?:\.[\d]+)?", str(text).replace(",", ""))
  if not match:
    return None
  try:
    return float(match.group())
  except ValueError:
    return None


def format_usd(amount):
  val = float(amount)
  return f"{int(val) if val.is_integer() else round(val, 2)}$"


def parse_item_line(line):
  parts = [p.strip() for p in line.split("|")]
  name = parts[0] if len(parts) > 0 else ""
  qty_raw = parts[1] if len(parts) > 1 else "1"
  price_raw = parts[2] if len(parts) > 2 else "0"

  qty_num = parse_number(qty_raw)
  price_num = parse_number(price_raw)

  qty_str = (
      str(int(qty_num))
      if (qty_num is not None and qty_num.is_integer())
      else (str(qty_num) if qty_num is not None else qty_raw)
  )
  price_str = (
      format_usd(price_num)
      if price_num is not None
      else (f"{price_raw}$" if price_raw and not price_raw.endswith("$") else price_raw)
  )

  if len(parts) > 3 and parts[3]:
    manual_total = parse_number(parts[3])
    total_num = manual_total if manual_total is not None else 0.0
    total_str = (
        format_usd(manual_total) if manual_total is not None else parts[3]
    )
  else:
    q = qty_num if qty_num is not None else 0.0
    p = price_num if price_num is not None else 0.0
    total_num = q * p
    total_str = format_usd(total_num)

  return {
      "name": name,
      "qty_str": qty_str,
      "price_str": price_str,
      "total_str": total_str,
      "total_num": total_num,
      "formatted_line": f"{name} | {qty_str} | {price_str} = {total_str}",
  }


@bot.message_handler(commands=["start"])
def send_welcome(message):
  chat_id = message.chat.id
  user_data[chat_id] = {"items_list": []}

  logo_path = os.path.join(BASE_DIR, "logo.png")
  if os.path.exists(logo_path):
    with open(logo_path, "rb") as logo:
      bot.send_photo(
          chat_id,
          logo,
          caption=(
              "👋 **សួស្តី! សូមស្វាគមន៍មកកាន់ប្រព័ន្ធគ្រប់គ្រងវិក្កយបត្រហាង THE SAL &"
              " P.S.C**"
          ),
      )
  else:
    bot.send_message(
        chat_id,
        "👋 **សួស្តី! សូមស្វាគមន៍មកកាន់ប្រព័ន្ធគ្រប់គ្រងវិក្កយបត្រហាង THE SAL &"
        " P.S.C**",
    )

  ask_item(chat_id)


def ask_item(chat_id):
  if isinstance(chat_id, types.Message):
    chat_id = chat_id.chat.id
  if chat_id not in user_data:
    user_data[chat_id] = {"items_list": []}

  bot.clear_step_handler_by_chat_id(chat_id)
  msg = bot.send_message(
      chat_id,
      "🛍️ សូមបញ្ចូល **មុខទំនិញ ចំនួន និងតម្លៃរាយ** (មិនបាច់វាយតម្លៃសរុបទេ"
      " ប្រព័ន្ធគណនាឱ្យដោយស្វ័យប្រវត្តិ):\n"
      "`ឈ្មោះទំនិញ | ចំនួន | តម្លៃរាយ`\n\n"
      "ឧទាហរណ៍:\n"
      "ប៊ូសចង្កូត | 1 | 15$\n"
      "សំបកកង់ | 4 | 50$",
      parse_mode="Markdown",
  )
  bot.register_next_step_handler(msg, process_item)


def process_item(message):
  chat_id = message.chat.id
  text = (message.text or "").strip()

  if chat_id not in user_data:
    user_data[chat_id] = {"items_list": []}

  for line in text.split("\n"):
    line = line.strip()
    if "|" in line:
      user_data[chat_id]["items_list"].append(line)

  markup = types.InlineKeyboardMarkup()
  markup.row(
      types.InlineKeyboardButton(
          "➕ បន្ថែមមុខទំនិញទៀត", callback_data="add_more"
      ),
      types.InlineKeyboardButton(
          "🧮 បញ្ចប់ & គណនាសរុប (Auto Total)", callback_data="calculate_total"
      ),
  )

  preview_lines = [
      parse_item_line(item)["formatted_line"]
      for item in user_data[chat_id]["items_list"]
  ]
  current_items = "\n".join(preview_lines) if preview_lines else "—"
  bot.send_message(
      chat_id,
      f"✅ **ទំនិញដែលបានកត់ត្រា៖**\n{current_items}\n\n"
      "តើបងចង់ធ្វើអ្វីបន្តទៀត?",
      parse_mode="Markdown",
      reply_markup=markup,
  )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  chat_id = call.message.chat.id
  bot.clear_step_handler_by_chat_id(chat_id)

  if call.data == "add_more":
    bot.answer_callback_query(
        call.id, "សូមវាយបញ្ចូល ឬ Paste មុខទំនិញបន្ថែម៖"
    )
    msg = bot.send_message(
        chat_id,
        "សូមវាយបញ្ចូលមុខទំនិញបន្ថែម៖\n`ឈ្មោះទំនិញ | ចំនួន | តម្លៃរាយ`",
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, process_item)

  elif call.data == "calculate_total":
    bot.answer_callback_query(call.id, "កំពុងគណនាតម្លៃសរុប...")

    total_sum = 0.0
    if chat_id in user_data and "items_list" in user_data[chat_id]:
      for item in user_data[chat_id]["items_list"]:
        parsed = parse_item_line(item)
        total_sum += parsed["total_num"]

    user_data[chat_id]["total_num"] = total_sum
    user_data[chat_id]["total"] = format_usd(total_sum)

    bot.send_message(
        chat_id,
        f"💵 **ទឹកប្រាក់សរុបគណនាបានស្វ័យប្រវត្តិ៖**"
        f" `{user_data[chat_id]['total']}`",
        parse_mode="Markdown",
    )

    msg = bot.send_message(
        chat_id, "👤 សូមបញ្ចូល **ឈ្មោះអតិថិជន**៖", parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_name)

  elif call.data == "edit_name":
    bot.answer_callback_query(call.id, "កែប្រែឈ្មោះអតិថិជន")
    msg = bot.send_message(
        chat_id, "👤 សូមបញ្ចូល **ឈ្មោះអតិថិជន** ថ្មី៖", parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, get_name)

  elif call.data == "edit_phone":
    bot.answer_callback_query(call.id, "កែប្រែលេខទូរស័ព្ទ")
    msg = bot.send_message(
        chat_id,
        "📞 សូមបញ្ចូល **លេខទូរស័ព្ទអ្នកទទួល** ថ្មី៖",
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, get_phone)

  elif call.data == "edit_location":
    bot.answer_callback_query(call.id, "កែប្រែទីតាំងដឹកជញ្ជូន")
    msg = bot.send_message(
        chat_id,
        "📍 សូមបញ្ចូល **ទីតាំងដឹកជញ្ជូន** ថ្មី៖",
        parse_mode="Markdown",
    )
    bot.register_next_step_handler(msg, get_location)

  elif call.data == "confirm_generate":
    bot.answer_callback_query(call.id, "សូមជ្រើសរើសប្រភេទបុងវិក្កយបត្រ៖")

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(
            "🧾 1. The Sal (template.png)", callback_data="template_the_sal"
        ),
        types.InlineKeyboardButton(
            "🧾 2. P.S.C (template2.png)", callback_data="template_psc"
        ),
    )
    bot.send_message(
        chat_id, "តើបងចង់ចេញវិក្កយបត្រប្រភេទណា?", reply_markup=markup
    )

  elif call.data == "template_the_sal":
    bot.answer_callback_query(call.id, "កំពុងបង្កើតវិក្កយបត្រ The Sal...")
    generate_invoice_image(chat_id, "template.png", "The Sal")

  elif call.data == "template_psc":
    bot.answer_callback_query(call.id, "កំពុងបង្កើតវិក្កយបត្រ P.S.C...")
    generate_invoice_image(chat_id, "template2.png", "P.S.C")

  elif call.data and call.data.startswith("check_pay:"):
    tran_id = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id, "កំពុងឆែកស្ថានភាពបង់ប្រាក់...")
    status_msg = check_aba_payment_status(tran_id)
    bot.send_message(chat_id, status_msg, parse_mode="Markdown")


def get_name(message):
  chat_id = message.chat.id
  if chat_id not in user_data:
    user_data[chat_id] = {}
  user_data[chat_id]["name"] = message.text

  msg = bot.send_message(
      chat_id,
      "📞 សូមបញ្ចូល **លេខទូរស័ព្ទអ្នកទទួល**៖",
      parse_mode="Markdown",
  )
  bot.register_next_step_handler(msg, get_phone)


def get_phone(message):
  chat_id = message.chat.id
  if chat_id not in user_data:
    user_data[chat_id] = {}
  user_data[chat_id]["phone"] = message.text

  msg = bot.send_message(
      chat_id, "📍 សូមបញ្ចូល **ទីតាំងដឹកជញ្ជូន**៖", parse_mode="Markdown"
  )
  bot.register_next_step_handler(msg, get_location)


def get_location(message):
  chat_id = message.chat.id
  if chat_id not in user_data:
    user_data[chat_id] = {}
  user_data[chat_id]["location"] = message.text

  show_preview_summary(chat_id)


def show_preview_summary(chat_id):
  data = user_data[chat_id]
  summary_text = (
      "📋 **ពិនិត្យព័ត៌មានអតិថិជនមុនចេញវិក្កយបត្រ៖**\n\n"
      f"👤 **ឈ្មោះ៖** {data.get('name', '')}\n"
      f"📞 **ទូរស័ព្ទ៖** {data.get('phone', '')}\n"
      f"📍 **ទីតាំង៖** {data.get('location', '')}\n"
      f"💵 **ទឹកប្រាក់សរុប៖** {data.get('total', '')}\n\n"
      "តើបងចង់កែប្រែព័ត៌មានណាមួយ ឬទៅជ្រើសរើសប្រភេទបុង?"
  )

  markup = types.InlineKeyboardMarkup()
  markup.row(
      types.InlineKeyboardButton("✏️ កែឈ្មោះ", callback_data="edit_name"),
      types.InlineKeyboardButton("✏️ កែទូរស័ព្ទ", callback_data="edit_phone"),
  )
  markup.row(
      types.InlineKeyboardButton("✏️ កែទីតាំង", callback_data="edit_location"),
      types.InlineKeyboardButton(
          "🚀 ជ្រើសរើសប្រភេទបុង", callback_data="confirm_generate"
      ),
  )

  bot.send_message(
      chat_id, summary_text, parse_mode="Markdown", reply_markup=markup
  )


# ==========================================
# 🔐 ABA PayWay Sandbox Purchase & Check API
# ==========================================
def generate_aba_hash(raw_string, key=ABA_PUBLIC_KEY):
  digest = hmac.new(
      key.encode("utf-8"), raw_string.encode("utf-8"), hashlib.sha512
  ).digest()
  return base64.b64encode(digest).decode("utf-8")


def request_aba_purchase_qr(tran_id, amount_num, customer_info, brand_name):
  """
    ហៅ ABA PayWay Sandbox /v1/payments/purchase។
    ប្រសិនបើ API ត្រឡប់ qrString / qr_string / abapay_deeplink / checkout_url នឹងប្រើសម្រាប់បង្កើត QR។
    """
  amount_str = f"{float(amount_num):.2f}"
  req_time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
  payment_option = "abapay_khqr"
  currency = "USD"

  # លំដាប់ hash string ធម្មតារបស់ ABA PayWay (អាចកែតាមឯកសារ PayWay version ពិតប្រាកដ)
  raw_for_hash = (
      f"{req_time}{ABA_MERCHANT_ID}{tran_id}{amount_str}{payment_option}{currency}"
  )
  req_hash = generate_aba_hash(raw_for_hash, ABA_PUBLIC_KEY)

  form_data = {
      "req_time": req_time,
      "merchant_id": ABA_MERCHANT_ID,
      "tran_id": tran_id,
      "amount": amount_str,
      "currency": currency,
      "payment_option": payment_option,
      "firstname": customer_info.get("name", "") or "Customer",
      "phone": customer_info.get("phone", ""),
      "hash": req_hash,
  }

  try:
    resp = requests.post(
        ABA_PURCHASE_URL,
        data=form_data,
        headers={"Accept": "application/json"},
        timeout=20,
    )
    try:
      res_json = resp.json()
    except ValueError:
      res_json = {"raw_text": resp.text}

    qr_val = (
        res_json.get("qrString")
        or res_json.get("qr_string")
        or res_json.get("abapay_deeplink")
        or res_json.get("checkout_url")
        or (res_json.get("data", {}) if isinstance(res_json.get("data"), dict) else {}).get("qrString")
        or (res_json.get("data", {}) if isinstance(res_json.get("data"), dict) else {}).get("qr_string")
    )
    if qr_val:
      return str(qr_val), None

    # ប្រសិនបើ Sandbox ទាមទារ field ឬ hash format ផ្សេង នឹងបង្ហាញព័ត៌មានឆ្លើយតបដើម្បីងាយស្រួលកែ
    return (
        f"ABA_SANDBOX|MID:{ABA_MERCHANT_ID}|{brand_name}|{tran_id}|{amount_str} USD",
        f"⚠️ ABA API response: `{str(res_json)[:300]}`",
    )
  except Exception as e:
    return (
        f"ABA_SANDBOX|MID:{ABA_MERCHANT_ID}|{brand_name}|{tran_id}|{amount_str} USD",
        f"⚠️ មិនអាចតភ្ជាប់ ABA Purchase API បាន៖ `{str(e)}`",
    )


def check_aba_payment_status(tran_id):
  info = transactions_store.get(tran_id, {})
  req_time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
  raw_for_hash = f"{req_time}{ABA_MERCHANT_ID}{tran_id}"
  payload = {
      "req_time": req_time,
      "merchant_id": ABA_MERCHANT_ID,
      "tran_id": tran_id,
      "hash": generate_aba_hash(raw_for_hash, ABA_PUBLIC_KEY),
  }

  try:
    resp = requests.post(ABA_CHECK_URL, json=payload, timeout=20)
    try:
      res_data = resp.json()
    except ValueError:
      res_data = {"raw_text": resp.text}

    payment_status = (
        res_data.get("payment_status")
        or (res_data.get("data", {}) if isinstance(res_data.get("data"), dict) else {}).get("payment_status")
        or (res_data.get("status", {}) if isinstance(res_data.get("status"), dict) else {}).get("message")
        or str(res_data)[:250]
    )
    return (
        f"🔎 **ស្ថានភាពបង់ប្រាក់ (Sandbox):**\n"
        f"• Ref: `{tran_id}`\n"
        f"• ទឹកប្រាក់៖ `{info.get('amount_str', 'N/A')}`\n"
        f"• លទ្ធផល៖ **{payment_status}**"
    )
  except Exception as e:
    return f"⚠️ មិនអាចឆែកស្ថានភាព `{tran_id}` បានទេ៖ `{str(e)}`"


def find_aba_qr_bg():
  for name in ("aba_qr_bg.jpg", "aba_qr_bg.jpeg", "aba_qr_bg.png"):
    p = os.path.join(BASE_DIR, name)
    if os.path.exists(p):
      return p
  return None


def generate_qr_image(qr_text, output_path):
  qr = qrcode.QRCode(
      version=None,
      error_correction=qrcode.constants.ERROR_CORRECT_M,
      box_size=10,
      border=2,
  )
  qr.add_data(qr_text)
  qr.make(fit=True)
  qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

  bg_path = find_aba_qr_bg()
  if bg_path:
    bg_img = Image.open(bg_path).convert("RGB")
    bg_w, bg_h = bg_img.size

    qr_size = int(min(bg_w, bg_h) * 0.42)
    qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    paste_x = (bg_w - qr_size) // 2
    paste_y = int(bg_h * 0.50) - (qr_size // 2)

    bg_img.paste(qr_resized, (paste_x, paste_y))
    bg_img.save(output_path, format="JPEG", quality=95)
  else:
    qr_img.save(output_path, format="JPEG", quality=95)


def generate_invoice_image(chat_id, template_filename, brand_name):
  data = user_data[chat_id]
  current_date = "កាលបរិច្ឆេទ : " + datetime.now().strftime("%d / %m / %Y")
  output_path = None
  qr_path = None

  try:
    img_path = os.path.join(BASE_DIR, template_filename)

    if not os.path.exists(img_path):
      bot.send_message(
          chat_id,
          f"⚠️ រកមិនឃើញរូបភាព {template_filename} ក្នុង Folder ទេ"
          " សូមដាក់បញ្ចូលជាមុនសិន។",
      )
      return

    font_candidates = [
        "KhmerS4.ttf",
        "Khmer S4.ttf",
        "Khmer S4 Regular.ttf",
        "Battambang-Regular.ttf",
    ]
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
      font_item = (
          ImageFont.truetype(font_path, int(height * 0.0175))
          if font_path
          else ImageFont.load_default()
      )
      font_cust = (
          ImageFont.truetype(font_path, int(height * 0.018))
          if font_path
          else ImageFont.load_default()
      )
      font_total = (
          ImageFont.truetype(font_path, int(height * 0.023))
          if font_path
          else ImageFont.load_default()
      )
      font_date = (
          ImageFont.truetype(font_path, int(height * 0.016))
          if font_path
          else ImageFont.load_default()
      )
    except Exception:
      font_item = font_cust = font_total = font_date = ImageFont.load_default()

    start_y = height * 0.330
    row_height = height * 0.040
    col_name_x = width * 0.15
    col_qty_x = width * 0.57
    col_price_x = width * 0.71
    col_total_x = width * 0.87

    lines = data.get("items_list", [])
    computed_grand_total = 0.0

    for i, line in enumerate(lines[:12]):
      parsed = parse_item_line(line)
      computed_grand_total += parsed["total_num"]

      y = start_y + (i * row_height) + (row_height * 0.5)
      draw.text(
          (col_name_x, y), parsed["name"], fill="black", font=font_item, anchor="lm"
      )
      draw.text(
          (col_qty_x, y),
          parsed["qty_str"],
          fill="black",
          font=font_item,
          anchor="mm",
      )
      draw.text(
          (col_price_x, y),
          parsed["price_str"],
          fill="black",
          font=font_item,
          anchor="mm",
      )
      draw.text(
          (col_total_x, y),
          parsed["total_str"],
          fill="black",
          font=font_item,
          anchor="mm",
      )

    cust_x = width * 0.23
    c_name = data.get("name", "")
    c_phone = data.get("phone", "")
    c_location = data.get("location", "")
    total_num = data.get("total_num", computed_grand_total)
    c_total = data.get("total") or format_usd(total_num)

    draw.text((cust_x, height * 0.818), c_name, fill="blue", font=font_cust)
    draw.text((cust_x, height * 0.852), c_phone, fill="blue", font=font_cust)
    draw.text(
        (cust_x, height * 0.885), c_location, fill="blue", font=font_cust
    )

    draw.text(
        (width * 0.84, height * 0.822),
        c_total,
        fill="red",
        font=font_total,
        anchor="mm",
    )
    draw.text(
        (width * 0.77, height * 0.876),
        current_date,
        fill="red",
        font=font_date,
        anchor="mm",
    )

    output_path = os.path.join(BASE_DIR, f"invoice_{chat_id}.jpg")
    img.save(output_path, format="JPEG", quality=95)

    prefix = "SAL" if brand_name == "The Sal" else "PSC"
    tran_id = f"{prefix}{datetime.now().strftime('%y%m%d%H%M%S')}{chat_id}"
    transactions_store[tran_id] = {
        "brand": brand_name,
        "amount_num": total_num,
        "amount_str": c_total,
        "customer": c_name,
    }

    qr_payload, api_notice = request_aba_purchase_qr(
        tran_id, total_num, data, brand_name
    )
    qr_path = os.path.join(BASE_DIR, f"qr_{chat_id}.jpg")
    generate_qr_image(qr_payload, qr_path)

    with open(output_path, "rb") as inv_photo, open(qr_path, "rb") as qr_photo:
      media = [
          types.InputMediaPhoto(
              inv_photo,
              caption=f"🧾 វិក្កយបត្រហាង **{brand_name}** | Ref: `{tran_id}`",
              parse_mode="Markdown",
          ),
          types.InputMediaPhoto(
              qr_photo,
              caption=f"💳 ABA KHQR ({c_total}) | Ref: `{tran_id}`",
              parse_mode="Markdown",
          ),
      ]
      bot.send_media_group(chat_id, media)

    check_markup = types.InlineKeyboardMarkup()
    check_markup.add(
        types.InlineKeyboardButton(
            "🔄 ឆែកស្ថានភាពបង់ប្រាក់", callback_data=f"check_pay:{tran_id}"
        )
    )
    extra_note = f"\n{api_notice}" if api_notice else ""
    bot.send_message(
        chat_id,
        f"📌 លេខយោងប្រតិបត្តិការ៖ `{tran_id}`\nទឹកប្រាក់៖ **{c_total}**{extra_note}",
        parse_mode="Markdown",
        reply_markup=check_markup,
    )

  except Exception as e:
    bot.send_message(chat_id, f"⚠️ មានបញ្ហាក្នុងការបង្កើតរូបភាព៖ {str(e)}")
  finally:
    for p in (output_path, qr_path):
      if p and os.path.exists(p):
        os.remove(p)

  user_data[chat_id] = {"items_list": []}
  ask_item(chat_id)


bot.infinity_polling()
