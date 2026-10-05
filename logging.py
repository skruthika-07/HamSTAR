import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Request bodies, passwords, tokens and API keys are never passed to this logger.
log = logging.getLogger("hamstar")
