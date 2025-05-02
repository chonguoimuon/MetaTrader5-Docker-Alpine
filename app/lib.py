import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from constants import MT5Timeframe # Assuming constants.py exists and has MT5Timeframe enum

logger = logging.getLogger(__name__)

def get_timeframe(timeframe_str: str) -> MT5Timeframe:
    try:
        return MT5Timeframe[timeframe_str.upper()].value
    except KeyError:
        valid_timeframes = ', '.join([t.name for t in MT5Timeframe])
        raise ValueError(
            f"Invalid timeframe: '{timeframe_str}'. Valid options are: {valid_timeframes}."
        )


def close_position(position, deviation=20, magic=0, comment='', type_filling=mt5.ORDER_FILLING_IOC):
    if 'type' not in position or 'ticket' not in position:
        logger.error("Position dictionary missing 'type' or 'ticket' keys.")
        return None

    order_type_dict = {
        1: mt5.ORDER_TYPE_BUY,
        0: mt5.ORDER_TYPE_SELL
    }

    position_type = position['type']
    if position_type not in order_type_dict:
        logger.error(f"Unknown position type: {position_type}")
        return None

    tick = mt5.symbol_info_tick(position['symbol'])
    if tick is None:
        logger.error(f"Failed to get tick for symbol: {position['symbol']}")
        return None

    price_dict = {
        1: tick.ask,  # Buy order uses Ask price
        0: tick.bid   # Sell order uses Bid price
    }

    price = price_dict[position_type]
    if price == 0.0:
        logger.error(f"Invalid price retrieved for symbol: {position['symbol']}")
        return None

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position['ticket'],  # select the position you want to close
        "symbol": position['symbol'],
        "volume": position['volume'],  # FLOAT
        "type": order_type_dict[position_type],
        "price": price,
        "deviation": deviation,  # INTEGER
        "magic": magic,          # INTEGER
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }

    order_result = mt5.order_send(request)

    if order_result is None or order_result.retcode != mt5.TRADE_RETCODE_DONE: # Added None check
        error_code, error_str = mt5.last_error()
        error_message = order_result.comment if order_result else "MT5 order_send returned None" # Added None check
        logger.error(f"Failed to close position {position['ticket']}: {error_message}. MT5 Error: {error_str}")
        return None

    logger.info(f"Position {position['ticket']} closed successfully.")
    return order_result


def close_all_positions(order_type='all', symbol='', comment='', magic=None, type_filling=mt5.ORDER_FILLING_IOC):
    order_type_dict = {
        'BUY': mt5.ORDER_TYPE_BUY,
        'SELL': mt5.ORDER_TYPE_SELL
    }

    if mt5.positions_total() > 0:
        positions = mt5.positions_get()
        if positions is None:
            logger.error("Failed to retrieve positions.")
            return []

        positions_data = [pos._asdict() for pos in positions]
        positions_df = pd.DataFrame(positions_data)

        # Filtering by symbol if specified
        if symbol !='':
            positions_df = positions_df[positions_df['symbol'] == symbol]

        # Filtering by comment if specified
        if comment !='':
            positions_df = positions_df[positions_df['comment'] == comment]

        # Filtering by magic if specified
        if magic is not None:
            positions_df = positions_df[positions_df['magic'] == magic]

        # Filtering by order_type if not 'all'
        if order_type != 'all':
            if order_type not in order_type_dict:
                logger.error(f"Invalid order_type: {order_type}. Must be 'BUY', 'SELL', or 'all'.")
                return []
            # Note: position['type'] is an integer (0 for SELL, 1 for BUY)
            positions_df = positions_df[positions_df['type'] == order_type_dict[order_type]]

        if positions_df.empty:
            logger.error('No open positions matching the criteria.')
            return []

        results = []
        for _, position in positions_df.iterrows():
            order_result = close_position(position, type_filling=type_filling)
            if order_result:
                results.append(order_result)
            else:
                logger.error(f"Failed to close position {position['ticket']}.")

        return results
    else:
        logger.error("No open positions to close.")
        return []

def get_positions(symbol='', comment='', magic=None):
    # First check if MT5 is initialized
    if not mt5.initialize():
        logger.error("Failed to initialize MT5.")
        return pd.DataFrame()

    total_positions = mt5.positions_total()
    if total_positions is None:
        logger.error("Failed to get positions total.")
        return pd.DataFrame()

    if total_positions > 0:
        positions = mt5.positions_get()
        if positions is None:
            logger.error("Failed to retrieve positions.")
            return pd.DataFrame()

        positions_data = [pos._asdict() for pos in positions]
        positions_df = pd.DataFrame(positions_data)

        # Filtering by symbol if specified
        if symbol !='':
            positions_df = positions_df[positions_df['symbol'] == symbol]

        # Filtering by comment if specified
        if comment !='':
            positions_df = positions_df[positions_df['comment'] == comment]

        if magic is not None:
            positions_df = positions_df[positions_df['magic'] == magic]

        return positions_df
    else:
        return pd.DataFrame(columns=['ticket', 'time', 'time_msc', 'time_update', 'time_update_msc', 'type',
                                   'magic', 'identifier', 'reason', 'volume', 'price_open', 'sl', 'tp',
                                   'price_current', 'swap', 'profit', 'symbol', 'comment', 'external_id'])


