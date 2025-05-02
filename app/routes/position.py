from flask import Blueprint, jsonify, request
import MetaTrader5 as mt5
import logging
from lib import close_position, close_all_positions, get_positions, apply_trailing_stop
from flasgger import swag_from
import pandas as pd # Import pandas for dataframe handling

# Import worker functions instead of scheduler_jobs
from trailing_stop_worker import add_trailing_stop_job_to_worker, remove_trailing_stop_job_from_worker, get_active_worker_jobs_list, active_trailing_stop_jobs # Import necessary components

# Removed module-level import of scheduler


position_bp = Blueprint('position', __name__)
logger = logging.getLogger(__name__)

# --- Endpoints ---

@position_bp.route('/close_position', methods=['POST'])
@swag_from({
    'tags': ['Position'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'ticket': {'type': 'integer', 'description': 'Ticket number of the position to close.'},
                    'type_filling': {'type': 'string', 'enum': ['ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', 'ORDER_FILLING_RETURN'], 'description': 'Order filling type (IOC, FOK, or RETURN).'}
                },
                'required': ['ticket']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Position closed successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'result': {
                        'type': 'object',
                        'properties': {
                            'retcode': {'type': 'integer'},
                            'order': {'type': 'integer'},
                            'magic': {'type': 'integer'},
                            'price': {'type': 'number'},
                            'symbol': {'type': 'string'},
                            # Add other relevant fields as needed
                        }
                    }
                }
            }
        },
        400: {
            'description': 'Bad request or failed to close position.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def close_position_endpoint():
    """
    Close a Specific Position
    ---
    description: Close a specific trading position based on the provided position data.
    """
    try:
        # Removed scheduler import

        # data = request.get_json()     
        
        # if not data or 'position' not in data:
            # return jsonify({"error": "Position data is required"}), 400

        # position_ticket = data['position'].get('ticket') # Get ticket to potentially remove job

        data = request.get_json()
        if not data or 'ticket' not in data:
            return jsonify({"error": "ticket is required"}), 400

        position_ticket = data.get('ticket')

        # Fetch the position details using the ticket
        positions = mt5.positions_get(ticket=position_ticket)

        if positions is None or len(positions) == 0:
            logger.error(f"Position with ticket {position_ticket} not found.")
            return jsonify({"error": f"Position with ticket {position_ticket} not found."}), 404

        # We found the position, now close it using the lib function
        position_to_close = positions[0]._asdict() # Convert Position object to dictionary
        
        
        type_filling_str = data.get('type_filling', 'ORDER_FILLING_IOC').upper()
        # Map filling type string to MT5 constant
        type_filling_map = {
            'ORDER_FILLING_IOC': mt5.ORDER_FILLING_IOC,
            'ORDER_FILLING_FOK': mt5.ORDER_FILLING_FOK,
            'ORDER_FILLING_RETURN': mt5.ORDER_FILLING_RETURN
        }
        type_filling = type_filling_map.get(type_filling_str)
        if type_filling is None:
             return jsonify({"error": f"Invalid filling type: {type_filling_str}. Must be 'ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', or 'ORDER_FILLING_RETURN'."}), 400

        
        # result = close_position(data['position'],type_filling=type_filling)
        result = close_position(position_to_close, type_filling=type_filling)

        if result is None:
            return jsonify({"error": "Failed to close position"}), 400

        # If position closed successfully, remove any active trailing stop job for it from worker tracking
        if position_ticket: # Ensure ticket is not None
             remove_trailing_stop_job_from_worker(position_ticket) # Use the function from worker


        return jsonify({"message": "Position closed successfully", "result": result._asdict()})

    except Exception as e:
        logger.error(f"Error in close_position: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@position_bp.route('/close_all_positions', methods=['POST'])
@swag_from({
    'tags': ['Position'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': False,
            'schema': {
                'type': 'object',
                'properties': {
                    'order_type': {'type': 'string', 'enum': ['BUY', 'SELL', 'all'], 'default': 'all'},
                    'symbol': {'type': 'string'},
                    'comment': {'type': 'string'},
                    'type_filling': {'type': 'string', 'enum': ['ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', 'ORDER_FILLING_RETURN'], 'description': 'Order filling type (IOC, FOK, or RETURN).'},
                    'magic': {'type': 'integer'}
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Closed positions successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'results': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'retcode': {'type': 'integer'},
                                'order': {'type': 'integer'},
                                'magic': {'type': 'integer'},
                                'price': {'type': 'number'},
                                'symbol': {'type': 'string'},
                                # Add other relevant fields as needed
                            }
                        }
                    }
                }
            }
        },
        400: {
            'description': 'Bad request or no positions were closed.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def close_all_positions_endpoint():
    """
    Close All Positions
    ---
    description: Close all open trading positions based on optional filters like order type and magic number.
    """
    try:
        # Removed scheduler import

        data = request.get_json() or {}
        order_type = data.get('order_type', 'all')
        magic = data.get('magic')
        comment = data.get('comment', '')
        symbol = data.get('symbol', '')
        type_filling_str = data.get('type_filling', 'ORDER_FILLING_IOC').upper()
        
        # Map filling type string to MT5 constant
        type_filling_map = {
            'ORDER_FILLING_IOC': mt5.ORDER_FILLING_IOC,
            'ORDER_FILLING_FOK': mt5.ORDER_FILLING_FOK,
            'ORDER_FILLING_RETURN': mt5.ORDER_FILLING_RETURN
        }
        type_filling = type_filling_map.get(type_filling_str)
        if type_filling is None:
             return jsonify({"error": f"Invalid filling type: {type_filling_str}. Must be 'ORDER_FILLING_IOC', 'ORDER_FILLING_FOK', or 'ORDER_FILLING_RETURN'."}), 400
        
        
        # Get positions before closing to know which jobs to remove
        positions_to_close_df = get_positions(symbol, comment, magic)
        positions_to_close_tickets = positions_to_close_df['ticket'].tolist() if not positions_to_close_df.empty else []


        results = close_all_positions(order_type, symbol, comment, magic, type_filling)
        if not results:
            return jsonify({"message": "No positions were closed"}), 200

        # Remove scheduled jobs for positions that were successfully closed from worker tracking
        closed_tickets = [res._asdict().get('position') for res in results if res and res.retcode == mt5.TRADE_RETCODE_DONE]
        for ticket in closed_tickets:
            remove_trailing_stop_job_from_worker(ticket) # Use the function from worker


        return jsonify({
            "message": f"Closed {len(results)} positions",
            "results": [result._asdict() for result in results]
        })

    except Exception as e:
        logger.error(f"Error in close_all_positions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@position_bp.route('/modify_sl_tp', methods=['POST'])
@swag_from({
    'tags': ['Position'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'position': {'type': 'integer'},
                    'symbol': {'type': 'string'}, # Added symbol to Swagger doc
                    'sl': {'type': 'number'},
                    'tp': {'type': 'number'}
                },
                # Made symbol required based on the request, adjust if optional
                'required': ['position', 'symbol']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'SL/TP modified successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'result': {
                        'type': 'object',
                        'properties': {
                            'retcode': {'type': 'integer'},
                            'order': {'type': 'integer'},
                            'magic': {'type': 'integer'},
                            'price': {'type': 'number'},
                            'symbol': {'type': 'string'},
                            # Add other relevant fields as needed
                        }
                    }
                }
            }
        },
        400: {
            'description': 'Bad request or failed to modify SL/TP.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def modify_sl_tp_endpoint():
    """
    Modify Stop Loss and Take Profit
    ---
    description: Modify the Stop Loss (SL) and Take Profit (TP) levels for a specific position.
    """
    try:
        data = request.get_json()
        if not data or 'position' not in data or 'symbol' not in data: # Added symbol check
            return jsonify({"error": "Position and symbol data are required"}), 400

        position_ticket = data['position']
        symbol = data.get('symbol') # Get symbol from request data
        sl = data.get('sl') * 1.0
        tp = data.get('tp') * 1.0

        # Removed the get_positions call here as symbol is now in the request body
        # Get position info to include symbol in the request if needed by MT5 (though usually not for SLTP)
        # positions = mt5.positions_get(ticket=position_ticket)
        # if positions is None or len(positions) == 0:
        #      return jsonify({"error": f"Position with ticket {position_ticket} not found."}), 404
        # position = positions[0]


        request_data = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position_ticket,
            "symbol": symbol, # Use symbol from request data
            "sl": sl,
            "tp": tp
        }

        # Log the values being sent to MT5
        logger.info(f"Attempting to modify SL/TP for position {position_ticket}: Symbol={symbol}, SL={sl}, TP={tp}")


        result = mt5.order_send(request_data)
        # Check if result is None before accessing retcode
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_code, error_str = mt5.last_error()
            # Include MT5 error in the response if result is None
            error_message = result.comment if result else "MT5 order_send returned None"
            logger.error(f"Failed to modify SL/TP for position {position_ticket}: {error_message}. MT5 Error: {error_str}") # Log the failure
            return jsonify({"error": f"Failed to modify SL/TP: {error_message}", "mt5_error": error_str}), 400


        logger.info(f"Successfully modified SL/TP for position {position_ticket}. Result: {result._asdict()}") # Log success
        return jsonify({"message": "SL/TP modified successfully", "result": result._asdict()})

    except Exception as e:
        logger.error(f"Error in modify_sl_tp: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@position_bp.route('/get_positions', methods=['POST'])
@swag_from({
    'tags': ['Position'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': False,
            'schema': {
                'type': 'object',
                'properties': {
                    'symbol': {'type': 'string'},
                    'comment': {'type': 'string'},
                    'magic': {'type': 'integer'}
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Positions retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'positions': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'ticket': {'type': 'integer'},
                                'time': {'type': 'string', 'format': 'date-time'},
                                'type': {'type': 'integer'},
                                'magic': {'type': 'integer'},
                                'symbol': {'type': 'string'},
                                'volume': {'type': 'number'},
                                'price_open': {'type': 'number'},
                                'sl': {'type': 'number'},
                                'tp': {'type': 'number'},
                                'price_current': {'type': 'number'},
                                'swap': {'type': 'number'},
                                'profit': {'type': 'number'},
                                'comment': {'type': 'string'},
                                'external_id': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        },
        400: {
            'description': 'Bad request or failed to retrieve positions.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def get_positions_endpoint():
    """
    Get Open Positions
    ---
    description: Retrieve all open trading positions, optionally filtered by magic number / comment string.
    """
    try:
        data = request.get_json() or {}
        magic = data.get('magic')
        comment = data.get('comment', '')
        symbol = data.get('symbol', '')

        positions_df = get_positions(symbol, comment, magic)

        if positions_df is None:
            return jsonify({"error": "Failed to retrieve positions"}), 500

        if positions_df.empty:
            return jsonify({"positions": []}), 200

        # Original code did not convert timestamp columns to datetime strings
        # for col in ['time', 'time_msc', 'time_update', 'time_update_msc']:
        #      if col in positions_df.columns:
        #          positions_df[col] = pd.to_datetime(positions_df[col], unit='s').dt.isoformat(timespec='seconds') # Corrected method

        return jsonify(positions_df.to_dict(orient='records')), 200

    except Exception as e:
        logger.error(f"Error in get_positions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@position_bp.route('/positions_total', methods=['GET'])
@swag_from({
    'tags': ['Position'],
    'responses': {
        200: {
            'description': 'Total number of open positions retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'total': {'type': 'integer'}
                }
            }
        },
        400: {
            'description': 'Failed to get positions total.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def positions_total_endpoint():
    """
    Get Total Open Positions
    ---
    description: Retrieve the total number of open trading positions.
    """
    try:
        total = mt5.positions_total()
        if total is None:
            return jsonify({"error": "Failed to get positions total"}), 400

        return jsonify({"total": total})

    except Exception as e:
        logger.error(f"Error in positions_total: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@position_bp.route('/apply_trailing_stop', methods=['POST'])
@swag_from({
    'tags': ['Position'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'position_ticket': {'type': 'integer', 'description': 'Ticket number of the position to apply trailing stop.'},
                    'trailing_distance': {'type': 'number', 'description': 'Trailing stop distance in points.'},
                    # Removed interval_seconds from API request as worker uses a fixed interval
                    # 'interval_seconds': {'type': 'integer', 'default': 5, 'description': 'Interval in seconds to check for trailing stop updates (default is 5 seconds).'}
                },
                'required': ['position_ticket', 'trailing_distance']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Trailing stop job scheduled successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    # Removed job_id as worker doesn't use APScheduler job IDs
                    # 'job_id': {'type': 'string'}
                }
            }
        },
        400: {
            'description': 'Bad request or failed to schedule trailing stop job.'
        },
        404: {
             'description': 'Position not found.'
        },
        409: {
             'description': 'Trailing stop job already exists for this position.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def apply_trailing_stop_endpoint():
    """
    Enable Trailing Stop for a Position (using Worker)
    ---
    description: Enables the trailing stop functionality for a specific trading position using the background worker.
    """
    try:
        # Removed scheduler import

        data = request.get_json()
        if not data or 'position_ticket' not in data or 'trailing_distance' not in data:
            return jsonify({"error": "position_ticket and trailing_distance are required"}), 400

        position_ticket = data['position_ticket']
        trailing_distance = data['trailing_distance']
        # Removed interval_seconds from data


        # Use the function from worker to add the job
        added = add_trailing_stop_job_to_worker(position_ticket, trailing_distance)

        if not added:
            # Check if the reason for failure was position not found or job already exists
            positions = mt5.positions_get(ticket=position_ticket)
            if positions is None or len(positions) == 0:
                 return jsonify({"error": f"Position with ticket {position_ticket} not found."}), 404
            elif position_ticket in active_trailing_stop_jobs: # Check worker's dictionary
                 return jsonify({"error": f"Trailing stop job already exists for position {position_ticket}"}), 409
            else:
                # This case should ideally not be reached if add_trailing_stop_job_to_worker returns False
                # only for position not found or already exists.
                return jsonify({"error": "Failed to enable trailing stop."}), 400


        return jsonify({
            "message": "Trailing stop enabled successfully for position. Worker will now monitor."
            # Removed job_id from response
        })

    except Exception as e:
        logger.error(f"Error in apply_trailing_stop_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@position_bp.route('/cancel_trailing_stop/<int:position_ticket>', methods=['DELETE'])
@swag_from({
    'tags': ['Position'],
    'parameters': [
        {
            'name': 'position_ticket',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': 'Ticket number of the position whose trailing stop job should be cancelled.'
        }
    ],
    'responses': {
        200: {
            'description': 'Trailing stop job cancelled successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'}
                }
            }
        }
        ,
        404: {
            'description': 'No active trailing stop job found for this position.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def cancel_trailing_stop_endpoint(position_ticket):
    """
    Disable Trailing Stop for a Position (using Worker)
    ---
    description: Disables the trailing stop functionality for a specific trading position by removing it from the background worker's monitoring list.
    """
    try:
        # Removed scheduler import

        # Use the function from worker to remove the job
        removed = remove_trailing_stop_job_from_worker(position_ticket)

        if not removed:
            return jsonify({"error": f"No active trailing stop job found for position {position_ticket}"}), 404

        return jsonify({"message": f"Trailing stop for position {position_ticket} disabled successfully."})

    except Exception as e:
        logger.error(f"Error in cancel_trailing_stop_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@position_bp.route('/list_trailing_stop_jobs', methods=['GET'])
@swag_from({
    'tags': ['Position'],
    'responses': {
        200: {
            'description': 'List of active trailing stop jobs retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'active_jobs': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'position_ticket': {'type': 'integer'},
                                'trailing_distance': {'type': 'number'},
                                # Removed APScheduler specific fields
                                # 'job_id': {'type': 'string'},
                                # 'next_run_time': {'type': 'string', 'format': 'date-time'},
                                # 'interval_seconds': {'type': 'integer'}
                            }
                        }
                    }
                }
            }
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def list_trailing_stop_jobs_endpoint():
    """
    List Active Trailing Stop Jobs (from Worker)
    ---
    description: Retrieves a list of all active trailing stop jobs currently monitored by the background worker.
    """
    try:
        # Removed scheduler import

        # Use the function from worker to get the list of jobs
        jobs_list = get_active_worker_jobs_list()

        return jsonify({"active_jobs": jobs_list})

    except Exception as e:
        logger.error(f"Error in list_trailing_stop_jobs_endpoint: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


