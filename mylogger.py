import logging

# Create your app-specific logger and set it to DEBUG
logger = logging.getLogger("hoopr")
logger.setLevel(logging.DEBUG)
logger.propagate = False

# 3️⃣ (Optional) Add a console handler if you want custom formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 4️⃣ Avoid adding multiple handlers if you re-run this in notebooks or REPLs
# if not logger.hasHandlers():
  # logger.addHandler(console_handler)