def get_deal_from_ticket(ticket, from_date=None, to_date=None):
    if not isinstance(ticket, int):
        logger.error("Ticket must be an integer.")
        return None

    # Define default date range if not provided
    # Note: MT5 history deals/orders are typically recent.
    # Adjusting default range to be wider for potential trailing stop history checks if needed,
    # but for a single deal lookup, a shorter range around current time might be sufficient.
    # Let's keep the original logic for now, assuming recent deal.
    if from_date is None or to_date is None:
        # Using UTC timezone for consistency with MetaTrader5
        utc_now = datetime.now(mt5.TIMEZONE)
        to_date = utc_now
        # Assuming the deal happened recently relative to the position close
        from_date = utc_now - timedelta(hours=1) # Adjusted to 1 hour, can be changed

    # Convert datetime to MT5 time (integer)
    from_timestamp = int(from_date.timestamp())
    to_timestamp = int(to_date.timestamp())

    # Retrieve deals using the specified date range and position
    # Note: history_deals_get can take 'position' argument to filter by position ticket
    deals = mt5.history_deals_get(from_timestamp, to_timestamp, position=ticket)
    if deals is None or len(deals) == 0:
        logger.error(f"No deal history found for position ticket {ticket} between {from_date} and {to_date}.")
        return None

    # Convert deals to a DataFrame for easier processing
    deals_df = pd.DataFrame([deal._asdict() for deal in deals])

    # Filter deals to only include those related to the specified position ticket
    deals_df = deals_df[deals_df['position_id'] == ticket]

    if deals_df.empty:
         logger.error(f"No deals found for position ticket {ticket} within the specified date range.")
         return None

    # Optional: Verify that all deals belong to the same symbol
    if not all(deal == deals_df['symbol'].iloc[0] for deal in deals_df['symbol']):
        logger.warning(f"Inconsistent symbols found in deals for position ticket {ticket}.")
        # Decide how to handle: proceed with the most common symbol, or return error.
        # For simplicity, we'll proceed but log a warning.

    # Extract relevant information - Assuming the first deal is the open and the last is the close for a simple case.
    # This might need refinement for partial closes or complex scenarios.
    first_deal = deals_df.iloc[0]
    last_deal = deals_df.iloc[-1]

    deal_details = {
        'ticket': ticket,
        'symbol': first_deal['symbol'],
        'type': 'BUY' if first_deal['type'] == mt5.DEAL_TYPE_BUY else 'SELL', # Using MT5 constants
        'volume': deals_df['volume'].sum(), # Sum of volumes for all deals related to the position
        'open_time': datetime.fromtimestamp(first_deal['time'], tz=mt5.TIMEZONE),
        'close_time': datetime.fromtimestamp(last_deal['time'], tz=mt5.TIMEZONE),
        'open_price': first_deal['price'],
        'close_price': last_deal['price'],
        'profit': deals_df['profit'].sum(), # Sum of profits from all deals
        'commission': deals_df['commission'].sum(), # Sum of commissions
        'swap': deals_df['swap'].sum(), # Sum of swaps
        'comment': last_deal['comment']  # Use the last comment
    }
    return deal_details


def get_order_from_ticket(ticket):
    if not isinstance(ticket, int):
        logger.error("Ticket must be an integer.")
        return None

    # Get the order history
    # Note: history_orders_get can take 'ticket' argument directly
    orders = mt5.history_orders_get(ticket=ticket)
    if orders is None or len(orders) == 0:
        logger.error(f"No order history found for ticket {ticket}")
        return None

    # Convert order to a dictionary (assuming only one order per ticket in history context)
    order_dict = orders[0]._asdict()

    return order_dict

