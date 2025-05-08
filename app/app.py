import logging
import os
from flask import Flask
from dotenv import load_dotenv
import MetaTrader5 as mt5
from flasgger import Swagger
from werkzeug.middleware.proxy_fix import ProxyFix
from swagger import swagger_config

# Import routes
from routes.health import health_bp
from routes.symbol import symbol_bp
from routes.data import data_bp
from routes.position import position_bp
from routes.order import order_bp
from routes.history import history_bp
from routes.error import error_bp
from routes.telegram import telegram_bp

# Import worker functions
from trailing_stop_worker import start_worker, stop_worker # Import worker control functions
from trade_signal_worker import start_worker as start_signal_worker, stop_worker as stop_signal_worker

load_dotenv()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['PREFERRED_URL_SCHEME'] = 'https'

swagger = Swagger(app, config=swagger_config)

# Register blueprints
app.register_blueprint(health_bp)
app.register_blueprint(symbol_bp)
app.register_blueprint(data_bp)
app.register_blueprint(position_bp)
app.register_blueprint(order_bp)
app.register_blueprint(history_bp)
app.register_blueprint(error_bp)
app.register_blueprint(telegram_bp)

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

if __name__ == '__main__':
    # if not mt5.initialize():
        # logger.error("Failed to initialize MT5.")
        # Consider exiting or handling this more gracefully in a production app
    # else:
        # logger.info("MT5 initialized successfully.")
        # Start the trailing stop worker thread after MT5 is initialized
        # start_worker()


    # The Flask app.run() call is blocking, so the worker will run in the background thread
    # It's important that the worker is started before the app runs.
    try:
        start_worker()
        start_signal_worker()    # Khởi động trade signal worker           
        app.run(host='0.0.0.0', port=int(os.environ.get('MT5_API_PORT')))
     
        
    finally:
        # Ensure the worker thread is stopped when the app exits
        stop_worker()
        stop_signal_worker()    # Dừng trade signal worker
        logger.info("Flask app finished running.")


