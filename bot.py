from datetime import datetime, timedelta, timezone
import json
import os
import re
import time
from PIL import Image, ImageDraw, ImageFont
import telebot
from telebot import types

try:
  from zoneinfo import ZoneInfo

  KH_TZ = ZoneInfo("Asia/Phnom_Penh")
except Exception:
  KH_TZ = timezone(timedelta(hours=7))


def now_kh():
  return datetime.now(KH_TZ)


def get_khmer_date_str():
  return "កាលបរិច្ឆេទ : " + now_kh().strftime("%d / %m / %Y")


TOKEN = os.environ.get(
    "BOT_TOKEN", "9274188079:AAGDENXlzH4vlYUQwLFoK0d0zVBLH7tbX-Q"
)
bot = telebot.TeleBot(TOKEN, parse_mode=None)

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
          data.setdefault("_seen_msgs", {})
          return data
    except Exception:
      pass
  return {"_seen_msgs": {}}


def save_income_data(data):
  try:
    with open(INCOME_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


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
      "បានផ្ទេរចេញ",
      "ចំណាយ",
  ]
  if any(k in low for k in out_keywords):
    return False

  in_keywords = [
      "ត្រូវបានបង់ដោយ",
      "aba khqr",
      "khqr",
      "received",
      "credited",
      "credit",
      "deposit",
      "incoming",
      "paid by",
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


def record_payment_message(chat_id, msg_id, msg_date_ts, text):
  """កត់ត្រាលុយចូលម្ដងមួយសារដោយការពារមិនឱ្យបូកជាន់ message_id ដដែល។"""
  if not text or text.strip().startswith("/"):
    return 0.0, 0.0, False
  if not is_incoming_payment_text(text):
    return 0.0, 0.0, False

  usd_found, khr_found = extract_amounts_from_text(text)
  if usd_found <= 0 and khr_found <= 0:
    return 0.0, 0.0, False

  chat_key = str(chat_id)
  seen_map = income_data.setdefault("_seen_msgs", {})
  seen_ids = seen_map.setdefault(chat_key, [])
  if msg_id is not None and msg_id in seen_ids:
    return 0.0, 0.0, False

  msg_dt = (
      datetime.fromtimestamp(msg_date_ts, tz=KH_TZ) if msg_date_ts else now_kh()
  )
  month_key = msg_dt.strftime("%Y-%m")

  income_data.setdefault(chat_key, {})
  entry = income_data[chat_key].setdefault(
      month_key, {"usd": 0.0, "khr": 0.0, "count": 0}
  )

  entry["usd"] = round(float(entry.get("usd", 0.0)) + usd_found, 2)
  entry["khr"] = round(float(entry.get("khr", 0.0)) + khr_found, 2)
  entry["count"] = int(entry.get("count", 0)) + 1

  if msg_id is not None:
    seen_ids.append(msg_id)
    if len(seen_ids) > 2000:
      seen_map[chat_key] = seen_ids[-2000:]

  save_income_data(income_data)
  return usd_found, khr_found, True


def build_income_menu_markup():
  markup = types.InlineKeyboardMarkup()
  markup.row(
      types.InlineKeyboardButton("ប្រចាំខែ", callback_data="inc_month_now"),
      types.InlineKeyboardButton("ប្រចាំឆ្នាំ", callback_data="inc_year_now"),
  )
  markup.row(
      types.InlineKeyboardButton(
          "រើសខែដែចង់បូក", callback_data="inc_pick_month"
      ),
      types.InlineKeyboardButton("📥 បូកសារចាស់", callback_data="inc_scan_old"),
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


def wrap_text_by_pixel_width(draw, text, font, max_width):
  """បំបែកអត្ថបទឱ្យចុះបន្ទាត់ស្វ័យប្រវត្តិ ពេលប្រវែងលើសពី max_width។"""
  if not text:
    return [""]

  tokens = re.findall(r"\S+\s*|\s+", str(text))
  lines = []
  current = ""

  for tok in tokens:
    candidate = current + tok
    bbox = draw.textbbox((0, 0), candidate.rstrip(), font=font)
    w = bbox[2] - bbox[0]
    if w <= max_width or not current.strip():
      current = candidate
    else:
      lines.append(current.rstrip())
      current = tok.lstrip()

  if current.strip():
    lines.append(current.rstrip())

  return lines if lines else [str(text)]


@bot.message_handler(commands=["ping"])
def cmd_ping(message):
  bot.reply_to(message, "✅ Bot កំពុងដំណើរការធម្មតា!")


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
          parse_mode="Markdown",
      )
  else:
    bot.send_message(
        chat_id,
        "👋 **សួស្តី! សូមស្វាគមន៍មកកាន់ប្រព័ន្ធគ្រប់គ្រងវិក្កយបត្រហាង THE SAL &"
        " P.S.C**",
        parse_mode="Markdown",
    )

  ask_item(chat_id)


@bot.message_handler(commands=["month", "income"], func=lambda m: True)
def cmd_monthly_income(message):
  chat_id_str = str(message.chat.id)
  now = now_kh()
  raw_text = (message.text or "").strip()
  parts = raw_text.split()

  arg = parts[1] if len(parts) > 1 else ""
  if arg and re.fullmatch(r"\d{4}-\d{2}", arg):
    text_out = get_month_summary_text(chat_id_str, arg)
  else:
    text_out = get_month_summary_text(chat_id_str, now.strftime("%Y-%m"))

  bot.send_message(
      message.chat.id,
      text_out,
      parse_mode="Markdown",
      reply_markup=build_income_menu_markup(),
  )


@bot.message_handler(
    func=lambda m: (
        m.chat.type in ("group", "supergroup")
        and not (m.text or m.caption or "").strip().startswith("/")
    ),
    content_types=["text", "photo", "document"],
)
def track_group_incoming_money(message):
  text = (message.text or message.caption or "").strip()
  record_payment_message(
      message.chat.id, message.message_id, message.date, text
  )


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
  now = now_kh()

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

  if call.data == "inc_scan_old":
    bot.answer_callback_query(call.id, "កំពុងពិនិត្យសារក្នុង Group...")
    added_count = 0
    added_usd = 0.0
    added_khr = 0.0

    start_mid = max(1, (call.message.message_id or 1) - 100)
    for mid in range(start_mid, (call.message.message_id or 1)):
      try:
        copied = bot.forward_message(chat_id, chat_id, mid)
        try:
          bot.delete_message(chat_id, copied.message_id)
        except Exception:
          pass
        txt = (copied.text or copied.caption or "").strip()
        u, k, ok = record_payment_message(chat_id, mid, copied.date, txt)
        if ok:
          added_count += 1
          added_usd += u
          added_khr += k
      except Exception:
        continue

    summary = get_month_summary_text(chat_id_str, now.strftime("%Y-%m"))
    note = (
        f"\n\n✅ បានបូកបន្ថែម `{added_count}` សារ (`{format_usd(added_usd)}` /"
        f" `{format_khr(added_khr)}`)"
        if added_count > 0
        else "\n\nℹ️ រកមិនឃើញសារលុយចូលថ្មីបន្ថែមទេ"
    )
    bot.edit_message_text(
        summary + note,
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
  current_date = get_khmer_date_str()
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

    loc_y_start = height * 0.885
    loc_line_height = height * 0.022
    max_loc_width = width * 0.46
    loc_lines = wrap_text_by_pixel_width(
        draw, c_location, font_cust, max_loc_width
    )
    for idx, loc_line in enumerate(loc_lines[:3]):
      draw.text(
          (cust_x, loc_y_start + (idx * loc_line_height)),
          loc_line,
          fill="blue",
          font=font_cust,
      )

    draw.text(
        (width * 0.84, height * 0.822),
        c_total,
        fill="red",
        font=font_total,
        anchor="mm",
    )

    date_center_x = int(width * 0.77)
    date_center_y = int(height * 0.892)

    bbox = draw.textbbox((0, 0), current_date, font=font_date)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x = int(width * 0.015)
    pad_y = int(height * 0.006)
    box_w = text_w + (pad_x * 2)
    box_h = text_h + (pad_y * 2)

    box_left = date_center_x - (box_w // 2)
    box_top = date_center_y - (box_h // 2)
    box_right = box_left + box_w
    box_bottom = box_top + box_h

    draw.rounded_rectangle(
        [box_left, box_top, box_right, box_bottom],
        radius=int(min(box_w, box_h) * 0.25),
        fill="white",
        outline="red",
        width=2,
    )
    draw.text(
        (date_center_x, date_center_y),
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


if __name__ == "__main__":
  try:
    bot.remove_webhook()
  except Exception:
    pass

  while True:
    try:
      bot.polling(
          non_stop=True,
          skip_pending=True,
          timeout=30,
          long_polling_timeout=25,
      )
    except Exception as e:
      print(f"Polling error: {e}")
      time.sleep(5)
