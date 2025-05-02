from flask import Blueprint, jsonify, request
import MetaTrader5 as mt5
import logging
from datetime import datetime
from flasgger import swag_from
from lib import get_deal_from_ticket, get_order_from_ticket

history_bp = Blueprint('history', __name__)
logger = logging.getLogger(__name__)

@history_bp.route('/get_deal_from_ticket', methods=['GET'])
@swag_from({
    'tags': ['History'],
    'parameters': [
        {
            'name': 'ticket',
            'in': 'query',
            'type': 'integer',
            'required': True,
            'description': 'Ticket number to retrieve deal information.'
        }
    ],
    'responses': {
        200: {
            'description': 'Deal information retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'ticket': {'type': 'integer'},
                    'symbol': {'type': 'string'},
                    'type': {'type': 'string'},
                    'volume': {'type': 'number'},
                    'open_time': {'type': 'string', 'format': 'date-time'},
                    'close_time': {'type': 'string', 'format': 'date-time'},
                    'open_price': {'type': 'number'},
                    'close_price': {'type': 'number'},
                    'profit': {'type': 'number'},
                    'commission': {'type': 'number'},
                    'swap': {'type': 'number'},
                    'comment': {'type': 'string'}
                }
            }
        },
        400: {
            'description': 'Invalid ticket format.'
        },
        404: {
            'description': 'Failed to get deal information.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def get_deal_from_ticket_endpoint():
    """
    Get Deal Information from Ticket
    ---
    description: Retrieve deal information associated with a specific ticket number.
    """
    try:
        ticket = request.args.get('ticket')
        if not ticket:
            return jsonify({"error": "Ticket parameter is required"}), 400
        
        ticket = int(ticket)
        deal = get_deal_from_ticket(ticket)
        if deal is None:
            return jsonify({"error": "Failed to get deal information"}), 404
        
        return jsonify(deal)
    
    except ValueError:
        return jsonify({"error": "Invalid ticket format"}), 400
    except Exception as e:
        logger.error(f"Error in get_deal_from_ticket: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@history_bp.route('/get_order_from_ticket', methods=['GET'])
@swag_from({
    'tags': ['History'],
    'parameters': [
        {
            'name': 'ticket',
            'in': 'query',
            'type': 'integer',
            'required': True,
            'description': 'Ticket number to retrieve order information.'
        }
    ],
    'responses': {
        200: {
            'description': 'Order information retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'order': {'type': 'object'}
                    # Define properties based on order structure
                }
            }
        },
        400: {
            'description': 'Invalid ticket format.'
        },
        404: {
            'description': 'Failed to get order information.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def get_order_from_ticket_endpoint():
    """
    Get Order Information from Ticket
    ---
    description: Retrieve order information associated with a specific ticket number.
    """
    try:
        ticket = request.args.get('ticket')
        if not ticket:
            return jsonify({"error": "Ticket parameter is required"}), 400
        
        ticket = int(ticket)
        order = get_order_from_ticket(ticket)
        if order is None:
            return jsonify({"error": "Failed to get order information"}), 404
        
        return jsonify(order)
    
    except ValueError:
        return jsonify({"error": "Invalid ticket format"}), 400
    except Exception as e:
        logger.error(f"Error in get_order_from_ticket: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@history_bp.route('/history_deals_get', methods=['GET'])
@swag_from({
    'tags': ['History'],
    'parameters': [
        {
            'name': 'from_date',
            'in': 'query',
            'type': 'string',
            'required': True,
            'format': 'date-time',
            'description': 'Start date in ISO format.'
        },
        {
            'name': 'to_date',
            'in': 'query',
            'type': 'string',
            'required': True,
            'format': 'date-time',
            'description': 'End date in ISO format.'
        },
        {
            'name': 'position',
            'in': 'query',
            'type': 'integer',
            'required': True,
            'description': 'Position number to filter deals.'
        }
    ],
    'responses': {
        200: {
            'description': 'Deals history retrieved successfully.',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object'
                    # Define properties based on deal structure
                }
            }
        },
        400: {
            'description': 'Invalid parameter format or missing parameters.'
        },
        404: {
            'description': 'Failed to get deals history.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def history_deals_get_endpoint():
    """
    Get Deals History
    ---
    description: Retrieve historical deals within a specified date range for a particular position.
    """
    try:
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        position = request.args.get('position')
        
        if not all([from_date, to_date, position]):
            return jsonify({"error": "from_date, to_date, and position parameters are required"}), 400
        
        from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        position = int(position)

        from_timestamp = int(from_date.timestamp())
        to_timestamp = int(to_date.timestamp())
        deals = mt5.history_deals_get(from_timestamp, to_timestamp, position=position)
        
        if deals is None:
            return jsonify({"error": "Failed to get deals history"}), 404
        
        deals_list = [deal._asdict() for deal in deals]
        return jsonify(deals_list)
    
    except ValueError:
        return jsonify({"error": "Invalid parameter format"}), 400
    except Exception as e:
        logger.error(f"Error in history_deals_get: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@history_bp.route('/history_orders_get', methods=['GET'])
@swag_from({
    'tags': ['History'],
    'parameters': [
        {
            'name': 'ticket',
            'in': 'query',
            'type': 'integer',
            'required': True,
            'description': 'Ticket number to retrieve orders history.'
        }
    ],
    'responses': {
        200: {
            'description': 'Orders history retrieved successfully.',
            'schema': {
                'type': 'array',
                'items': {
                    'type': 'object'
                    # Define properties based on order structure
                }
            }
        },
        400: {
            'description': 'Invalid ticket format or missing parameter.'
        },
        404: {
            'description': 'Failed to get orders history.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def history_orders_get_endpoint():
    """
    Get Orders History
    ---
    description: Retrieve historical orders associated with a specific ticket number.
    """
    try:
        ticket = request.args.get('ticket')
        if not ticket:
            return jsonify({"error": "Ticket parameter is required"}), 400
        
        ticket = int(ticket)
        orders = mt5.history_orders_get(ticket=ticket)
        if orders is None:
            return jsonify({"error": "Failed to get orders history"}), 404
        
        orders_list = [order._asdict() for order in orders]
        return jsonify(orders_list)
    
    except ValueError:
        return jsonify({"error": "Invalid ticket format"}), 400
    except Exception as e:
        logger.error(f"Error in history_orders_get: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500