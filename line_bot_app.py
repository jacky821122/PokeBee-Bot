import os
import re
from flask import Flask, request, abort
import datetime
from pathlib import Path

from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FileMessage

from daily_metrics import calculate_daily_metrics
from report_renderer import render_daily_report
from metrics_common import _PROJECT_ROOT


# === LINE 設定 ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set")
ALLOWED_USER_IDS = {
    "U93300c2024ddf77f75adb10d4c7a0944"  # 你的 LINE userId
}

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(LINE_CHANNEL_SECRET)

app = Flask(__name__)


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        abort(400)

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
       
        # 👇 TextMessage
        if isinstance(event.message, TextMessage):
            handle_text_message(event)
       
        # 👇 FileMessage（新增）
        elif isinstance(event.message, FileMessage):
            handle_file_message(event)

    return "OK"


def handle_text_message(event: MessageEvent):
    user_id = event.source.user_id
    if user_id not in ALLOWED_USER_IDS:
        return  # 直接不回或回固定訊息

    source = event.source
    is_group = hasattr(source, "group_id")

    text = event.message.text.strip()

    if is_group:
        if not text.startswith("分析"):
            return  # 完全不回

    # 指令格式：分析 YYYY-MM-DD
    if text.startswith("分析"):
        parts = text.split()
        if len(parts) != 2:
            reply_text = "❌ 指令格式錯誤，請使用：分析 YYYY-MM-DD"
        elif parts[1] == "今天":
            reply_text = handle_analysis_command(datetime.date.today().isoformat())
        elif parts[1] == "昨天":
            reply_text = handle_analysis_command((datetime.date.today() - datetime.timedelta(days=1)).isoformat())
        else:
            date = parts[1]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                reply_text = "❌ 日期格式錯誤，請使用：YYYY-MM-DD"
            else:
                try:
                    datetime.date.fromisoformat(date)
                except ValueError:
                    reply_text = "❌ 日期不存在，請確認日期是否正確"
                else:
                    reply_text = handle_analysis_command(date)
    else:
        reply_text = "🤖 我目前只支援指令：分析 YYYY-MM-DD"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )


def handle_analysis_command(date: str) -> str:
    try:
        result = calculate_daily_metrics(date)
        if result is None:
            return f"⚠️ 找不到 {date} 的營業資料，請確認 CSV 是否已匯入。"

        return render_daily_report(result)

    except Exception as e:
        return f"❌ 分析失敗：{str(e)}"

def handle_file_message(event):
    # 1. 只允許 1:1
    if event.source.type != "user":
        return

    user_id = event.source.user_id
    if user_id not in ALLOWED_USER_IDS:
        return  # 直接不回或回固定訊息

    file_name = event.message.file_name

    # 2. 檢查檔名（iCHEF 原始格式）
    if not (
        file_name.startswith("Payment_Void Record_")
        and file_name.endswith(".csv")
    ) and not (
        file_name.startswith("modifier")
        and file_name.endswith(".csv")
    ):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ 檔名不是 iCHEF 匯出格式，請直接上傳原始 CSV")
        )
        return

    # 3. 決定儲存路徑（依上傳月份）
    today = datetime.datetime.today().strftime("%Y-%m")
    raw_dir = _PROJECT_ROOT / "data" / "ichef" / "raw" / today
    raw_dir.mkdir(parents=True, exist_ok=True)

    save_path = raw_dir / file_name

    # 4. 下載檔案內容
    message_content = line_bot_api.get_message_content(event.message.id)
    with open(save_path, "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    # 5. 呼叫 import
    try:
        from import_csv import import_csv  # 依你實際檔名調整
        from import_modifier_csv import import_modifier_csv
        if file_name.startswith("Payment"):
            result = import_csv(str(save_path))
        elif file_name.startswith("modifier"):
            result = import_modifier_csv(str(save_path))
    except Exception as e:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"❌ Import failed:\n{e}")
        )
        return

    # 6. 回傳結果（完全照你的原始 log）
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=result)
    )

if __name__ == "__main__":
    #app.run(host="0.0.0.0", port=8000, debug=True)
    app.run(host="0.0.0.0", port=8000)
