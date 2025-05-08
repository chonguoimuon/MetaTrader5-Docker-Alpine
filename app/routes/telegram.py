from flask import Blueprint, jsonify, request
from flasgger import swag_from
import logging
from telegram_utils import set_telegram_config, get_telegram_config, send_telegram_message

telegram_bp = Blueprint('telegram', __name__)
logger = logging.getLogger(__name__)

@telegram_bp.route('/telegram/config', methods=['POST'])
@swag_from({
    'tags': ['Telegram'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'bot_token': {'type': 'string', 'description': 'Telegram bot token.'},
                    'chat_id': {'type': 'string', 'description': 'Telegram chat ID.'}
                },
                'required': ['bot_token', 'chat_id']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Telegram configuration updated successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'config': {
                        'type': 'object',
                        'properties': {
                            'bot_token': {'type': 'string'},
                            'chat_id': {'type': 'string'},
                            'enabled': {'type': 'boolean'}
                        }
                    }
                }
            }
        },
        400: {
            'description': 'Invalid request parameters.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def set_telegram_config_endpoint():
    """Set or update Telegram bot token and chat ID."""
    try:
        # Kiểm tra và parse JSON
        data = request.get_json(silent=True)
        if not data:
            logger.error("Invalid JSON in request body")
            return jsonify({"error": "Invalid JSON in request body"}), 400
        if 'bot_token' not in data or 'chat_id' not in data:
            logger.error("Missing bot_token or chat_id in request")
            return jsonify({"error": "bot_token and chat_id are required"}), 400

        bot_token = data["bot_token"]
        chat_id = data["chat_id"]
        set_telegram_config(bot_token, chat_id)

        # Test gửi tin nhắn để kiểm tra cấu hình
        test_message = "🔔 *MT5 Bot Configuration Updated*\nBot token and chat ID configured successfully."
        config = get_telegram_config()
        sent = send_telegram_message(test_message)
        if not sent and config["enabled"]:
            logger.warning("Telegram configuration saved but test message failed to send.")

        return jsonify({
            "message": "Telegram configuration updated successfully",
            "config": {
                "bot_token": config["bot_token"],
                "chat_id": config["chat_id"],
                "enabled": config["enabled"]
            }
        })

    except Exception as e:
        logger.error(f"Error in set_telegram_config_endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@telegram_bp.route('/telegram/config', methods=['GET'])
@swag_from({
    'tags': ['Telegram'],
    'responses': {
        200: {
            'description': 'Telegram configuration retrieved successfully.',
            'schema': {
                'type': 'object',
                'properties': {
                    'config': {
                        'type': 'object',
                        'properties': {
                            'bot_token': {'type': 'string'},
                            'chat_id': {'type': 'string'},
                            'enabled': {'type': 'boolean'}
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
def get_telegram_config_endpoint():
    """Get current Telegram configuration."""
    try:
        config = get_telegram_config()
        return jsonify({
            "config": {
                "bot_token": config["bot_token"],
                "chat_id": config["chat_id"],
                "enabled": config["enabled"]
            }
        })

    except Exception as e:
        logger.error(f"Error in get_telegram_config_endpoint: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@telegram_bp.route('/telegram/enable', methods=['POST'])
@swag_from({
    'tags': ['Telegram'],
    'parameters': [],
    'responses': {
        200: {
            'description': 'Telegram signal sending enabled.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'enabled': {'type': 'boolean'}
                }
            }
        },
        400: {
            'description': 'Telegram configuration incomplete.'
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def enable_telegram_signals():
    """Enable Telegram signal sending."""
    try:
        config = get_telegram_config()
        if not config["bot_token"] or not config["chat_id"]:
            logger.error("Cannot enable: bot_token and chat_id must be configured")
            return jsonify({"error": "Cannot enable: bot_token and chat_id must be configured"}), 400

        config["enabled"] = True
        set_telegram_config(config["bot_token"], config["chat_id"])  # Cập nhật lại để đảm bảo đồng bộ

        # Gửi tin nhắn thông báo bật tính năng
        message = "🔔 *MT5 Bot Notification*\nTelegram signal sending has been enabled."
        send_telegram_message(message)

        return jsonify({"message": "Telegram signal sending enabled", "enabled": True})

    except Exception as e:
        logger.error(f"Error in enable_telegram_signals: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@telegram_bp.route('/telegram/disable', methods=['POST'])
@swag_from({
    'tags': ['Telegram'],
    'parameters': [],
    'responses': {
        200: {
            'description': 'Telegram signal sending disabled.',
            'schema': {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'enabled': {'type': 'boolean'}
                }
            }
        },
        500: {
            'description': 'Internal server error.'
        }
    }
})
def disable_telegram_signals():
    """Disable Telegram signal sending."""
    try:
        config = get_telegram_config()
        config["enabled"] = False
        set_telegram_config(config["bot_token"], config["chat_id"])  # Cập nhật lại để đảm bảo đồng bộ

        # Gửi tin nhắn thông báo tắt tính năng (nếu vẫn còn cấu hình)
        if config["bot_token"] and config["chat_id"]:
            message = "🔔 *MT5 Bot Notification*\nTelegram signal sending has been disabled."
            send_telegram_message(message)

        return jsonify({"message": "Telegram signal sending disabled", "enabled": False})

    except Exception as e:
        logger.error(f"Error in disable_telegram_signals: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500