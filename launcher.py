import subprocess
import time
import logging

# ログ設定（任意）
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

while True:
    logging.info("🚀 controller.py を起動します")
    proc = subprocess.Popen(["python", "controller.py"])
    proc.wait()  # 終了を待つ

    logging.info("🔁 試合終了 → controller.py を再起動します")
    time.sleep(2)  # 少し待ってから再起動
