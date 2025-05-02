import logging
import time
import threading
import MetaTrader5 as mt5
from lib import apply_trailing_stop # Import the core trailing stop logic

logger = logging.getLogger(__name__)

# Dictionary to store active trailing stop jobs: {position_ticket: trailing_distance}
# We store the distance here as the worker needs it for apply_trailing_stop
active_trailing_stop_jobs = {}

# Flag to control the worker thread loop
worker_running = False
worker_thread = None

def trailing_stop_worker_function():
    """
    The main function for the background worker thread.
    It periodically checks active jobs and applies trailing stops.
    """
    logger.info("Trailing stop worker thread started.")
    global worker_running
    worker_running = True

    while worker_running:
        # Iterate over a copy of the dictionary keys to avoid issues if jobs are removed during iteration
        tickets_to_process = list(active_trailing_stop_jobs.keys())
        # logger.debug(f"Worker: Checking {len(tickets_to_process)} active trailing stop jobs.") # Avoid excessive logging

        for position_ticket in tickets_to_process:
            # Check if the job is still in the dictionary (could have been removed by API call)
            if position_ticket in active_trailing_stop_jobs:
                trailing_distance = active_trailing_stop_jobs[position_ticket]
                try:
                    # Check if position exists BEFORE attempting to apply trailing stop
                    positions_before = mt5.positions_get(ticket=position_ticket)
                    if positions_before is None or len(positions_before) == 0:
                        logger.info(f"Worker: Position {position_ticket} no longer exists (check before apply). Removing job.")
                        remove_trailing_stop_job_from_worker(position_ticket)
                        continue # Move to the next ticket

                    # Call the core trailing stop logic
                    result = apply_trailing_stop(position_ticket, trailing_distance)

                    if result is None:
                        logger.error(f"Worker: Failed to apply trailing stop for position {position_ticket}. Will retry.")
                    elif "message" in result and result["message"] == "No SL update needed":
                        # logger.info(f"Worker: Trailing stop for position {position_ticket}: No SL update needed.") # Avoid excessive logging
                        pass
                    else:
                        logger.info(f"Worker: Trailing stop applied successfully for position {position_ticket}. Result: {result}")

                    # --- Check if position still exists AFTER attempting to apply trailing stop ---
                    # This is important in case the trailing stop just hit and closed the position
                    positions_after = mt5.positions_get(ticket=position_ticket)
                    if positions_after is None or len(positions_after) == 0:
                         logger.info(f"Worker: Position {position_ticket} no longer exists (check after apply). Removing job.")
                         remove_trailing_stop_job_from_worker(position_ticket)
                    # --- End Check ---


                except Exception as e:
                    logger.error(f"Worker: Error applying trailing stop for position {position_ticket}: {str(e)}")
                    # Decide how to handle persistent errors. For now, just log and continue.
                    # Consider adding logic here to remove the job after N consecutive failures.


        # Sleep for the interval before the next check
        # Note: With a single interval for all jobs, this is simpler.
        # If different intervals per job are needed, the logic would be more complex (e.g., using a min-heap or similar)
        # For this new solution, let's assume a common check interval for the worker loop.
        # A fixed interval like 5 seconds seems reasonable for most trailing stop needs.
        # We can make this interval configurable if needed.
        check_interval_seconds = 5 # Default worker check interval
        time.sleep(check_interval_seconds)

    logger.info("Trailing stop worker thread stopped.")

def start_worker():
    """
    Starts the background trailing stop worker thread.
    """
    global worker_thread
    if worker_thread is None or not worker_thread.is_alive():
        logger.info("Starting trailing stop worker thread.")
        worker_thread = threading.Thread(target=trailing_stop_worker_function, daemon=True)
        worker_thread.start()
        logger.info("Trailing stop worker thread started successfully.")
    else:
        logger.warning("Trailing stop worker thread is already running.")


def stop_worker():
    """
    Stops the background trailing stop worker thread.
    """
    global worker_running, worker_thread
    if worker_thread and worker_thread.is_alive():
        logger.info("Stopping trailing stop worker thread.")
        worker_running = False
        worker_thread.join(timeout=10) # Wait for the thread to finish (with a timeout)
        if worker_thread.is_alive():
            logger.warning("Trailing stop worker thread did not stop gracefully.")
        worker_thread = None
        logger.info("Trailing stop worker thread stopped.")
    else:
        logger.warning("Trailing stop worker thread is not running.")

def add_trailing_stop_job_to_worker(position_ticket: int, trailing_distance: float):
    """
    Adds or updates a trailing stop job in the worker's tracking dictionary.

    Args:
        position_ticket: The ticket number of the position.
        trailing_distance: The trailing stop distance in points.

    Returns:
        True if added/updated successfully, False if position not found.
    """
    # Check if the position exists before adding/updating (Optional but good practice)
    positions = mt5.positions_get(ticket=position_ticket)
    if positions is None or len(positions) == 0:
         logger.error(f"Position with ticket {position_ticket} not found. Cannot add/update job in worker.")
         return False

    # If the position is already being tracked, log that we are updating the distance
    if position_ticket in active_trailing_stop_jobs:
        logger.info(f"Updating trailing stop distance for position {position_ticket} from {active_trailing_stop_jobs[position_ticket]} to {trailing_distance}.")
    else:
        logger.info(f"Adding new trailing stop job for position {position_ticket} with distance {trailing_distance} to worker tracking.")


    # Add or update the entry in the dictionary
    active_trailing_stop_jobs[position_ticket] = trailing_distance

    return True

def remove_trailing_stop_job_from_worker(position_ticket: int):
    """
    Removes a trailing stop job from the worker's tracking dictionary.

    Args:
        position_ticket: The ticket number of the position.

    Returns:
        True if removed successfully, False if job not found.
    """
    if position_ticket in active_trailing_stop_jobs:
        del active_trailing_stop_jobs[position_ticket]
        logger.info(f"Removed trailing stop job for position {position_ticket} from worker tracking.")
        return True
    else:
        logger.warning(f"No trailing stop job found for position {position_ticket} in worker tracking.")
        return False

def get_active_worker_jobs_list():
    """
    Retrieves a list of details for all active trailing stop jobs tracked by the worker.

    Returns:
        A list of dictionaries, each representing an active job.
    """
    # Convert the dictionary items to a list of dictionaries
    jobs_list = [
        {'position_ticket': ticket, 'trailing_distance': distance}
        for ticket, distance in active_trailing_stop_jobs.items()
    ]
    logger.info(f"Retrieved list of {len(jobs_list)} active worker jobs.")
    return jobs_list

