import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import fitz  # PyMuPDF

# حذف واترمارک تصویری
def remove_images(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    for page in doc:
        image_list = page.get_images(full=True)
        for image in image_list:
            xref = image[0]
            page.delete_image(xref)
    doc.save(output_pdf)
    doc.close()

# حذف لینک‌های کلیک‌پذیر (وب‌سایت، انجمن‌ها) و متن‌های دارای @
def remove_links_and_at_text(input_pdf, output_pdf):
    patterns = ["http://", "https://", "t.me/", "@"]  # الگوهای لینک‌ها و @
    doc = fitz.open(input_pdf)

    for page in doc:
        text_instances = []

        # دریافت لیست لینک‌های کلیک‌پذیر
        links = page.get_links()

        # حذف لینک‌های کلیک‌پذیر
        for link in links:
            uri = link.get("uri", "")
            if any(pattern in uri for pattern in patterns):
                if "from" in link:  # اگر لینک به متن متصل است
                    rect = fitz.Rect(link["from"])
                    text_instances.append(rect)

        # حذف متن‌های دارای @
        text_blocks = page.get_text("blocks")
        for block in text_blocks:
            text = block[4]  # متن بلوک
            if "@" in text:
                rect = fitz.Rect(block[:4])  # مختصات بلوک
                text_instances.append(rect)

        # حذف متن‌ها و لینک‌ها
        for rect in text_instances:
            page.add_redact_annot(rect)  # ایجاد ناحیه حذف
            page.apply_redactions()  # حذف متن

    # فشرده‌سازی فایل بعد از حذف
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()

# اضافه کردن سربرگ با لینک کلیک‌پذیر (پایین چپ)
def add_watermark_text(input_pdf, output_pdf, watermark_text="Romandl", link="https://t.me/romandl"):
    doc = fitz.open(input_pdf)

    for page in doc:
        # حذف سربرگ قبلی (اگر وجود داشت)
        text_instances = page.search_for(watermark_text)
        for inst in text_instances:
            page.add_redact_annot(inst)  # ایجاد ناحیه حذف
            page.apply_redactions()  # حذف متن

        # اضافه کردن سربرگ جدید در پایین چپ
        text_position = fitz.Point(50, 750)  # x=50 (چپ)، y=750 (پایین)
        page.insert_text(text_position, watermark_text, fontsize=18, color=(1, 0, 0))  # رنگ قرمز، اندازه بزرگ‌تر

        # ایجاد لینک روی متن "Romandl" در پایین چپ
        link_rect = fitz.Rect(50, 745, 150, 765)  # تنظیم مختصات لینک متناسب با متن
        page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": link})

    doc.save(output_pdf)
    doc.close()

# حذف صفحه خاص
def remove_page(input_pdf, output_pdf, page_number):
    doc = fitz.open(input_pdf)
    doc.delete_page(page_number - 1)  # شماره صفحه از ۰ شروع می‌شود
    doc.save(output_pdf)
    doc.close()

# فشرده‌سازی PDF
def compress_pdf(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()

# منوی اصلی
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🔹 حذف واترمارک", callback_data='remove_watermark')],
        [InlineKeyboardButton("🔹 حذف لینک‌ها و متن @", callback_data='remove_links')],
        [InlineKeyboardButton("🔹 اضافه کردن سربرگ", callback_data='add_watermark')],
        [InlineKeyboardButton("🔹 فشرده‌سازی PDF", callback_data='compress_pdf')],
        [InlineKeyboardButton("🔹 حذف صفحه خاص", callback_data='remove_page')]  # دکمه جدید
    ]
    return InlineKeyboardMarkup(keyboard)

# شروع ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=get_main_menu())

# کلیک روی دکمه‌ها
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['action'] = query.data

    messages = {
        "remove_watermark": "📌 لطفاً فایل PDF را ارسال کنید تا واترمارک حذف شود.",
        "remove_links": "📌 لطفاً فایل PDF را ارسال کنید تا لینک‌ها و متن‌های @ حذف شوند.",
        "add_watermark": "📌 لطفاً فایل PDF را ارسال کنید تا سربرگ اضافه شود.",
        "compress_pdf": "📌 لطفاً فایل PDF را ارسال کنید تا فشرده شود.",
        "remove_page": "📌 لطفاً فایل PDF را ارسال کنید و شماره صفحه‌ای که می‌خواهید حذف شود را بنویسید."  # پیام جدید
    }
    await query.edit_message_text(messages[query.data])

# پردازش فایل PDF
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.document.file_id
    file = await context.bot.get_file(file_id)
    file_size = file.file_size  # اندازه فایل به بایت

    # محدودیت ۳۰ مگابایت (۳۰ * 1024 * 1024 بایت)
    if file_size > 30 * 1024 * 1024:
        await update.message.reply_text("❌ حجم فایل ارسالی بیشتر از ۳۰ مگابایت است. لطفاً فایل کوچک‌تری ارسال کنید.")
        return

    # دانلود فایل
    await file.download_to_drive("received_file.pdf")

    output_file = "processed_file.pdf"
    action = context.user_data.get('action')

    if action == "remove_watermark":
        remove_images("received_file.pdf", output_file)
        await update.message.reply_text("✅ واترمارک‌ها حذف شدند. ارسال فایل...")
    elif action == "remove_links":
        remove_links_and_at_text("received_file.pdf", output_file)
        await update.message.reply_text("✅ لینک‌ها و متن‌های @ حذف شدند. ارسال فایل...")
    elif action == "add_watermark":
        add_watermark_text("received_file.pdf", output_file)
        await update.message.reply_text("✅ سربرگ اضافه شد. ارسال فایل...")
    elif action == "compress_pdf":
        compress_pdf("received_file.pdf", output_file)
        await update.message.reply_text("✅ فایل فشرده شد. ارسال فایل...")
    elif action == "remove_page":
        # دریافت شماره صفحه از کاربر
        await update.message.reply_text("📌 لطفاً شماره صفحه‌ای که می‌خواهید حذف شود را وارد کنید (مثلاً ۱):")
        return

    # فشرده‌سازی نهایی فایل (اختیاری)
    compressed_file = "@Romandl.pdf"
    compress_pdf(output_file, compressed_file)

    await update.message.reply_document(open(compressed_file, "rb"))

    # حذف فایل‌های موقت
    os.remove("received_file.pdf")
    os.remove(output_file)
    os.remove(compressed_file)

    await start(update, context)

# دریافت شماره صفحه و حذف آن
async def handle_page_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        page_number = int(update.message.text)
        if page_number < 1:
            await update.message.reply_text("❌ شماره صفحه باید بزرگ‌تر از ۰ باشد.")
            return

        # حذف صفحه
        remove_page("received_file.pdf", "processed_file.pdf", page_number)
        await update.message.reply_text(f"✅ صفحه {page_number} حذف شد. ارسال فایل...")

        # فشرده‌سازی نهایی فایل (اختیاری)
        compressed_file = "@Romandl.pdf"
        compress_pdf("processed_file.pdf", compressed_file)

        await update.message.reply_document(open(compressed_file, "rb"))

        # حذف فایل‌های موقت
        os.remove("received_file.pdf")
        os.remove("processed_file.pdf")
        os.remove(compressed_file)

        await start(update, context)
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")

# راه‌اندازی ربات
def main():
    application = Application.builder().token("5473579370:AAEXJYS7Val4ObKjWQ5DsJUqr_jlqU-m2bc").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.Document.MimeType("application/pdf"), handle_pdf))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_page_number))  # دریافت شماره صفحه

    application.run_polling()

if __name__ == "__main__":
    main()