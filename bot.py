from datetime import datetime
import json
import os
import re
from PIL import Image, ImageDraw, ImageFont
import telebot
from telebot import types

TOKEN = "9274188079:AAGDENXlzH4vlYUQwLFoK0d0zVBLH7tbX-Q"
bot = telebot.TeleBot(TOKEN)

user_data = {}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INCOME_FILE = os.path.join(BASE_DIR, "monthly_income.json")

KHMER_MONTHS = {
    1: "មករា",
    2: "កុម្ភៈ",
    3: "មីនា",
    4: "មេសា",
    5: "ឧសភា",
    6: "មិថុនា",
    7: "កក្កដា",
    8: "សីហា",
    9: "កញ្ញា",
    10: "តុលា",
    11: "វិច្ឆិកា",
    12: "ធ្នូ",
}


# ==========================================
# 💰 មុខងារបូកលុយចូលប្រចាំខែ & ប្រចាំឆ្នាំ
# ==========================================
def load_income_data():
  if os.path.exists(INCOME_FILE):
    try:
      with open(INCOME_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
          return data
    except Exception:
      pass
  return {}


def save_income_data(data):
  with open(INCOME_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


income_data = load_income_data()


def is_incoming_payment_text(text):
  """ពិនិត្យថាតើសារជាការលុយចូល (មិនមែនលុយចេញ/ដក)។"""
  if not text:
    return False
  low = text.lower()

  out_keywords = [
      "sent ",
      "transferred to",
      "transfer out",
      "withdraw",
      "withdrawn",
      "debit",
      "paid to",
      "payment to",
      "ផ្ទេរចេញ",
      "ដកប្រាក់",
      "ចំណាយ",
  ]
  if any(k in low for k in out_keywords):
    return False

  in_keywords = [
      "ត្រូវបានបង់ដោយ",
      "received",
      "credited",
      "credit",
      "deposit",
      "incoming",
      "paid by",
      "from ",
      "khqr",
      "aba",
      "បានទទួល",
      "លុយចូល",
      "ទទួលបាន",
      "ចូលគណនី",
  ]
  return any(k in low for k in in_keywords)


def extract_amounts_from_text(text):
  """ទាញយកទឹកប្រាក់ USD ($) និង KHR (៛) ពីសារ។"""
  usd_total = 0.0
  khr_total = 0.0

  for m in re.finditer(
      r"\$\s*([\d,]+(?:\.[\d]+)?)|([\d,]+(?:\.[\d]+)?)\s*(?:\$|usd)\b",
      text,
      flags=re.IGNORECASE,
  ):
    val_str = (m.group(1) or m.group(2) or "").replace(",", "")
    try:
      usd_total += float(val_str)
    except ValueError:
      pass

  for m in re.finditer(
      r"([\d,]+(?:\.[\d]+)?)\s*(?:៛|khr)\b", text, flags=re.IGNORECASE
  ):
    val_str = (m.group(1) or "").replace(",", "")
    try:
      khr_total += float(val_str)
    except ValueError:
      pass

  return usd_total, khr_total


def format_khr(amount):
  val = float(amount)
  if val.is_integer():
    return f"{int(val):,}៛"
  return f"{val:,.2f}៛"


def build_income_menu_markup():
  markup = types.InlineKeyboardMarkup()
  markup.row(
      types.InlineKeyboardButton("ប្រចាំខែ", callback_data="inc_month_now"),
      types.InlineKeyboardButton("ប្រចាំឆ្នាំ", callback_data="inc_year_now"),
  )
  markup.row(
      types.InlineKeyboardButton(
          "រើសខែដែចង់បូក", callback_data="inc_pick_month"
      )
  )
  return markup


def build_pick_month_markup(year_str):
  markup = types.InlineKeyboardMarkup(row_width=3)
  buttons = []
  for m_num in range(1, 13):
    m_key = f"{year_str}-{m_num:02d}"
    label = f"ខែ{KHMER_MONTHS[m_num]} ({m_num:02d})"
    buttons.append(
        types.InlineKeyboardButton(label, callback_data=f"inc_sel_month:{m_key}")
    )
  markup.add(*buttons)
  markup.row(
      types.InlineKeyboardButton("⬅️ ត្រឡប់ក្រោយ", callback_data="inc_back_menu")
  )
  return markup


def get_month_summary_text(chat_id_str, month_key):
  entry = income_data.get(chat_id_str, {}).get(
      month_key, {"usd": 0.0, "khr": 0.0, "count": 0}
  )
  usd_val = float(entry.get("usd", 0.0))
  khr_val = float(entry.get("khr", 0.0))
  count_val = int(entry.get("count", 0))

  try:
    yr, mo = month_key.split("-")
    kh_label = f"ខែ{KHMER_MONTHS.get(int(mo), mo)} {yr}"
  except Exception:
    kh_label = month_key

  return (
      f"📊 **សរុបលុយចូលប្រចាំខែ — {kh_label} (`{month_key}`)**\n\n"
      f"💵 **USD៖** `{format_usd(usd_val)}`\n"
      f"🇰🇭 **KHR៖** `{format_khr(khr_val)}`\n"
      f"🔢 **ចំនួនប្រតិបត្តិការចូល៖** `{count_val}` ដង"
  )


def get_year_summary_text(chat_id_str, year_str):
  chat_months = income_data.get(chat_id_str, {})
  usd_sum = 0.0
  khr_sum = 0.0
  count_sum = 0

  for m_key, entry in chat_months.items():
    if str(m_key).startswith(f"{year_str}-"):
      usd_sum += float(entry.get("usd", 0.0))
      khr_sum += float(entry.get("khr", 0.0))
      count_sum += int(entry.get("count", 0))

  return (
      f"📈 **សរុបលុយចូលប្រចាំឆ្នាំ (`{year_str}`)**\n\n"
      f"💵 **USD៖** `{format_usd(usd_sum)}`\n"
      f"🇰🇭 **KHR៖** `{format_khr(khr_sum)}`\n"
      f"🔢 **ចំនួនប្រតិបត្តិការចូល៖** `{count_sum}` ដង"
  )


@bot.message_handler(commands=["month", "income"])
def cmd_monthly_income(message):
  chat_id_str = str(message.chat.id)
  now = datetime.now()
  parts = (message.text or "").strip().split()

  if len(parts) > 1 and re.fullmatch(r"\d{4}-\d{2}", parts[1]):
    text_out = get_month_summary_text(chat_id_str, parts[1])
  else:
    text_out = get_month_summary_text(chat_id_str, now.strftime("%Y-%m"))

  bot.reply_to(
      message, text_out, parse_mode="Markdown", reply_markup=build_income_menu_markup()
  )


@bot.message_handler(
    func=lambda m: m.chat.type in ("group", "supergroup"),
    content_types=["text", "photo", "document"],
)
def track_group_incoming_money(message):
  text = (message.text or message.caption or "").strip()
  if not text or text.startswith("/"):
    return

  if not is_incoming_payment_text(text):
    return

  usd_found, khr_found = extract_amounts_from_text(text)
  if usd_found <= 0 and khr_found <= 0:
    return

  chat_id = str(message.chat.id)
  msg_dt = (
      datetime.fromtimestamp(message.date) if message.date else datetime.now()
  )
  month_key = msg_dt.strftime("%Y-%m")

  income_data.setdefault(chat_id, {})
  entry = income_data[chat_id].setdefault(
      month_key, {"usd": 0.0, "khr": 0.0, "count": 0}
  )

  entry["usd"] = round(float(entry.get("usd", 0.0)) + usd_found, 2)
  entry["khr"] = round(float(entry.get("khr", 0.0)) + khr_found, 2)
  entry["count"] = int(entry.get("count", 0)) + 1
  save_income_data(income_data)


# ==========================================
# 🧾 មុខងារចេញវិក្កយបត្រ (THE SAL & P.S.C)
# ==========================================
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


def split_item_line(line):
  text = line.strip()
  if "|" in text:
    return [p.strip() for p in text.split("|")]
  if "," in text:
    return [p.strip() for p in text.split(",")]
  if "/" in text:
    return [p.strip() for p in text.split("/")]
  return [text]


def parse_item_line(line):
  parts = split_item_line(line)
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
      else (
          f"{price_raw}$"
          if price_raw and not price_raw.endswith("$")
          else price_raw
      )
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
      "🛍️ សូមបញ្ចូល **មុខទំនិញ ចំនួន និងតម្លៃរាយ**"
      " (ប្រព័ន្ធគណនាតម្លៃសរុបឱ្យស្វ័យប្រវត្តិ):\n"
      "`ឈ្មោះទំនិញ, ចំនួន, តម្លៃរាយ`\n\n"
      "ឧទាហរណ៍:\n"
      "ប៊ូសចង្កូត, 1, 15$\n"
      "សំបកកង់, 4, 50$",
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
    if any(sep in line for sep in ("|", ",", "/")):
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
  chat_id_str = str(chat_id)
  now = datetime.now()

  # ប៊ូតុងរបាយការណ៍លុយចូល (មិនប៉ះពាល់ដល់ step handler របស់វិក្កយបត្រទេ)
  if call.data == "inc_month_now":
    bot.answer_callback_query(call.id, "កំពុងបង្ហាញប្រចាំខែ...")
    txt = get_month_summary_text(chat_id_str, now.strftime("%Y-%m"))
    bot.edit_message_text(
        txt,
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=build_income_menu_markup(),
    )
    return

  if call.data == "inc_year_now":
    bot.answer_callback_query(call.id, "កំពុងបង្ហាញប្រចាំឆ្នាំ...")
    txt = get_year_summary_text(chat_id_str, now.strftime("%Y"))
    bot.edit_message_text(
        txt,
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=build_income_menu_markup(),
    )
    return

  if call.data == "inc_pick_month":
    bot.answer_callback_query(call.id, "ជ្រើសរើសខែដែលចង់បូក")
    yr_str = now.strftime("%Y")
    bot.edit_message_text(
        f"📅 **រើសខែដែចង់បូក (ឆ្នាំ `{yr_str}`)**",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=build_pick_month_markup(yr_str),
    )
    return

  if call.data and call.data.startswith("inc_sel_month:"):
    m_key = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id, f"បូកលុយខែ {m_key}")
    txt = get_month_summary_text(chat_id_str, m_key)
    yr_str = m_key.split("-")[0] if "-" in m_key else now.strftime("%Y")
    bot.edit_message_text(
        txt,
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=build_pick_month_markup(yr_str),
    )
    return

  if call.data == "inc_back_menu":
    bot.answer_callback_query(call.id, "ត្រឡប់ទៅម៉ឺនុយ")
    txt = get_month_summary_text(chat_id_str, now.strftime("%Y-%m"))
    bot.edit_message_text(
        txt,
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=build_income_menu_markup(),
    )
    return

  bot.clear_step_handler_by_chat_id(chat_id)

  if call.data == "add_more":
    bot.answer_callback_query(
        call.id, "សូមវាយបញ្ចូល ឬ Paste មុខទំនិញបន្ថែម៖"
    )
    msg = bot.send_message(
        chat_id,
        "សូមវាយបញ្ចូលមុខទំនិញបន្ថែម៖\n`ឈ្មោះទំនិញ, ចំនួន, តម្លៃរាយ`",
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


def generate_invoice_image(chat_id, template_filename, brand_name):
  data = user_data[chat_id]
  current_date = "កាលបរិច្ឆេទ : " + datetime.now().strftime("%d / %m / %Y")
  output_path = None

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

    with open(output_path, "rb") as photo:
      bot.send_photo(
          chat_id,
          photo,
          caption=f"🧾 **នេះជារូបភាពវិក្កយបត្ររបស់អ្នកហាង {brand_name}!**",
          parse_mode="Markdown",
      )

  except Exception as e:
    bot.send_message(chat_id, f"⚠️ មានបញ្ហាក្នុងការបង្កើតរូបភាព៖ {str(e)}")
  finally:
    if output_path and os.path.exists(output_path):
      os.remove(output_path)

  user_data[chat_id] = {"items_list": []}
  ask_item(chat_id)


bot.infinity_polling()
