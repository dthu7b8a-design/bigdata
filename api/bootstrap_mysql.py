"""Provision ONLY the authorized independent MySQL instance on 127.0.0.1:3307.

Never connects to port 3306, resets existing credentials, or changes a Windows service.
Generated credentials are stored only in api/.env; subprocess output is suppressed.
"""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

import pymysql

BASE = Path(os.getenv("MYSQL_BASEDIR", ""))
RUNTIME = Path(os.getenv("BIGDATA_MYSQL_RUNTIME", str(Path(__file__).resolve().parents[1] / "runtime" / "mysql")))
ENV = Path(__file__).with_name(".env")
DATABASE = "bigdata_dashboard"


def port_open():
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", 3307)) == 0


def main():
    if port_open():
        print("Port 3307 is already occupied; no instance was modified. Verify with /api/health.")
        return 1
    if not os.getenv("MYSQL_BASEDIR") or not (BASE / "bin/mysqld.exe").is_file():
        print("Set MYSQL_BASEDIR to a local MySQL installation containing bin/mysqld.exe; no instance was modified.")
        return 1
    data = RUNTIME / "data"
    existing = (data / "mysql").is_dir()
    if not existing and (ENV.exists() or (data.exists() and any(data.iterdir()))):
        print("Local configuration or partial data exists; refusing to overwrite it.")
        return 1
    if existing and not ENV.exists():
        print("Existing independent data has no local credentials; refusing to modify it.")
        return 1
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not existing:
        admin_password = secrets.token_urlsafe(32)
        api_password = secrets.token_urlsafe(32)
        # Write before initialization so credentials survive an interrupted setup.
        with ENV.open("x", encoding="utf-8") as stream:
            stream.write(f"MYSQL_HOST=127.0.0.1\nMYSQL_PORT=3307\nMYSQL_DATABASE={DATABASE}\nMYSQL_USER=bigdata_api\nMYSQL_PASSWORD={api_password}\nMYSQL_ADMIN_PASSWORD={admin_password}\n")
        initialized = subprocess.run([str(BASE / "bin/mysqld.exe"), "--no-defaults", "--initialize-insecure",
                                      f"--basedir={BASE.as_posix()}", f"--datadir={data.as_posix()}",
                                      f"--log-error={(RUNTIME / 'initialize.log').as_posix()}"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        if initialized.returncode:
            print("Independent MySQL initialization failed. Inspect runtime initialize.log locally.")
            return 1
    process = subprocess.Popen([str(BASE / "bin/mysqld.exe"), "--no-defaults", f"--basedir={BASE.as_posix()}",
                                f"--datadir={data.as_posix()}", "--port=3307", "--bind-address=127.0.0.1",
                                "--mysqlx=OFF", "--skip-log-bin", "--general-log=OFF", "--slow-query-log=OFF",
                                f"--log-error={(RUNTIME / 'mysql.log').as_posix()}",
                                f"--pid-file={(RUNTIME / 'mysql.pid').as_posix()}"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(120):
        if process.poll() is not None:
            print("Independent MySQL startup failed. Inspect runtime mysql.log locally.")
            return 1
        if port_open():
            break
        time.sleep(0.25)
    else:
        print("Independent MySQL did not become ready within 30 seconds.")
        return 1
    if not existing:
        try:
            conn = pymysql.connect(host="127.0.0.1", port=3307, user="root", password="", autocommit=True)
            with conn:
                with conn.cursor() as cur:
                    cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (admin_password,))
                    cur.execute(f"CREATE DATABASE `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
                    cur.execute("CREATE USER 'bigdata_api'@'localhost' IDENTIFIED BY %s", (api_password,))
                    cur.execute("CREATE USER 'bigdata_api'@'127.0.0.1' IDENTIFIED BY %s", (api_password,))
                    for host in ("localhost", "127.0.0.1"):
                        cur.execute(f"GRANT SELECT, INSERT, UPDATE, CREATE, REFERENCES ON `{DATABASE}`.* TO 'bigdata_api'@'{host}'")
        except pymysql.MySQLError:
            process.terminate()
            print("Independent MySQL provisioning failed; server stopped. Credentials were not logged.")
            return 1
    print("Independent MySQL running on 127.0.0.1:3307. Local credentials: api/.env (do not publish).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
