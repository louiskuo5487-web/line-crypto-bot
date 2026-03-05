from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import datetime
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

def get_binance_price(symbol):
    symbol = symbol.upper().replace('PERP', '').replace('USDT', '') + 'USDT'
    url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if 'lastPrice' not in data:
            return None
        price = float(data['lastPrice'])
        change = float(data['priceChangePercent'])
        return {
            'symbol': data['symbol'],
            'price': price,
            'change': change
        }
    except:
        return None

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip().upper()
    
    if text in ['HELP', '幫助', '?', '指令']:
        msg = "📌 輸入幣種名稱即可查詢，例如：\n\nBTC\nETH\nSOL\nXRP\nDOGE\n\n支援 Binance USDT 永續合約"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    info = get_binance_price(text)
    if not info:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 找不到 {text} 的合約資料，請確認幣種名稱"))
        return

    tz = pytz.timezone('Asia/Taipei')
    now = datetime.datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

    change = info['change']
    if change > 0:
        change_str = f"📈 +{change:.2f}%"
    else:
        change_str = f"📉 {change:.2f}%"

    reply = f"""🪙 {info['symbol']} 永續合約

💰 價格: {info['price']:,.4f} USDT
{change_str}
⏰ 時間: {now} (台灣時間)"""

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
