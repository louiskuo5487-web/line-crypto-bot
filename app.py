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
    original = symbol.strip()
    cleaned = original.upper().replace('PERP', '').replace('USDT', '').strip()
    symbol_final = cleaned + 'USDT'
    
    url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol_final}"
    
    print(f"[DEBUG] 輸入: '{original}'")
    print(f"[DEBUG] 清理後: '{cleaned}' → 最終 symbol: {symbol_final}")
    print(f"[DEBUG] 請求 URL: {url}")
    
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        print(f"[DEBUG] 狀態碼: {r.status_code}")
        print(f"[DEBUG] 回應長度: {len(r.text)} 字")
        print(f"[DEBUG] 回應前300字: {r.text[:300]}...")
        
        if r.status_code != 200:
            return f"API 錯誤 {r.status_code}: {r.text[:200]}"
        
        data = r.json()
        print(f"[DEBUG] JSON keys: {list(data.keys())}")
        
        if isinstance(data, list):
            if data:
                data = data[0]
            else:
                return "API 回空陣列"
        
        if 'lastPrice' not in data:
            return f"缺少 lastPrice key，回應: {r.text[:200]}"
        
        price = float(data['lastPrice'])
        change = float(data.get('priceChangePercent', 0))
        
        return {
            'symbol': data.get('symbol', symbol_final),
            'price': price,
            'change': change
        }
    except requests.exceptions.RequestException as e:
        print(f"[REQUEST ERROR] {str(e)}")
        return f"網路錯誤: {str(e)}"
    except ValueError as e:
        print(f"[JSON ERROR] {str(e)}")
        return f"JSON 解析錯誤: {str(e)}"
    except Exception as e:
        print(f"[其他錯誤] {str(e)}")
        return f"未知錯誤: {str(e)}"

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
    if not info or isinstance(info, str):  # 如果是錯誤字串
        error_msg = info if isinstance(info, str) else "找不到資料"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 錯誤: {error_msg}\n\n請把 Railway Deploy Logs 的 [DEBUG] 內容貼給我"))
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

