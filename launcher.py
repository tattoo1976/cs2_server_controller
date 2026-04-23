import logging
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

while True:
    logging.info("controller.py を起動します")
    proc = subprocess.Popen([sys.executable, "controller.py"])
    proc.wait()

    logging.info("試合終了 -> controller.py を再起動します")
    time.sleep(2)
