if call.data == "inc_scan_old":
    bot.answer_callback_query(call.id, "កំពុងពិនិត្យសារក្នុង Group...")
    added_count = 0
    added_usd = 0.0
    added_khr = 0.0

    # ព្យាយាមអានសារដែលកំពុងមានក្នុង chat (ដំណើរការលើ Bot API / client ខ្លះដែលគាំទ្រ)
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
