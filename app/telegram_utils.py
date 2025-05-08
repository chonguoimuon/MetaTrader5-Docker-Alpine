import logging
import requests
import MetaTrader5 as mt5
from datetime import datetime

logger = logging.getLogger(__name__)

# Cấu hình Telegram lưu trong bộ nhớ
telegram_config = {
    "bot_token": "",
    "chat_id": "",
    "enabled": False
}

def set_telegram_config(bot_token, chat_id):
    """Thiết lập hoặc cập nhật cấu hình Telegram."""
    try:
        telegram_config["bot_token"] = bot_token
        telegram_config["chat_id"] = chat_id
        logger.info("Telegram config updated in memory.")
    except Exception as e:
        logger.error(f"Error setting Telegram config: {str(e)}")

def get_telegram_config():
    """Lấy cấu hình Telegram hiện tại."""
    return telegram_config

def send_telegram_message(message):
    """Gửi tin nhắn đến Telegram."""
    if not telegram_config["enabled"]:
        logger.info("Telegram signal sending is disabled.")
        return False
    if not telegram_config["bot_token"] or not telegram_config["chat_id"]:
        logger.error("Telegram bot token or chat ID not configured.")
        return False

    url = f"https://api.telegram.org/bot{telegram_config['bot_token']}/sendMessage"
    payload = {
        "chat_id": telegram_config["chat_id"],
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info("Telegram message sent successfully.")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram message: {str(e)}")
        return False

def format_trade_signal(deal, position_ticket=None, action="open", **kwargs):
    """Định dạng tín hiệu giao dịch từ deal hoặc vị thế."""
    deal_dict = deal if isinstance(deal, dict) else deal._asdict()
    symbol = deal_dict.get("symbol", "N/A")
    volume = deal_dict.get("volume", 0.0)
    price = deal_dict.get("price", 0.0)
    order_type = "BUY" if deal_dict.get("type") == mt5.DEAL_TYPE_BUY else "SELL" if deal_dict.get("type") == mt5.DEAL_TYPE_SELL else "N/A"
    timestamp = deal_dict.get("time", 0)
    time_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "open":
        message = (
            "🔔 *New Trade Signal (MT5)*\n"
            f"Symbol: {symbol}\n"
            f"Type: {order_type}\n"
            f"Volume: {volume:.2f}\n"
            f"Price: {price:.5f}\n"
            f"Time: {time_str}\n"
            f"Position Ticket: {position_ticket if position_ticket else 'N/A'}"
        )
    elif action == "close":
        profit = deal_dict.get("profit", 0.0)
        message = (
            "🔔 *Position Closed (MT5)*\n"
            f"Symbol: {symbol}\n"
            f"Type: {order_type}\n"
            f"Volume: {volume:.2f}\n"
            f"Close Price: {price:.5f}\n"
            f"Profit: {profit:.2f}\n"
            f"Time: {time_str}\n"
            f"Position Ticket: {position_ticket if position_ticket else 'N/A'}"
        )
    elif action == "modify_tp_sl":
        old_tp = kwargs.get("old_tp", 0.0)
        new_tp = kwargs.get("new_tp", 0.0)
        old_sl = kwargs.get("old_sl", 0.0)
        new_sl = kwargs.get("new_sl", 0.0)
        message = (
            "🔔 *TP/SL Modified (MT5)*\n"
            f"Symbol: {symbol}\n"
            f"Position Ticket: {position_ticket if position_ticket else 'N/A'}\n"
            f"Old TP: {old_tp:.5f}\n"
            f"New TP: {new_tp:.5f}\n"
            f"Old SL: {old_sl:.5f}\n"
            f"New SL: {new_sl:.5f}\n"
            f"Time: {time_str}"
        )
    else:
        message = f"Unknown action: {action}"
        logger.warning(message)
    return message