def apply_trailing_stop(position_ticket: int, trailing_distance: float):
    """
    Applies a trailing stop to a given position.

    Args:
        position_ticket: The ticket number of the position.
        trailing_distance: The trailing stop distance in points.

    Returns:
        A dictionary containing the result of the modification request,
        or None if the position is not found or modification fails.
        Returns {"message": "No SL update needed"} if SL doesn't need to be moved.
    """
    logger.info(f"Attempting to apply trailing stop for position: {position_ticket} with trailing distance: {trailing_distance} points.")

    # Get the position
    positions = mt5.positions_get(ticket=position_ticket)
    if positions is None or len(positions) == 0:
        logger.error(f"Position with ticket {position_ticket} not found.")
        return None

    position = positions[0] # Assuming only one position per ticket
    logger.info(f"  Position found: Symbol={position.symbol}, Type={position.type}, Current SL={position.sl}, Open Price={position.price_open}")

    # Get current tick price
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        logger.error(f"Failed to get tick for symbol: {position.symbol}")
        return None

    current_price = tick.ask if position.type == mt5.ORDER_TYPE_BUY else tick.bid
    logger.info(f"  Current Price ({'Ask' if position.type == mt5.ORDER_TYPE_BUY else 'Bid'}): {current_price}")


    # Get symbol info to calculate points and Digits
    symbol_info = mt5.symbol_info(position.symbol)
    if symbol_info is None:
        logger.error(f"Failed to get symbol info for: {position.symbol}")
        return None

    logger.info(f"  Symbol Info: Point={symbol_info.point}, Digits={symbol_info.digits}")

    # Calculate trailing distance in price points
    trailing_distance_price = trailing_distance * symbol_info.point
    logger.info(f"  Trailing Distance (price): {trailing_distance_price}")


    # Calculate potential new stop loss
    new_sl = position.sl # Start with current SL
    calculated_sl = None # To store the initially calculated SL

    if position.type == mt5.ORDER_TYPE_BUY:
        # For a BUY position, SL trails below the current price
        calculated_sl = current_price - trailing_distance_price
        logger.info(f"  Calculated initial SL (BUY): {calculated_sl}")

        # The new SL should be the maximum of the current SL and the calculated SL
        # This ensures SL only moves up
        new_sl = max(position.sl, calculated_sl)

        # For a BUY, SL must be BELOW the current price.
        if new_sl >= current_price:
             logger.warning(f"  Calculated new SL ({new_sl:.{symbol_info.digits}f}) for BUY position {position_ticket} is at or above current price ({current_price:.{symbol_info.digits}f}). Skipping update.")
             return {"message": "No SL update needed - new SL is above current price"}


        # Check if the new SL is actually better (higher) than the current SL
        # Use a small tolerance for floating point comparison
        tolerance = symbol_info.point * 0.1 # Define a small tolerance (e.g., 1/10th of a point)
        if position.sl != 0.0 and new_sl <= position.sl + tolerance:
             logger.info(f"  Trailing stop for BUY position {position_ticket}: New SL {new_sl:.{symbol_info.digits}f} is not significantly better than current SL {position.sl:.{symbol_info.digits}f}.")
             return {"message": "No SL update needed"} # No update needed

    elif position.type == mt5.ORDER_TYPE_SELL:
        # For a SELL position, SL trails above the current price
        calculated_sl = current_price + trailing_distance_price
        logger.info(f"  Calculated initial SL (SELL): {calculated_sl}")

        # The new SL should be the minimum of the current SL (if set and better) and the calculated SL
        # This ensures SL only moves down
        if position.sl == 0.0:
            new_sl = calculated_sl
        else:
            new_sl = min(position.sl, calculated_sl)


        # For a SELL, SL must be ABOVE the current price.
        if new_sl <= current_price:
             logger.warning(f"  Calculated new SL ({new_sl:.{symbol_info.digits}f}) for SELL position {position_ticket} is at or below current price ({current_price:.{symbol_info.digits}f}). Skipping update.")
             return {"message": "No SL update needed - new SL is below current price"}


        # Check if the new SL is actually better (lower) than the current SL
        # Use a small tolerance for floating point comparison
        tolerance = symbol_info.point * 0.1 # Define a small tolerance (e.g., 1/10th of a point)
        if position.sl != 0.0 and new_sl >= position.sl - tolerance:
             logger.info(f"  Trailing stop for SELL position {position_ticket}: New SL {new_sl:.{symbol_info.digits}f} is not significantly better than current SL {position.sl:.{symbol_info.digits}f}.")
             return {"message": "No SL update needed"} # No update needed


    else:
        logger.error(f"Unknown position type for trailing stop: {position.type}")
        return None # Unknown type

    # Format new_sl to the correct number of digits for the symbol
    formatted_new_sl = round(new_sl, symbol_info.digits)
    logger.info(f"  Formatted New SL (rounded to {symbol_info.digits} digits): {formatted_new_sl}")


    # Prepare the modification request
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position_ticket,
        "symbol": position.symbol,
        "sl": formatted_new_sl, # Use the formatted SL
        "tp": position.tp # Keep the existing TP
    }

    # Send the modification order
    logger.info(f"  Sending MT5 modification request: {request}")
    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        error_code, error_str = mt5.last_error()
        error_message = result.comment if result else "MT5 order_send returned None"
        logger.error(f"Failed to modify SL for position {position_ticket}: {error_message}. MT5 Error: {error_str}")
        return None # Modification failed

    logger.info(f"Successfully applied trailing stop for position {position_ticket}. New SL: {formatted_new_sl}. MT5 Result: {result._asdict()}")
    return result._asdict() # Modification successful

