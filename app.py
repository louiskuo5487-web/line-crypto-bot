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

def get_okx_price(symbol):
    original = symbol.strip()
    cleaned = original.upper().replace('PERP', '').replace('USDT', '').strip()
    symbol_final = cleaned + '-USDT-SWAP'  # OKX 永續合約格式：BTC-USDT-SWAP
    
    url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol_final}"
    
    print(f"[DEBUG] 輸入: '{original}' → 最終 instId: {symbol_final}")
    print(f"[DEBUG] OKX URL: {url}")
    
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        print(f"[DEBUG] 狀態碼: {r.status_code}")
        print(f"[DEBUG] 回應前300字: {r.text[:300]}...")
        
        if r.status_code != 200:
            return f"OKX API 錯誤 {r.status_code}: {r.text[:200]}"
        
        data = r.json()
        print(f"[DEBUG] 回應 keys: {list(data.keys())}")
        
        if data.get('code') != '0':
            return f"OKX 錯誤: {data.get('msg')}"
        
        ticker = data['data'][0]
        price = float(ticker['last'])
        open24h = float(ticker['open24h'])
        change = ((price - open24h) / open24h) * 100 if open24h != 0 else 0
        
        return {
            'symbol': ticker['instId'].replace('-USDT-SWAP', ''),
            'price': price,
            'change': change
        }
    except Exception as e:
        print(f"[DEBUG] 錯誤: {str(e)}")
        return f"網路/解析錯誤: {str(e)}"

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
        msg = "📌 輸入幣種名稱即可查詢，例如：\n\nBTC\nETH\nSOL\nXRP\nDOGE\n\n支援 OKX USDT 永續合約"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
    
    info = get_okx_price(text)
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
