import threading
import time
import logging
import MetaTrader5 as mt5
from telegram_utils import send_telegram_message, format_trade_signal

logger = logging.getLogger(__name__)

# Lưu danh sách deal tickets đã xử lý
processed_deals = set()

# Lưu trạng thái vị thế để theo dõi TP/SL
position_states = {}  # {position_id: {'tp': float, 'sl': float}}

# Lưu danh sách position_id đã biết
known_positions = set()

# Biến toàn cục để kiểm soát worker
_worker_thread = None
_stop_event = threading.Event()

def trade_signal_worker():
    """Worker thread để ghi nhận giao dịch và gửi tín hiệu Telegram."""
    logger.info("Starting trade signal worker...")

    while not _stop_event.is_set():
        try:
            # Kiểm tra trạng thái MT5
            if not mt5.initialize():
                logger.error(f"MT5 initialization failed. Last error: {mt5.last_error()}")
                time.sleep(5)
                continue

            # Kiểm tra thông tin tài khoản
            account_info = mt5.account_info()
            if not account_info:
                logger.error(f"Failed to get account info. Last error: {mt5.last_error()}")
                time.sleep(5)
                continue
            logger.debug(f"Account info: {account_info}")

            # Lấy danh sách vị thế hiện tại
            positions = mt5.positions_get()
            if positions is None:
                logger.error(f"Failed to retrieve positions. Last error: {mt5.last_error()}")
                time.sleep(5)
                continue
            logger.debug(f"Retrieved {len(positions)} positions")

            current_positions = set()
            for position in positions:
                position_id = position.ticket
                current_positions.add(position_id)
                known_positions.add(position_id)  # Lưu position_id
                current_tp = position.tp
                current_sl = position.sl

                # Kiểm tra deals cho vị thế đang mở
                deals = mt5.history_deals_get(position=position_id)
                if deals is None:
                    logger.error(f"Failed to retrieve deals for position {position_id}. Last error: {mt5.last_error()}")
                    continue
                logger.debug(f"Retrieved {len(deals)} deals for position {position_id}")

                for deal in deals:
                    deal_dict = deal._asdict()
                    deal_ticket = deal_dict["ticket"]

                    # Bỏ qua deal đã xử lý
                    if deal_ticket in processed_deals:
                        continue

                    # Xử lý deal mở hoặc đóng
                    if deal_dict["entry"] in [mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT]:
                        action = "open" if deal_dict["entry"] == mt5.DEAL_ENTRY_IN else "close"
                        message = format_trade_signal(deal_dict, position_id, action=action)
                        sent = send_telegram_message(message)
                        if sent:
                            logger.info(f"Sent Telegram signal for deal {deal_ticket} ({action}).")
                        else:
                            logger.warning(f"Failed to send Telegram signal for deal {deal_ticket}.")

                        # Đánh dấu deal đã xử lý
                        processed_deals.add(deal_ticket)

                # Kiểm tra thay đổi TP/SL
                if position_id in position_states:
                    prev_tp = position_states[position_id]["tp"]
                    prev_sl = position_states[position_id]["sl"]
                    if current_tp != prev_tp or current_sl != prev_sl:
                        logger.info(f"Detected TP/SL change for position {position_id}")
                        message = format_trade_signal(
                            position._asdict(), position_id, action="modify_tp_sl",
                            old_tp=prev_tp, old_sl=prev_sl, new_tp=current_tp, new_sl=current_sl
                        )
                        sent = send_telegram_message(message)
                        if sent:
                            logger.info(f"Sent Telegram signal for TP/SL change on position {position_id}.")
                        else:
                            logger.warning(f"Failed to send Telegram signal for TP/SL change on position {position_id}.")

                # Cập nhật trạng thái vị thế
                position_states[position_id] = {"tp": current_tp, "sl": current_sl}

            # Kiểm tra deals cho tất cả position_id đã biết (bao gồm vị thế đã đóng)
            positions_to_remove = set()
            for position_id in known_positions:
                deals = mt5.history_deals_get(position=position_id)
                if deals is None:
                    logger.error(f"Failed to retrieve deals for position {position_id}. Last error: {mt5.last_error()}")
                    continue
                logger.debug(f"Retrieved {len(deals)} deals for position {position_id}")

                for deal in deals:
                    deal_dict = deal._asdict()
                    deal_ticket = deal_dict["ticket"]
                    if deal_ticket in processed_deals:
                        continue
                    if deal_dict["entry"] == mt5.DEAL_ENTRY_OUT:
                        message = format_trade_signal(deal_dict, position_id, action="close")
                        sent = send_telegram_message(message)
                        if sent:
                            logger.info(f"Sent Telegram signal for deal {deal_ticket} (close) on position {position_id}.")
                        else:
                            logger.warning(f"Failed to send Telegram signal for deal {deal_ticket} on position {position_id}.")
                        processed_deals.add(deal_ticket)
                        # Đánh dấu vị thế để xóa sau khi xử lý deal đóng
                        if position_id not in current_positions:
                            positions_to_remove.add(position_id)

            # Xóa trạng thái và position_id của các vị thế đã đóng
            for position_id in positions_to_remove:
                logger.debug(f"Removing closed position {position_id} from tracking")
                if position_id in position_states:
                    del position_states[position_id]
                known_positions.discard(position_id)

            # Chờ lâu hơn để đảm bảo deals được ghi
            time.sleep(10)

        except Exception as e:
            logger.error(f"Error in trade signal worker: {str(e)}")
            time.sleep(5)

    logger.info("Trade signal worker stopped.")

def start_worker():
    """Khởi động trade signal worker."""
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _stop_event.clear()
        _worker_thread = threading.Thread(target=trade_signal_worker, daemon=True)
        _worker_thread.start()
        logger.info("Trade signal worker started.")
    else:
        logger.info("Trade signal worker is already running.")

def stop_worker():
    """Dừng trade signal worker."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        _stop_event.set()
        _worker_thread.join()
        logger.info("Trade signal worker stopped.")
    _worker_thread = None