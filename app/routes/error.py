from flask import Blueprint, jsonify
import logging
import MetaTrader5 as mt5
from flasgger import swag_from

error_bp = Blueprint('error', __name__)
logger = logging.getLogger(__name__)

@error_bp.route('/last_error', methods=['GET'])
@swag_from({
    'tags': ['Error'],
    'responses': {
        200: {
            'description': 'Last error retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'error_code': {'type': 'integer'},
                    'error_message': {'type': 'string'}
                }
            }
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def last_error_endpoint():
    """
    Get Last Error Code and Message
    ---
    description: Retrieve the last error code and message from MetaTrader5.
    """
    try:
        error = mt5.last_error()
        return jsonify({"error_code": error[0], "error_message": error[1]})
    except Exception as e:
        logger.error(f"Error in last_error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@error_bp.route('/last_error_str', methods=['GET'])
@swag_from({
    'tags': ['Error'],
    'responses': {
        200: {
            'description': 'Last error message retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'error_message': {'type': 'string'}
                }
            }
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def last_error_str_endpoint():
    """
    Get Last Error Message as String
    ---
    description: Retrieve the last error message string from MetaTrader5.
    """
    try:
        error_code, error_str = mt5.last_error()
        return jsonify({"error_message": error_str})
    except Exception as e:
        logger.error(f"Error in last_error_str: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500