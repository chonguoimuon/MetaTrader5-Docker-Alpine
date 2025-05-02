from flask import Blueprint, jsonify, request
import MetaTrader5 as mt5
import logging
from flasgger import swag_from
import time
from datetime import datetime, timedelta
import pytz # Import pytz for timezone handling

# Import the worker function to add trailing stop jobs
from trailing_stop_worker import add_trailing_stop_job_to_worker

order_bp = Blueprint('order', __name__)
logger = logging.getLogger(__name__)

@order_bp.route('/order', methods=['POST'])
@swag_from({
    'tags': ['Order'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'symbol': {'type': 'string', 'description': 'Trading symbol (e.g., "EURUSD").'},
                    'volume': {'type': 'number', 'description': 'Volume of the order (e.g., 0.1).'},
                    'type': {'type': 'string', 'enum': ['BUY', 'SELL'], 'description': 'Order type ("BUY" or "SELL").'},
                    'deviation': {'type': 'integer', 'default': 20, 'description': 'Maximum allowed deviation from the requested price in points (default is 20).'},
                    'magic': {'type': 'integer', 'default': 0, 'description': 'Magic number for the order (default is 0).'},
                    'comment': {'type': 'string', 'default': '', 'description': 'Comment for the order (default is empty string).'},
                    'type_filling': {'type': 'string', 'enum': ['ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', 'ORDER_FILLING_RETURN'], 'description': 'Order filling type (IOC, FOK, or RETURN).'},
                    'sl': {'type': 'number', 'description': 'Optional Stop Loss price.'},
                    'tp': {'type': 'number', 'description': 'Optional Take Profit price.'},
                    'ts': {'type': 'number', 'description': 'Optional Trailing Stop distance in points. If provided, trailing stop is enabled for the new position.'} # Added ts parameter
                },
                'required': ['symbol', 'volume', 'type']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Order executed successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'result': {
                        'type': 'object',
                        'properties': {
                            'retcode': {'type': 'integer'},
                            'order': {'type': 'integer'}, # Order ticket
                            'deal': {'type': 'integer'},   # Deal ticket
                            # 'position': {'type': 'integer'}, # Removed direct position from result schema
                            'magic': {'type': 'integer'},
                            'price': {'type': 'number'},
                            'volume': {'type': 'number'},
                            'symbol': {'type': 'string'},
                            'comment': {'type': 'string'}
                            # Add other relevant fields as needed
                        }
                    },
                    'position_ticket': {'type': 'integer', 'description': 'Ticket of the newly created position, if any.'}, # Added position ticket to top level
                    'trailing_stop_status': {'type': 'string', 'description': 'Status of trailing stop activation (e.g., "activated", "not requested", "failed").'} # Added trailing stop status
                }
            }
        },
        400: {
            'description': 'Bad request or order failed.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def post_order():
    """
    Place a Market Order
    ---
    description: Place a market buy or sell order for a given symbol and volume.
    """
    try:
        data = request.get_json()
        if not data or 'symbol' not in data or 'volume' not in data or 'type' not in data:
            return jsonify({"error": "symbol, volume, and type are required"}), 400

        symbol = str(data['symbol'])
        volume = float(data['volume'])
        order_type_str = data['type'].upper()
        deviation = int(data.get('deviation', 20))
        magic = int(data.get('magic', 0))
        comment = str(data.get('comment', ''))
        type_filling_str = data.get('type_filling', 'ORDER_FILLING_IOC').upper()
        ts_distance = data.get('ts') # Get the optional 'ts' parameter

        # Map order type string to MT5 constant
        order_type_map = {
            'BUY': mt5.ORDER_TYPE_BUY,
            'SELL': mt5.ORDER_TYPE_SELL
        }
        order_type = order_type_map.get(order_type_str)
        if order_type is None:
            return jsonify({"error": f"Invalid order type: {order_type_str}. Must be 'BUY' or 'SELL'."}), 400

        # Map filling type string to MT5 constant
        type_filling_map = {
            'ORDER_FILLING_IOC': mt5.ORDER_FILLING_IOC,
            'ORDER_FILLING_FOK': mt5.ORDER_FILLING_FOK,
            'ORDER_FILLING_RETURN': mt5.ORDER_FILLING_RETURN
        }
        type_filling = type_filling_map.get(type_filling_str)
        if type_filling is None:
             return jsonify({"error": f"Invalid filling type: {type_filling_str}. Must be 'ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', or 'ORDER_FILLING_RETURN'."}), 400


        # Get current price for market order
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Failed to get tick for symbol: {symbol}")
            return jsonify({"error": f"Failed to get tick for symbol: {symbol}"}), 400

        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        if price == 0.0:
             logger.error(f"Invalid price retrieved for symbol: {symbol}")
             return jsonify({"error": f"Invalid price retrieved for symbol: {symbol}"}), 400


        request_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }

        # Add optional SL/TP if provided in the request body
        if 'sl' in data and data['sl'] is not None:
            request_data["sl"] = float(data['sl'])
        if 'tp' in data and data['tp'] is not None:
            request_data["tp"] = float(data['tp'])

        logger.info(f"Sending order request: {request_data}")

        # Send order
        result = mt5.order_send(request_data)

        logger.debug(f"Order result: {result}")

        # Check if result is None before accessing retcode
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code, error_str = mt5.last_error()
            # Include MT5 error in the response if result is None
            error_message = result.comment if result else "MT5 order_send returned None"
            logger.error(f"Order failed: {error_message}. MT5 Error: {error_str}") # Log the failure

            # Check if result is not None before trying to access _asdict()
            return jsonify({
                "error": f"Order failed: {error_message}",
                "mt5_error": error_str,
                "result": result._asdict() if result else None
            }), 400

        logger.info(f"Order executed successfully. Result: {result._asdict()}")

        # --- Trailing Stop Activation Logic ---
        trailing_stop_status = "not requested"
        position_ticket = None # Initialize position_ticket

        if ts_distance is not None:
            # Order was successful, now try to find the resulting position
            # The deal ticket is available in result.deal
            deal_ticket = result.deal
            if deal_ticket != 0: # Check if a deal was created
                logger.info(f"Order resulted in deal ticket: {deal_ticket}. Attempting to find associated position.")
                # Retrieve the deal to get the position ID
                # Search for deals in a small time window around the current time
                utc_now = datetime.now(pytz.UTC) # Use pytz.UTC for timezone
                from_date = utc_now - timedelta(seconds=5) # Look back a few seconds
                to_date = utc_now + timedelta(seconds=1) # Look forward a little

                # Fetch deals by ticket to be more precise
                # Using history_deals_get with ticket is the most reliable way to get a specific deal
                deals = mt5.history_deals_get(ticket=deal_ticket)


                found_position_ticket = None
                if deals:
                    for deal in deals:
                        # Find the deal matching the ticket and associated with a position
                        # Also ensure the deal is related to the order that was just sent (check order)
                        # Note: result.order contains the order ticket
                        if deal.ticket == deal_ticket and deal.position_id != 0 and deal.order == result.order: # Corrected from deal.order_id
                            found_position_ticket = deal.position_id
                            logger.info(f"Found position ticket {found_position_ticket} for deal {deal_ticket} and order {result.order}.")
                            break # Found the position, no need to check other deals

                if found_position_ticket:
                    position_ticket = found_position_ticket # Set the position_ticket for the response
                    # Now get the position details to get the open price
                    positions = mt5.positions_get(ticket=position_ticket)
                    if positions and len(positions) > 0:
                        new_position = positions[0]
                        # Use the open price of the new position as the initial_sl_price for the worker
                        #initial_sl_for_ts = new_position.price_open
                        #logger.info(f"Found new position {position_ticket} with open price {initial_sl_for_ts}. Attempting to add trailing stop job to worker with distance {ts_distance}.")
                        # Add the trailing stop job to the worker
                        added_to_worker = add_trailing_stop_job_to_worker(position_ticket, float(ts_distance)) #, initial_sl_price=initial_sl_for_ts)

                        if added_to_worker:
                            trailing_stop_status = "activated"
                            logger.info(f"Trailing stop job added to worker for position {position_ticket}.")
                        else:
                            trailing_stop_status = "failed to activate (worker add failed)"
                            logger.error(f"Failed to add trailing stop job to worker for position {position_ticket}.")
                    else:
                        trailing_stop_status = "failed to activate (position details not found)"
                        logger.error(f"Deal {deal_ticket} associated with position {position_ticket}, but position details could not be retrieved.")
                else:
                    trailing_stop_status = "failed to activate (position not linked to deal or order mismatch)"
                    logger.error(f"Deal {deal_ticket} found, but no associated position_id or order mismatch with {result.order}.")
            else:
                trailing_stop_status = "not activated (no deal created)"
                logger.warning(f"Order executed successfully but did not result in a deal (ticket {result.order}). Trailing stop not activated.")
        # --- End Trailing Stop Activation Logic ---


        response_data = {
            "message": "Order executed successfully",
            "result": result._asdict(),
            "trailing_stop_status": trailing_stop_status # Include the trailing stop status in the response
        }
        if position_ticket is not None:
             response_data["position_ticket"] = position_ticket # Add position ticket to response if found

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in post_order: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


