import csv
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tkinter as tk
import threading
import socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from tkinter import filedialog, messagebox, ttk


def get_bundle_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def get_data_dir():
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        base_dir = Path(local_appdata)
    else:
        base_dir = Path.home() / "AppData" / "Local"

    data_dir = base_dir / "Idana Technologies and Projects PTY LTD" / "StockManagementApp"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


BUNDLE_DIR = get_bundle_dir()
DATA_DIR = get_data_dir()
DB_PATH = DATA_DIR / "inventory.db"
ASSETS_DIR = BUNDLE_DIR / "assets"
ICON_ICO_PATH = ASSETS_DIR / "app_icon.ico"
ICON_PNG_PATH = ASSETS_DIR / "app_icon.png"
RECEIPTS_DIR = DATA_DIR / "receipts"

COLORS = {
    "bg": "#f3efe7",
    "panel": "#fffaf2",
    "panel_alt": "#f7f0e3",
    "border": "#ded2c1",
    "text": "#1f2933",
    "muted": "#6b7280",
    "teal": "#0f766e",
    "teal_dark": "#134e4a",
    "gold": "#b45309",
    "blue": "#1d4ed8",
    "red": "#b42318",
    "cream": "#ece2d0",
}

PHONE_SCANNER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Phone Barcode Scanner</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #f3efe7; color: #1f2933; }
    .shell { max-width: 760px; margin: 0 auto; padding: 24px 16px 40px; }
    .card { background: #fffaf2; border: 1px solid #ded2c1; border-radius: 18px; padding: 18px; margin-bottom: 16px; }
    h1 { margin: 0 0 8px; font-size: 1.5rem; }
    p { line-height: 1.45; }
    #reader { width: 100%; min-height: 280px; overflow: hidden; border-radius: 14px; background: #000; }
    video { width: 100%; border-radius: 14px; background: #000; }
    input, button { width: 100%; box-sizing: border-box; padding: 14px; font-size: 1rem; border-radius: 12px; }
    input { border: 1px solid #cbbca8; margin-bottom: 12px; }
    button { border: 0; background: #0f766e; color: white; font-weight: 700; margin-bottom: 10px; }
    .secondary { background: #1d4ed8; }
    .muted { color: #6b7280; }
    .ok { color: #0f766e; font-weight: 700; }
    .warn { color: #b42318; font-weight: 700; }
  </style>
  <script src="https://unpkg.com/html5-qrcode" defer></script>
</head>
<body>
  <div class="shell">
    <div class="card">
      <h1>Phone Barcode Scanner</h1>
      <p>Keep your phone on the same Wi-Fi as the desktop app. Scan a barcode, then send it into the stock app.</p>
      <p class="muted">This page first tries a wider-compatibility scanner library. If that still does not work, use the manual barcode box below.</p>
    </div>
    <div class="card">
      <div id="reader"></div>
      <video id="preview" autoplay playsinline muted style="display:none;"></video>
      <p id="scannerStatus" class="muted">Starting camera...</p>
    </div>
    <div class="card">
      <input id="barcodeInput" placeholder="Scanned barcode will appear here">
      <button id="sendFind">Send To App and Find</button>
      <button id="sendSale" class="secondary">Send To App and Open Sale</button>
      <p id="result" class="muted">Waiting for scan...</p>
    </div>
  </div>
  <script>
    const input = document.getElementById("barcodeInput");
    const result = document.getElementById("result");
    const scannerStatus = document.getElementById("scannerStatus");
    const video = document.getElementById("preview");
    const readerContainer = document.getElementById("reader");
    let detector = null;
    let scanTimer = null;
    let html5Scanner = null;

    async function sendBarcode(action) {
      const barcode = input.value.trim();
      if (!barcode) {
        result.textContent = "Enter or scan a barcode first.";
        result.className = "warn";
        return;
      }
      try {
        const response = await fetch("/scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ barcode, action })
        });
        const data = await response.json();
        result.textContent = data.message;
        result.className = response.ok ? "ok" : "warn";
      } catch (error) {
        result.textContent = "Could not send barcode to desktop app.";
        result.className = "warn";
      }
    }

    function setScannedCode(code) {
      if (!code) {
        return;
      }
      input.value = code;
      result.textContent = "Barcode captured. Tap a send button.";
      result.className = "ok";
    }

    document.getElementById("sendFind").addEventListener("click", () => sendBarcode("find"));
    document.getElementById("sendSale").addEventListener("click", () => sendBarcode("sale"));
    input.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        sendBarcode("find");
      }
    });

    async function startHtml5Scanner() {
      if (!window.Html5Qrcode) {
        return false;
      }
      try {
        html5Scanner = new Html5Qrcode("reader");
        await html5Scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 260, height: 120 }, aspectRatio: 1.7 },
          decodedText => setScannedCode(decodedText),
          () => {}
        );
        scannerStatus.textContent = "Camera ready. Point at a barcode.";
        return true;
      } catch (error) {
        scannerStatus.textContent = "Advanced scanner could not start. Trying browser fallback...";
        return false;
      }
    }

    async function startBarcodeDetectorFallback() {
      if (!("mediaDevices" in navigator) || !("BarcodeDetector" in window)) {
        return false;
      }
      try {
        readerContainer.style.display = "none";
        video.style.display = "block";
        detector = new BarcodeDetector({ formats: ["ean_13", "ean_8", "code_128", "code_39", "upc_a", "upc_e", "qr_code"] });
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        video.srcObject = stream;
        scannerStatus.textContent = "Camera ready. Point at a barcode.";
        scanTimer = setInterval(async () => {
          try {
            const barcodes = await detector.detect(video);
            if (barcodes.length > 0 && barcodes[0].rawValue) {
              setScannedCode(barcodes[0].rawValue);
            }
          } catch (error) {
          }
        }, 700);
        return true;
      } catch (error) {
        return false;
      }
    }

    async function startScanner() {
      scannerStatus.textContent = "Starting camera...";
      const html5Ready = await startHtml5Scanner();
      if (html5Ready) {
        return;
      }
      const detectorReady = await startBarcodeDetectorFallback();
      if (detectorReady) {
        return;
      }
      scannerStatus.textContent = "Live camera scanning is not available here. Use manual input.";
    }

    window.addEventListener("load", () => {
      setTimeout(startScanner, 250);
    });
  </script>
</body>
</html>
"""


class PhoneScanServer:
    def __init__(self, app, port=8765):
        self.app = app
        self.port = port
        self.server = None
        self.thread = None
        self.host_ip = self._detect_host_ip()

    def _detect_host_ip(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            sock.close()

    def start(self):
        if self.server is not None:
            return

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    body = PHONE_SCANNER_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path != "/scan":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    self._json_response(400, {"message": "Invalid request."})
                    return

                barcode = str(payload.get("barcode", "")).strip()
                action = str(payload.get("action", "find")).strip().lower()
                if not barcode:
                    self._json_response(400, {"message": "Barcode is required."})
                    return
                if action not in {"find", "sale"}:
                    action = "find"

                outer.app.phone_scan_queue.put({"barcode": barcode, "action": action})
                message = "Barcode sent to app." if action == "find" else "Barcode sent to app for sale."
                self._json_response(200, {"message": message})

            def _json_response(self, status_code, payload):
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def url(self):
        return f"http://{self.host_ip}:{self.port}"


class InventoryDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sku TEXT NOT NULL UNIQUE,
                    barcode TEXT UNIQUE,
                    category TEXT NOT NULL,
                    price REAL NOT NULL DEFAULT 0,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    supplier TEXT,
                    low_stock_limit INTEGER NOT NULL DEFAULT 5
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
            if "barcode" not in columns:
                conn.execute("ALTER TABLE products ADD COLUMN barcode TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    customer_name TEXT,
                    notes TEXT,
                    sold_at TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL
                )
                """
            )
            conn.commit()
            self._seed_default_users(conn)

    def _seed_default_users(self, conn):
        existing = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
        if existing:
            return

        default_users = [
            ("admin", self.hash_password("admin123"), "admin"),
            ("cashier", self.hash_password("cashier123"), "cashier"),
        ]
        conn.executemany(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            default_users,
        )
        conn.commit()

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def authenticate_user(self, username, password):
        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
            if user is None:
                return None
            if user["password_hash"] != self.hash_password(password):
                return None
            return user

    def update_user_password(self, user_id, new_password):
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (self.hash_password(new_password), user_id),
            )
            conn.commit()

    def fetch_products(self, search=""):
        query = """
            SELECT *
            FROM products
            WHERE name LIKE ? OR sku LIKE ? OR barcode LIKE ? OR category LIKE ? OR supplier LIKE ?
            ORDER BY quantity ASC, name COLLATE NOCASE ASC
        """
        wildcard = f"%{search.strip()}%"
        with self._connect() as conn:
            return conn.execute(query, (wildcard, wildcard, wildcard, wildcard, wildcard)).fetchall()

    def fetch_product(self, product_id):
        with self._connect() as conn:
            return conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    def fetch_product_by_barcode(self, barcode):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM products WHERE barcode = ?",
                (barcode.strip(),),
            ).fetchone()

    def create_product(self, payload):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO products (name, sku, barcode, category, price, quantity, supplier, low_stock_limit)
                VALUES (:name, :sku, :barcode, :category, :price, :quantity, :supplier, :low_stock_limit)
                """,
                payload,
            )
            conn.commit()

    def update_product(self, product_id, payload):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE products
                SET name = :name,
                    sku = :sku,
                    barcode = :barcode,
                    category = :category,
                    price = :price,
                    quantity = :quantity,
                    supplier = :supplier,
                    low_stock_limit = :low_stock_limit
                WHERE id = :id
                """,
                {**payload, "id": product_id},
            )
            conn.commit()

    def delete_product(self, product_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()

    def adjust_stock(self, product_id, change):
        with self._connect() as conn:
            current = conn.execute(
                "SELECT quantity FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
            if current is None:
                return

            new_quantity = max(0, current["quantity"] + change)
            conn.execute(
                "UPDATE products SET quantity = ? WHERE id = ?",
                (new_quantity, product_id),
            )
            conn.commit()

    def record_sale(self, product_id, quantity, unit_price, customer_name="", notes=""):
        with self._connect() as conn:
            product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                raise ValueError("Product not found.")
            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")
            if unit_price < 0:
                raise ValueError("Unit price cannot be negative.")
            if product["quantity"] < quantity:
                raise ValueError("Not enough stock available for this sale.")

            total_amount = quantity * unit_price
            conn.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (quantity, product_id),
            )
            conn.execute(
                """
                INSERT INTO sales (
                    product_id,
                    product_name,
                    quantity,
                    unit_price,
                    total_amount,
                    customer_name,
                    notes,
                    sold_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    product["name"],
                    quantity,
                    unit_price,
                    total_amount,
                    customer_name.strip(),
                    notes.strip(),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            sale_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()
            return {
                "sale_id": sale_id,
                "product_id": product_id,
                "product_name": product["name"],
                "sku": product["sku"],
                "quantity": quantity,
                "unit_price": unit_price,
                "total_amount": total_amount,
                "customer_name": customer_name.strip(),
                "notes": notes.strip(),
                "sold_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    def fetch_sales(self, limit=100, search=""):
        wildcard = f"%{search.strip()}%"
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM sales
                WHERE sold_at LIKE ? OR product_name LIKE ? OR customer_name LIKE ? OR notes LIKE ?
                ORDER BY sold_at DESC, id DESC
                LIMIT ?
                """,
                (wildcard, wildcard, wildcard, wildcard, limit),
            ).fetchall()

    def fetch_daily_sales(self, limit=31):
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT
                    substr(sold_at, 1, 10) AS sale_date,
                    COUNT(*) AS sale_count,
                    COALESCE(SUM(quantity), 0) AS units_sold,
                    COALESCE(SUM(total_amount), 0) AS revenue
                FROM sales
                GROUP BY substr(sold_at, 1, 10)
                ORDER BY sale_date DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def summary(self):
        with self._connect() as conn:
            inventory = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_products,
                    COALESCE(SUM(quantity), 0) AS total_units,
                    COALESCE(SUM(quantity * price), 0) AS inventory_value
                FROM products
                """
            ).fetchone()
            low_stock = conn.execute(
                "SELECT COUNT(*) AS count FROM products WHERE quantity <= low_stock_limit"
            ).fetchone()
            sales = conn.execute(
                """
                SELECT
                    COUNT(*) AS sale_count,
                    COALESCE(SUM(quantity), 0) AS units_sold,
                    COALESCE(SUM(total_amount), 0) AS revenue
                FROM sales
                """
            ).fetchone()
            today = conn.execute(
                """
                SELECT
                    COUNT(*) AS today_sale_count,
                    COALESCE(SUM(quantity), 0) AS today_units_sold,
                    COALESCE(SUM(total_amount), 0) AS today_revenue
                FROM sales
                WHERE substr(sold_at, 1, 10) = date('now', 'localtime')
                """
            ).fetchone()
            return {
                "total_products": inventory["total_products"],
                "total_units": inventory["total_units"],
                "inventory_value": inventory["inventory_value"],
                "low_stock_count": low_stock["count"],
                "sale_count": sales["sale_count"],
                "units_sold": sales["units_sold"],
                "revenue": sales["revenue"],
                "today_sale_count": today["today_sale_count"],
                "today_units_sold": today["today_units_sold"],
                "today_revenue": today["today_revenue"],
            }

    def low_stock_products(self):
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM products
                WHERE quantity <= low_stock_limit
                ORDER BY quantity ASC, name COLLATE NOCASE ASC
                """
            ).fetchall()

    def export_inventory_csv(self, file_path):
        rows = self.fetch_products("")
        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["ID", "Name", "SKU", "Category", "Price", "Quantity", "Supplier", "Low Stock Limit"]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["id"],
                        row["name"],
                        row["sku"],
                        row["category"],
                        row["price"],
                        row["quantity"],
                        row["supplier"] or "",
                        row["low_stock_limit"],
                    ]
                )

    def export_sales_csv(self, file_path):
        rows = self.fetch_sales(limit=100000)
        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "ID",
                    "Product ID",
                    "Product Name",
                    "Quantity",
                    "Unit Price",
                    "Total Amount",
                    "Customer Name",
                    "Notes",
                    "Sold At",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["id"],
                        row["product_id"],
                        row["product_name"],
                        row["quantity"],
                        row["unit_price"],
                        row["total_amount"],
                        row["customer_name"] or "",
                        row["notes"] or "",
                        row["sold_at"],
                    ]
                )

    def backup_database(self, destination_path):
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as source_conn:
            with sqlite3.connect(destination) as backup_conn:
                source_conn.backup(backup_conn)

    def restore_database(self, source_path):
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError("Selected backup file was not found.")

        temp_restore = self.db_path.with_suffix(".restore_tmp.db")
        try:
            shutil.copy2(source, temp_restore)
            with sqlite3.connect(temp_restore) as conn:
                conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            shutil.copy2(temp_restore, self.db_path)
        finally:
            if temp_restore.exists():
                temp_restore.unlink()


class Panel(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, style="Panel.TFrame", padding=kwargs.get("padding", 18))


class ProductDialog(tk.Toplevel):
    def __init__(self, master, title, on_save, product=None):
        super().__init__(master)
        self.title(title)
        self.on_save = on_save
        self.product = product
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])

        self.vars = {
            "name": tk.StringVar(value=product["name"] if product else ""),
            "sku": tk.StringVar(value=product["sku"] if product else ""),
            "barcode": tk.StringVar(value=product["barcode"] if product and product["barcode"] else ""),
            "category": tk.StringVar(value=product["category"] if product else ""),
            "price": tk.StringVar(value=str(product["price"]) if product else ""),
            "quantity": tk.StringVar(value=str(product["quantity"]) if product else "0"),
            "supplier": tk.StringVar(value=product["supplier"] if product else ""),
            "low_stock_limit": tk.StringVar(
                value=str(product["low_stock_limit"]) if product else "5"
            ),
        }

        self._build()
        self.transient(master)
        self.grab_set()
        self.focus()

    def _build(self):
        shell = tk.Frame(self, bg=COLORS["panel"], padx=20, pady=20, highlightbackground=COLORS["border"], highlightthickness=1)
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            shell,
            text=self.title(),
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 16),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        fields = [
            ("Product Name", "name"),
            ("SKU", "sku"),
            ("Barcode", "barcode"),
            ("Category", "category"),
            ("Price", "price"),
            ("Quantity", "quantity"),
            ("Supplier", "supplier"),
            ("Low Stock Limit", "low_stock_limit"),
        ]

        for row, (label, key) in enumerate(fields, start=1):
            tk.Label(
                shell,
                text=label,
                anchor="w",
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 10, "bold"),
            ).grid(row=row, column=0, sticky="w", pady=(0, 6), padx=(0, 12))
            entry = tk.Entry(
                shell,
                textvariable=self.vars[key],
                width=34,
                font=("Segoe UI", 10),
                relief="flat",
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            entry.grid(row=row, column=1, sticky="ew", pady=(0, 10))

        button_row = tk.Frame(shell, bg=COLORS["panel"])
        button_row.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="e", pady=(8, 0))

        tk.Button(
            button_row,
            text="Cancel",
            command=self.destroy,
            bg=COLORS["cream"],
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            button_row,
            text="Save Product",
            command=self._submit,
            bg=COLORS["teal"],
            fg="white",
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="left")

    def _submit(self):
        try:
            payload = {
                "name": self.vars["name"].get().strip(),
                "sku": self.vars["sku"].get().strip(),
                "barcode": self.vars["barcode"].get().strip() or None,
                "category": self.vars["category"].get().strip(),
                "price": float(self.vars["price"].get()),
                "quantity": int(self.vars["quantity"].get()),
                "supplier": self.vars["supplier"].get().strip(),
                "low_stock_limit": int(self.vars["low_stock_limit"].get()),
            }
        except ValueError:
            messagebox.showerror("Invalid values", "Price, quantity, and low stock limit must be numbers.")
            return

        if not payload["name"] or not payload["sku"] or not payload["category"]:
            messagebox.showerror("Missing fields", "Name, SKU, and category are required.")
            return
        if payload["price"] < 0 or payload["quantity"] < 0 or payload["low_stock_limit"] < 0:
            messagebox.showerror("Invalid values", "Negative values are not allowed.")
            return

        try:
            self.on_save(payload)
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate SKU", "That SKU already exists. Please use a unique SKU.")
            return

        self.destroy()


class StockAdjustmentDialog(tk.Toplevel):
    def __init__(self, master, product_name, on_apply):
        super().__init__(master)
        self.title("Adjust Stock")
        self.on_apply = on_apply
        self.amount_var = tk.StringVar(value="1")
        self.mode_var = tk.StringVar(value="in")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        shell = tk.Frame(self, bg=COLORS["panel"], padx=20, pady=20, highlightbackground=COLORS["border"], highlightthickness=1)
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            shell,
            text=f"Adjust stock for {product_name}",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 15),
        ).pack(anchor="w", pady=(0, 12))

        tk.Label(shell, text="Quantity", bg=COLORS["panel"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Entry(
            shell,
            textvariable=self.amount_var,
            width=24,
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        ).pack(anchor="w", pady=(6, 12))

        mode_frame = tk.Frame(shell, bg=COLORS["panel"])
        mode_frame.pack(anchor="w", pady=(0, 14))
        tk.Radiobutton(mode_frame, text="Stock In", variable=self.mode_var, value="in", bg=COLORS["panel"]).pack(side="left", padx=(0, 10))
        tk.Radiobutton(mode_frame, text="Stock Out", variable=self.mode_var, value="out", bg=COLORS["panel"]).pack(side="left")

        action_row = tk.Frame(shell, bg=COLORS["panel"])
        action_row.pack(anchor="e")
        tk.Button(action_row, text="Cancel", command=self.destroy, bg=COLORS["cream"], relief="flat", padx=16, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(action_row, text="Apply", command=self._apply, bg=COLORS["teal"], fg="white", relief="flat", padx=16, pady=8).pack(side="left")

        self.transient(master)
        self.grab_set()
        self.focus()

    def _apply(self):
        try:
            amount = int(self.amount_var.get())
        except ValueError:
            messagebox.showerror("Invalid quantity", "Enter a valid whole number.")
            return

        if amount <= 0:
            messagebox.showerror("Invalid quantity", "Quantity must be greater than zero.")
            return

        change = amount if self.mode_var.get() == "in" else -amount
        self.on_apply(change)
        self.destroy()


class SaleDialog(tk.Toplevel):
    def __init__(self, master, product, on_save):
        super().__init__(master)
        self.title("Record Sale")
        self.product = product
        self.on_save = on_save
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        self.quantity_var = tk.StringVar(value="1")
        self.unit_price_var = tk.StringVar(value=f"{product['price']:.2f}")
        self.customer_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        self.create_receipt_var = tk.BooleanVar(value=True)
        self.print_receipt_var = tk.BooleanVar(value=False)

        shell = tk.Frame(self, bg=COLORS["panel"], padx=20, pady=20, highlightbackground=COLORS["border"], highlightthickness=1)
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            shell,
            text=f"Record sale for {product['name']}",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 15),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        info = f"Available stock: {product['quantity']}    SKU: {product['sku']}"
        tk.Label(shell, text=info, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))

        fields = [
            ("Quantity", self.quantity_var),
            ("Unit Price", self.unit_price_var),
            ("Customer Name", self.customer_var),
            ("Notes", self.notes_var),
        ]

        for row, (label, variable) in enumerate(fields, start=2):
            tk.Label(shell, text=label, bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 6), padx=(0, 12))
            tk.Entry(
                shell,
                textvariable=variable,
                width=34,
                font=("Segoe UI", 10),
                relief="flat",
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            ).grid(row=row, column=1, sticky="ew", pady=(0, 10))

        options_frame = tk.Frame(shell, bg=COLORS["panel"])
        options_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 10))
        tk.Checkbutton(
            options_frame,
            text="Create receipt file",
            variable=self.create_receipt_var,
            bg=COLORS["panel"],
            activebackground=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 10),
        ).pack(anchor="w")
        tk.Checkbutton(
            options_frame,
            text="Print receipt after saving",
            variable=self.print_receipt_var,
            bg=COLORS["panel"],
            activebackground=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 10),
        ).pack(anchor="w")

        action_row = tk.Frame(shell, bg=COLORS["panel"])
        action_row.grid(row=7, column=0, columnspan=2, sticky="e", pady=(8, 0))
        tk.Button(action_row, text="Cancel", command=self.destroy, bg=COLORS["cream"], relief="flat", padx=16, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(action_row, text="Save Sale", command=self._submit, bg=COLORS["gold"], fg="white", relief="flat", padx=16, pady=8).pack(side="left")

        self.transient(master)
        self.grab_set()
        self.focus()

    def _submit(self):
        try:
            quantity = int(self.quantity_var.get())
            unit_price = float(self.unit_price_var.get())
        except ValueError:
            messagebox.showerror("Invalid values", "Quantity must be a whole number and unit price must be numeric.")
            return

        if quantity <= 0:
            messagebox.showerror("Invalid quantity", "Quantity must be greater than zero.")
            return

        try:
            self.on_save(
                quantity,
                unit_price,
                self.customer_var.get().strip(),
                self.notes_var.get().strip(),
                self.create_receipt_var.get(),
                self.print_receipt_var.get(),
            )
        except ValueError as error:
            messagebox.showerror("Sale error", str(error))
            return

        self.destroy()


class SplashScreen(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(bg=COLORS["bg"])

        width = 520
        height = 300
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = int((screen_width - width) / 2)
        y_pos = int((screen_height - height) / 2)
        self.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

        shell = tk.Frame(
            self,
            bg=COLORS["panel"],
            padx=28,
            pady=28,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        if ICON_PNG_PATH.exists():
            try:
                self.icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH))
                tk.Label(shell, image=self.icon_image, bg=COLORS["panel"]).pack(pady=(0, 16))
            except tk.TclError:
                self.icon_image = None

        tk.Label(
            shell,
            text="Stock Management App",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 22),
        ).pack()
        tk.Label(
            shell,
            text="Loading inventory, sales, and reporting workspace...",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 11),
        ).pack(pady=(10, 18))
        tk.Label(
            shell,
            text="Powered by Idana Technologies and Projects PTY (LTD)",
            bg=COLORS["panel"],
            fg=COLORS["teal_dark"],
            font=("Segoe UI", 9, "bold"),
        ).pack(pady=(0, 14))

        progress_wrap = tk.Frame(shell, bg=COLORS["cream"], height=14)
        progress_wrap.pack(fill="x", padx=24, pady=(0, 16))
        progress_wrap.pack_propagate(False)

        self.progress_bar = tk.Frame(progress_wrap, bg=COLORS["teal"])
        self.progress_bar.place(relheight=1, relwidth=0.0)

        self.status_label = tk.Label(
            shell,
            text="Starting up...",
            bg=COLORS["panel"],
            fg=COLORS["teal_dark"],
            font=("Segoe UI", 10, "bold"),
        )
        self.status_label.pack()

    def set_progress(self, ratio, message):
        ratio = max(0.0, min(1.0, ratio))
        self.progress_bar.place(relheight=1, relwidth=ratio)
        self.status_label.config(text=message)
        self.update_idletasks()


class LoginDialog(tk.Toplevel):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db
        self.user = None
        self.title("Sign In")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.attributes("-topmost", True)

        self.username_var = tk.StringVar(value="admin")
        self.password_var = tk.StringVar(value="admin123")

        self._build()
        self.grab_set()
        self.update_idletasks()
        self._center_window()
        self.focus_force()

    def _center_window(self):
        width = max(430, self.winfo_reqwidth())
        height = max(320, self.winfo_reqheight())
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = int((screen_width - width) / 2)
        y_pos = int((screen_height - height) / 2)
        self.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    def _build(self):
        shell = tk.Frame(
            self,
            bg=COLORS["panel"],
            padx=24,
            pady=24,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        shell.grid_columnconfigure(1, weight=1)

        tk.Label(
            shell,
            text="Login",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 18),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        tk.Label(
            shell,
            text="Use admin or cashier credentials to open the app.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))

        fields = [
            ("Username", self.username_var, False),
            ("Password", self.password_var, True),
        ]
        for row, (label, variable, masked) in enumerate(fields, start=2):
            tk.Label(
                shell,
                text=label,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 10, "bold"),
            ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
            entry = tk.Entry(
                shell,
                textvariable=variable,
                width=28,
                show="*" if masked else "",
                font=("Segoe UI", 10),
                relief="flat",
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            entry.grid(row=row, column=1, sticky="ew", pady=(0, 8))
            if row == 2:
                entry.focus_set()

        tk.Label(
            shell,
            text="Default admin: admin / admin123    Default cashier: cashier / cashier123",
            bg=COLORS["panel"],
            fg=COLORS["teal_dark"],
            font=("Segoe UI", 9, "bold"),
            wraplength=380,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 14))

        actions = tk.Frame(shell, bg=COLORS["panel"])
        actions.grid(row=5, column=0, columnspan=2, sticky="e")
        tk.Button(actions, text="Exit", command=self._cancel, bg=COLORS["cream"], relief="flat", padx=16, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Login", command=self._login, bg=COLORS["teal"], fg="white", relief="flat", padx=16, pady=8).pack(side="left")

        self.bind("<Return>", lambda event: self._login())

    def _login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        user = self.db.authenticate_user(username, password)
        if user is None:
            messagebox.showerror("Login failed", "Incorrect username or password.")
            return
        self.user = user
        self.destroy()

    def _cancel(self):
        self.user = None
        self.destroy()


class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, master, username, on_save):
        super().__init__(master)
        self.title("Change Password")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.on_save = on_save

        self.current_password_var = tk.StringVar()
        self.new_password_var = tk.StringVar()
        self.confirm_password_var = tk.StringVar()

        shell = tk.Frame(
            self,
            bg=COLORS["panel"],
            padx=24,
            pady=24,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        shell.grid_columnconfigure(1, weight=1)

        tk.Label(
            shell,
            text=f"Change password for {username}",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 16),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        fields = [
            ("Current Password", self.current_password_var),
            ("New Password", self.new_password_var),
            ("Confirm Password", self.confirm_password_var),
        ]
        for row, (label, variable) in enumerate(fields, start=1):
            tk.Label(
                shell,
                text=label,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=("Segoe UI", 10, "bold"),
            ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
            tk.Entry(
                shell,
                textvariable=variable,
                show="*",
                width=28,
                font=("Segoe UI", 10),
                relief="flat",
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            ).grid(row=row, column=1, sticky="ew", pady=(0, 8))

        actions = tk.Frame(shell, bg=COLORS["panel"])
        actions.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        tk.Button(actions, text="Cancel", command=self.destroy, bg=COLORS["cream"], relief="flat", padx=16, pady=8).pack(side="left", padx=(0, 8))
        tk.Button(actions, text="Save", command=self._submit, bg=COLORS["teal"], fg="white", relief="flat", padx=16, pady=8).pack(side="left")

        self.bind("<Return>", lambda event: self._submit())
        self.transient(master)
        self.grab_set()
        self.update_idletasks()
        self._center_window()
        self.focus_force()

    def _center_window(self):
        width = max(430, self.winfo_reqwidth())
        height = max(260, self.winfo_reqheight())
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = int((screen_width - width) / 2)
        y_pos = int((screen_height - height) / 2)
        self.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    def _submit(self):
        current_password = self.current_password_var.get()
        new_password = self.new_password_var.get()
        confirm_password = self.confirm_password_var.get()

        if not current_password or not new_password or not confirm_password:
            messagebox.showerror("Missing fields", "Please complete all password fields.")
            return
        if new_password != confirm_password:
            messagebox.showerror("Password mismatch", "New password and confirmation do not match.")
            return
        if len(new_password) < 6:
            messagebox.showerror("Weak password", "New password must be at least 6 characters long.")
            return

        try:
            self.on_save(current_password, new_password)
        except ValueError as error:
            messagebox.showerror("Password change failed", str(error))
            return

        messagebox.showinfo("Password updated", "Your password was changed successfully.")
        self.destroy()


class StockManagementApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.db = InventoryDatabase(DB_PATH)
        login = LoginDialog(self, self.db)
        self.wait_window(login)
        if login.user is None:
            self.destroy()
            return
        self.current_user = login.user
        self.title("Stock Management Desktop App")
        self.geometry("1320x820")
        self.minsize(980, 640)
        self.configure(bg=COLORS["bg"])

        self.search_var = tk.StringVar()
        self.barcode_var = tk.StringVar()
        self.sales_search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.phone_scan_queue = Queue()
        self.summary_labels = {}
        self.report_labels = {}
        self.tree = None
        self.sales_tree = None
        self.daily_sales_tree = None
        self.low_stock_list = None
        self._icon_image = None
        self.last_receipt_path = None
        self.add_button = None
        self.edit_button = None
        self.delete_button = None
        self.restore_button = None
        self.phone_server = PhoneScanServer(self)

        self._configure_style()
        self._configure_icon()
        splash = SplashScreen(self)
        splash.set_progress(0.2, "Preparing workspace...")
        self.phone_server.start()
        self._build_layout()
        splash.set_progress(0.6, "Loading inventory and sales data...")
        self.refresh_all()
        splash.set_progress(1.0, "Ready")
        self.after(250, splash.destroy)
        self.after(250, self.deiconify)
        self.after(300, self.lift)
        self.after(250, self._poll_phone_scans)
        self.protocol("WM_DELETE_WINDOW", self._close_app)

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"], relief="flat")
        style.configure("Card.TFrame", background=COLORS["panel_alt"], relief="flat")
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=COLORS["teal_dark"], foreground="white", font=("Segoe UI Semibold", 21))
        style.configure("Subtitle.TLabel", background=COLORS["teal_dark"], foreground="#d7f4ef", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=("Segoe UI Semibold", 14))
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("Notebook.TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("Notebook.TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(16, 8), background=COLORS["cream"])
        style.map("Notebook.TNotebook.Tab", background=[("selected", COLORS["panel"])], foreground=[("selected", COLORS["teal_dark"])])
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10), background="white", fieldbackground="white", bordercolor=COLORS["border"])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=COLORS["cream"], foreground=COLORS["text"])

    def _configure_icon(self):
        if ICON_PNG_PATH.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH))
                self.iconphoto(True, self._icon_image)
            except tk.TclError:
                self._icon_image = None

        if ICON_ICO_PATH.exists():
            try:
                self.iconbitmap(default=str(ICON_ICO_PATH))
            except tk.TclError:
                pass

    def _build_layout(self):
        header = tk.Frame(self, bg=COLORS["teal_dark"], padx=28, pady=22)
        header.pack(fill="x")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        brand_frame = tk.Frame(header, bg=COLORS["teal_dark"])
        brand_frame.grid(row=0, column=0, sticky="w")
        ttk.Label(brand_frame, text="Stock Management", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            brand_frame,
            text="A desktop control center for products, sales, low-stock monitoring, and quick reports.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(6, 0))
        tk.Label(
            brand_frame,
            text="Powered by Idana Technologies and Projects PTY (LTD)",
            bg=COLORS["teal_dark"],
            fg="#c9ece7",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(8, 0))

        account_frame = tk.Frame(header, bg=COLORS["teal_dark"])
        account_frame.grid(row=0, column=1, sticky="ne", padx=(20, 0))
        tk.Label(
            account_frame,
            text=f"Signed in as: {self.current_user['username']} ({self.current_user['role']})",
            bg=COLORS["teal_dark"],
            fg="#f8fbfb",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="e", pady=(0, 8))
        account_actions = tk.Frame(account_frame, bg=COLORS["teal_dark"])
        account_actions.pack(anchor="e")
        tk.Button(
            account_actions,
            text="Change Password",
            command=self.open_change_password_dialog,
            bg=COLORS["cream"],
            fg=COLORS["text"],
            relief="flat",
            padx=14,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            account_actions,
            text="Log Out",
            command=self.logout,
            bg=COLORS["red"],
            fg="white",
            relief="flat",
            padx=14,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="left")

        stats_wrap = tk.Frame(self, bg=COLORS["bg"], padx=24, pady=18)
        stats_wrap.pack(fill="x")
        stats = [
            ("Products", "total_products"),
            ("Units In Stock", "total_units"),
            ("Inventory Value", "inventory_value"),
            ("Low Stock", "low_stock_count"),
            ("Sales", "sale_count"),
            ("Revenue", "revenue"),
        ]
        for index, (title, key) in enumerate(stats):
            card = tk.Frame(
                stats_wrap,
                bg=COLORS["panel"],
                padx=16,
                pady=14,
                highlightbackground=COLORS["border"],
                highlightthickness=1,
            )
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            stats_wrap.grid_columnconfigure(index, weight=1)
            tk.Label(card, text=title, bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
            label = tk.Label(card, text="0", bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 18))
            label.pack(anchor="w", pady=(8, 0))
            self.summary_labels[key] = label

        notebook = ttk.Notebook(self, style="Notebook.TNotebook")
        notebook.pack(fill="both", expand=True, padx=24, pady=(0, 18))

        inventory_tab = ttk.Frame(notebook, style="App.TFrame")
        reports_tab = ttk.Frame(notebook, style="App.TFrame")
        notebook.add(inventory_tab, text="Inventory")
        notebook.add(reports_tab, text="Sales & Reports")

        self._build_inventory_tab(inventory_tab)
        self._build_reports_tab(reports_tab)

        footer = tk.Frame(self, bg=COLORS["cream"], padx=24, pady=10)
        footer.pack(fill="x")
        tk.Label(footer, textvariable=self.status_var, bg=COLORS["cream"], fg=COLORS["muted"], font=("Segoe UI", 10)).pack(anchor="w")

    def _build_inventory_tab(self, parent):
        parent.grid_columnconfigure(0, weight=3)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        main_panel = tk.Frame(parent, bg=COLORS["panel"], padx=18, pady=18, highlightbackground=COLORS["border"], highlightthickness=1)
        main_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=10)
        main_panel.grid_rowconfigure(3, weight=1)
        main_panel.grid_columnconfigure(0, weight=1)

        toolbar = tk.Frame(main_panel, bg=COLORS["panel"])
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        toolbar.grid_columnconfigure(0, weight=1)

        search_row = tk.Frame(toolbar, bg=COLORS["panel"])
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        barcode_row = tk.Frame(toolbar, bg=COLORS["panel"])
        barcode_row.grid(row=1, column=0, sticky="ew")
        for index in range(3):
            barcode_row.grid_columnconfigure(index, weight=1)

        tk.Entry(
            search_row,
            textvariable=self.search_var,
            font=("Segoe UI", 10),
            width=30,
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        ).pack(side="left", padx=(0, 8), ipady=6)
        self._button(search_row, "Search", self.refresh_all, COLORS["teal"]).pack(side="left", padx=(0, 8))
        self._button(search_row, "Clear", self.clear_search, COLORS["cream"], fg=COLORS["text"]).pack(side="left", padx=(0, 8))
        self.add_button = self._button(search_row, "Add Product", self.open_add_dialog, COLORS["gold"])
        self.add_button.pack(side="right")

        barcode_entry = tk.Entry(
            barcode_row,
            textvariable=self.barcode_var,
            font=("Segoe UI", 10),
            width=22,
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        barcode_entry.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8), ipady=6)
        barcode_entry.bind("<Return>", lambda event: self.find_by_barcode())
        self._button(barcode_row, "Find Barcode", self.find_by_barcode, COLORS["teal_dark"]).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self._button(barcode_row, "Scan Sale", self.scan_sale_by_barcode, COLORS["blue"]).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        self._button(barcode_row, "Phone Scanner", self.show_phone_scanner_info, COLORS["teal"]).grid(row=1, column=2, sticky="ew")

        tk.Label(main_panel, text="Inventory Table", bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 14)).grid(row=1, column=0, sticky="w")
        tk.Label(main_panel, text="View current stock, identify shortages, and manage products quickly.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=(4, 14))

        columns = ("id", "name", "sku", "barcode", "category", "price", "quantity", "supplier", "status")
        table_frame = tk.Frame(main_panel, bg=COLORS["panel"])
        table_frame.grid(row=3, column=0, sticky="nsew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headers = {
            "id": "ID",
            "name": "Name",
            "sku": "SKU",
            "barcode": "Barcode",
            "category": "Category",
            "price": "Price",
            "quantity": "Qty",
            "supplier": "Supplier",
            "status": "Status",
        }
        widths = {
            "id": 50,
            "name": 210,
            "sku": 110,
            "barcode": 130,
            "category": 130,
            "price": 95,
            "quantity": 70,
            "supplier": 160,
            "status": 120,
        }
        for column in columns:
            self.tree.heading(column, text=headers[column])
            self.tree.column(column, width=widths[column], anchor="w")

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        actions = tk.Frame(main_panel, bg=COLORS["panel"])
        actions.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        for index in range(2):
            actions.grid_columnconfigure(index, weight=1)

        self.edit_button = self._button(actions, "Edit Selected", self.open_edit_dialog, COLORS["teal"])
        self.edit_button.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        self._button(actions, "Adjust Stock", self.open_adjust_dialog, COLORS["blue"]).grid(row=0, column=1, sticky="ew", pady=(0, 8))
        self._button(actions, "Record Sale", self.open_sale_dialog, COLORS["gold"]).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.delete_button = self._button(actions, "Delete Selected", self.delete_selected, COLORS["red"])
        self.delete_button.grid(row=1, column=1, sticky="ew")

        side_panel = tk.Frame(parent, bg=COLORS["panel"], padx=18, pady=18, highlightbackground=COLORS["border"], highlightthickness=1)
        side_panel.grid(row=0, column=1, sticky="nsew", pady=10)

        tk.Label(side_panel, text="Low Stock Alerts", bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 14)).pack(anchor="w")
        tk.Label(side_panel, text="Items at or below their minimum stock level.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 12))

        self.low_stock_list = tk.Listbox(
            side_panel,
            font=("Segoe UI", 10),
            bd=0,
            highlightthickness=0,
            activestyle="none",
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            selectbackground=COLORS["cream"],
        )
        self.low_stock_list.pack(fill="both", expand=True)

    def _build_reports_tab(self, parent):
        parent.grid_columnconfigure(0, weight=2)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        sales_panel = tk.Frame(parent, bg=COLORS["panel"], padx=18, pady=18, highlightbackground=COLORS["border"], highlightthickness=1)
        sales_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=10)
        sales_panel.grid_columnconfigure(0, weight=1)
        sales_panel.grid_rowconfigure(1, weight=1)

        tk.Label(sales_panel, text="Sales History", bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 14)).grid(row=0, column=0, sticky="w")
        tk.Label(sales_panel, text="Track individual sales and review totals by day.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(4, 12))

        sales_notebook = ttk.Notebook(sales_panel, style="Notebook.TNotebook")
        sales_notebook.grid(row=2, column=0, sticky="nsew")

        history_tab = ttk.Frame(sales_notebook, style="App.TFrame")
        daily_tab = ttk.Frame(sales_notebook, style="App.TFrame")
        sales_notebook.add(history_tab, text="Sales History")
        sales_notebook.add(daily_tab, text="Daily Sales")

        history_tab.grid_columnconfigure(0, weight=1)
        history_tab.grid_rowconfigure(1, weight=1)

        sales_search_row = tk.Frame(history_tab, bg=COLORS["panel"])
        sales_search_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        tk.Entry(
            sales_search_row,
            textvariable=self.sales_search_var,
            font=("Segoe UI", 10),
            width=34,
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        ).pack(side="left", padx=(0, 8), ipady=6)
        self._button(sales_search_row, "Search Sales", self._refresh_sales, COLORS["teal"]).pack(side="left", padx=(0, 8))
        self._button(sales_search_row, "Clear", self.clear_sales_search, COLORS["cream"], fg=COLORS["text"]).pack(side="left")

        sales_columns = ("sold_at", "product_name", "quantity", "unit_price", "total_amount", "customer_name")
        sales_table_frame = tk.Frame(history_tab, bg=COLORS["panel"])
        sales_table_frame.grid(row=1, column=0, sticky="nsew")
        sales_table_frame.grid_rowconfigure(0, weight=1)
        sales_table_frame.grid_columnconfigure(0, weight=1)

        self.sales_tree = ttk.Treeview(sales_table_frame, columns=sales_columns, show="headings", selectmode="browse")
        sales_headers = {
            "sold_at": "Date",
            "product_name": "Product",
            "quantity": "Qty",
            "unit_price": "Unit Price",
            "total_amount": "Total",
            "customer_name": "Customer",
        }
        sales_widths = {
            "sold_at": 150,
            "product_name": 220,
            "quantity": 70,
            "unit_price": 95,
            "total_amount": 95,
            "customer_name": 160,
        }
        for column in sales_columns:
            self.sales_tree.heading(column, text=sales_headers[column])
            self.sales_tree.column(column, width=sales_widths[column], anchor="w")

        sales_y_scroll = ttk.Scrollbar(sales_table_frame, orient="vertical", command=self.sales_tree.yview)
        sales_x_scroll = ttk.Scrollbar(sales_table_frame, orient="horizontal", command=self.sales_tree.xview)
        self.sales_tree.configure(yscrollcommand=sales_y_scroll.set, xscrollcommand=sales_x_scroll.set)

        self.sales_tree.grid(row=0, column=0, sticky="nsew")
        sales_y_scroll.grid(row=0, column=1, sticky="ns")
        sales_x_scroll.grid(row=1, column=0, sticky="ew")

        daily_tab.grid_columnconfigure(0, weight=1)
        daily_tab.grid_rowconfigure(1, weight=1)
        tk.Label(daily_tab, text="View sales totals grouped by day.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=(0, 12))

        daily_table_frame = tk.Frame(daily_tab, bg=COLORS["panel"])
        daily_table_frame.grid(row=1, column=0, sticky="nsew")
        daily_table_frame.grid_rowconfigure(0, weight=1)
        daily_table_frame.grid_columnconfigure(0, weight=1)

        daily_columns = ("sale_date", "sale_count", "units_sold", "revenue")
        self.daily_sales_tree = ttk.Treeview(daily_table_frame, columns=daily_columns, show="headings", selectmode="browse")
        daily_headers = {
            "sale_date": "Date",
            "sale_count": "Sales",
            "units_sold": "Units Sold",
            "revenue": "Revenue",
        }
        daily_widths = {
            "sale_date": 140,
            "sale_count": 90,
            "units_sold": 110,
            "revenue": 120,
        }
        for column in daily_columns:
            self.daily_sales_tree.heading(column, text=daily_headers[column])
            self.daily_sales_tree.column(column, width=daily_widths[column], anchor="w")

        daily_y_scroll = ttk.Scrollbar(daily_table_frame, orient="vertical", command=self.daily_sales_tree.yview)
        self.daily_sales_tree.configure(yscrollcommand=daily_y_scroll.set)
        self.daily_sales_tree.grid(row=0, column=0, sticky="nsew")
        daily_y_scroll.grid(row=0, column=1, sticky="ns")

        side_panel = tk.Frame(parent, bg=COLORS["panel"], padx=18, pady=18, highlightbackground=COLORS["border"], highlightthickness=1)
        side_panel.grid(row=0, column=1, sticky="nsew", pady=10)
        side_panel.grid_rowconfigure(0, weight=1)
        side_panel.grid_columnconfigure(0, weight=1)

        report_canvas = tk.Canvas(side_panel, bg=COLORS["panel"], highlightthickness=0, bd=0)
        report_scroll = ttk.Scrollbar(side_panel, orient="vertical", command=report_canvas.yview)
        report_content = tk.Frame(report_canvas, bg=COLORS["panel"])

        report_content.bind(
            "<Configure>",
            lambda event: report_canvas.configure(scrollregion=report_canvas.bbox("all")),
        )

        report_canvas.create_window((0, 0), window=report_content, anchor="nw")
        report_canvas.configure(yscrollcommand=report_scroll.set)

        report_canvas.grid(row=0, column=0, sticky="nsew")
        report_scroll.grid(row=0, column=1, sticky="ns")

        tk.Label(report_content, text="Reports", bg=COLORS["panel"], fg=COLORS["text"], font=("Segoe UI Semibold", 14)).pack(anchor="w")
        tk.Label(report_content, text="Export inventory or sales data as CSV reports.", bg=COLORS["panel"], fg=COLORS["muted"], font=("Segoe UI", 10), wraplength=260, justify="left").pack(anchor="w", pady=(4, 12))

        report_stats = [
            ("Total Sales", "sale_count"),
            ("Units Sold", "units_sold"),
            ("Revenue", "revenue"),
            ("Today's Sales", "today_sale_count"),
            ("Today's Revenue", "today_revenue"),
        ]
        for title, key in report_stats:
            box = tk.Frame(report_content, bg=COLORS["panel_alt"], padx=14, pady=12, highlightbackground=COLORS["border"], highlightthickness=1)
            box.pack(fill="x", pady=(0, 10))
            tk.Label(box, text=title, bg=COLORS["panel_alt"], fg=COLORS["muted"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
            value = tk.Label(box, text="0", bg=COLORS["panel_alt"], fg=COLORS["text"], font=("Segoe UI Semibold", 16))
            value.pack(anchor="w", pady=(6, 0))
            self.report_labels[key] = value

        buttons = tk.Frame(report_content, bg=COLORS["panel"])
        buttons.pack(fill="x", pady=(10, 0))
        self._button(buttons, "Export Inventory CSV", self.export_inventory_report, COLORS["teal"]).pack(fill="x", pady=(0, 8))
        self._button(buttons, "Export Sales CSV", self.export_sales_report, COLORS["blue"]).pack(fill="x", pady=(0, 8))
        self._button(buttons, "Open Last Receipt", self.open_last_receipt, COLORS["teal_dark"]).pack(fill="x", pady=(0, 8))
        self._button(buttons, "Print Last Receipt", self.print_last_receipt, COLORS["blue"]).pack(fill="x", pady=(0, 8))
        self._button(buttons, "Backup Database", self.backup_database_file, COLORS["gold"]).pack(fill="x", pady=(0, 8))
        self.restore_button = self._button(buttons, "Restore Database", self.restore_database_file, COLORS["red"])
        self.restore_button.pack(fill="x", pady=(0, 8))
        self._button(buttons, "Refresh Reports", self.refresh_all, COLORS["cream"], fg=COLORS["text"]).pack(fill="x")
        self._apply_role_permissions()

    def _button(self, master, text, command, bg, fg="white"):
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            relief="flat",
            activebackground=bg,
            activeforeground=fg,
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=8,
            cursor="hand2",
        )

    def _is_admin(self):
        return self.current_user["role"] == "admin"

    def _apply_role_permissions(self):
        admin_only = [self.add_button, self.edit_button, self.delete_button, self.restore_button]
        state = "normal" if self._is_admin() else "disabled"
        for widget in admin_only:
            if widget is not None:
                widget.config(state=state)

    def _require_admin(self, action_name):
        if self._is_admin():
            return True
        messagebox.showwarning("Admin only", f"{action_name} is available only to admin users.")
        return False

    def _poll_phone_scans(self):
        try:
            while True:
                payload = self.phone_scan_queue.get_nowait()
                self.barcode_var.set(payload["barcode"])
                if payload["action"] == "sale":
                    self.scan_sale_by_barcode()
                else:
                    self.find_by_barcode()
        except Empty:
            pass
        self.after(250, self._poll_phone_scans)

    def show_phone_scanner_info(self):
        url = self.phone_server.url()
        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo(
            "Phone Scanner",
            "Open this address on your phone while it is on the same Wi-Fi network:\n\n"
            f"{url}\n\n"
            "The link has also been copied to your clipboard.",
        )

    def _close_app(self):
        self.phone_server.stop()
        self.destroy()

    def open_change_password_dialog(self):
        ChangePasswordDialog(
            self,
            self.current_user["username"],
            self._change_password,
        )

    def _change_password(self, current_password, new_password):
        verified_user = self.db.authenticate_user(self.current_user["username"], current_password)
        if verified_user is None:
            raise ValueError("Current password is incorrect.")
        self.db.update_user_password(self.current_user["id"], new_password)

    def logout(self):
        confirmed = messagebox.askyesno("Log out", "Do you want to log out and return to the login screen?")
        if not confirmed:
            return
        self.phone_server.stop()
        self.destroy()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def clear_search(self):
        self.search_var.set("")
        self.barcode_var.set("")
        self.refresh_all()

    def clear_sales_search(self):
        self.sales_search_var.set("")
        self._refresh_sales()

    def refresh_all(self):
        self._refresh_products()
        self._refresh_sales()
        self._refresh_daily_sales()
        self._refresh_summaries()

    def _refresh_products(self):
        products = self.db.fetch_products(self.search_var.get())
        low_stock = self.db.low_stock_products()

        for item in self.tree.get_children():
            self.tree.delete(item)

        for product in products:
            status = self._status_text(product["quantity"], product["low_stock_limit"])
            self.tree.insert(
                "",
                "end",
                iid=str(product["id"]),
                values=(
                    product["id"],
                    product["name"],
                    product["sku"],
                    product["barcode"] or "-",
                    product["category"],
                    f"R {product['price']:.2f}",
                    product["quantity"],
                    product["supplier"] or "-",
                    status,
                ),
            )

        self.low_stock_list.delete(0, tk.END)
        if low_stock:
            for product in low_stock:
                self.low_stock_list.insert(
                    tk.END,
                    f"{product['name']} | {product['quantity']} left | min {product['low_stock_limit']}",
                )
        else:
            self.low_stock_list.insert(tk.END, "All products are above minimum stock.")

        self.status_var.set(f"Showing {len(products)} product(s)")

    def _refresh_sales(self):
        sales = self.db.fetch_sales(search=self.sales_search_var.get())
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)

        for sale in sales:
            self.sales_tree.insert(
                "",
                "end",
                iid=f"sale-{sale['id']}",
                values=(
                    sale["sold_at"],
                    sale["product_name"],
                    sale["quantity"],
                    f"R {sale['unit_price']:.2f}",
                    f"R {sale['total_amount']:.2f}",
                    sale["customer_name"] or "-",
                ),
            )

    def _refresh_daily_sales(self):
        daily_sales = self.db.fetch_daily_sales()
        for item in self.daily_sales_tree.get_children():
            self.daily_sales_tree.delete(item)

        for row in daily_sales:
            self.daily_sales_tree.insert(
                "",
                "end",
                iid=f"daily-{row['sale_date']}",
                values=(
                    row["sale_date"],
                    row["sale_count"],
                    row["units_sold"],
                    f"R {row['revenue']:.2f}",
                ),
            )

    def _refresh_summaries(self):
        summary = self.db.summary()
        self.summary_labels["total_products"].config(text=str(summary["total_products"]))
        self.summary_labels["total_units"].config(text=str(summary["total_units"]))
        self.summary_labels["inventory_value"].config(text=f"R {summary['inventory_value']:.2f}")
        self.summary_labels["low_stock_count"].config(text=str(summary["low_stock_count"]))
        self.summary_labels["sale_count"].config(text=str(summary["sale_count"]))
        self.summary_labels["revenue"].config(text=f"R {summary['revenue']:.2f}")

        self.report_labels["sale_count"].config(text=str(summary["sale_count"]))
        self.report_labels["units_sold"].config(text=str(summary["units_sold"]))
        self.report_labels["revenue"].config(text=f"R {summary['revenue']:.2f}")
        self.report_labels["today_sale_count"].config(text=str(summary["today_sale_count"]))
        self.report_labels["today_revenue"].config(text=f"R {summary['today_revenue']:.2f}")

    def _status_text(self, quantity, limit):
        if quantity == 0:
            return "Out of stock"
        if quantity <= limit:
            return "Low stock"
        return "Healthy"

    def _selected_product_id(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a product", "Please select a product first.")
            return None
        return int(selected[0])

    def _get_barcode_product(self):
        barcode = self.barcode_var.get().strip()
        if not barcode:
            messagebox.showinfo("Scan barcode", "Enter or scan a barcode first.")
            return None

        product = self.db.fetch_product_by_barcode(barcode)
        if product is None:
            messagebox.showerror("Barcode not found", f"No product was found for barcode:\n{barcode}")
            return None
        return product

    def find_by_barcode(self):
        product = self._get_barcode_product()
        if product is None:
            return

        self.search_var.set(product["barcode"] or "")
        self.refresh_all()
        item_id = str(product["id"])
        if self.tree.exists(item_id):
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self.tree.see(item_id)
        self.status_var.set(f"Found {product['name']} by barcode")

    def scan_sale_by_barcode(self):
        product = self._get_barcode_product()
        if product is None:
            return
        if product["quantity"] <= 0:
            messagebox.showerror("Out of stock", f"{product['name']} is out of stock.")
            return

        SaleDialog(
            self,
            product,
            lambda quantity, unit_price, customer_name, notes, create_receipt, print_receipt: self._save_sale(
                product["id"],
                product["name"],
                quantity,
                unit_price,
                customer_name,
                notes,
                create_receipt,
                print_receipt,
            ),
        )

    def open_add_dialog(self):
        if not self._require_admin("Adding products"):
            return
        ProductDialog(self, "Add Product", self._save_new_product)

    def _save_new_product(self, payload):
        self.db.create_product(payload)
        self.refresh_all()
        self.status_var.set(f"Added {payload['name']}")

    def open_edit_dialog(self):
        if not self._require_admin("Editing products"):
            return
        product_id = self._selected_product_id()
        if product_id is None:
            return
        product = self.db.fetch_product(product_id)
        if product is None:
            messagebox.showerror("Missing product", "That product could not be found.")
            return
        ProductDialog(
            self,
            "Edit Product",
            lambda payload: self._save_existing_product(product_id, payload),
            product=product,
        )

    def _save_existing_product(self, product_id, payload):
        self.db.update_product(product_id, payload)
        self.refresh_all()
        self.status_var.set(f"Updated {payload['name']}")

    def open_adjust_dialog(self):
        product_id = self._selected_product_id()
        if product_id is None:
            return
        product = self.db.fetch_product(product_id)
        if product is None:
            messagebox.showerror("Missing product", "That product could not be found.")
            return
        StockAdjustmentDialog(
            self,
            product["name"],
            lambda change: self._apply_stock_change(product_id, product["name"], change),
        )

    def _apply_stock_change(self, product_id, product_name, change):
        self.db.adjust_stock(product_id, change)
        self.refresh_all()
        action = "Added to" if change > 0 else "Removed from"
        self.status_var.set(f"{action} {product_name} stock")

    def open_sale_dialog(self):
        product_id = self._selected_product_id()
        if product_id is None:
            return
        product = self.db.fetch_product(product_id)
        if product is None:
            messagebox.showerror("Missing product", "That product could not be found.")
            return
        SaleDialog(
            self,
            product,
            lambda quantity, unit_price, customer_name, notes, create_receipt, print_receipt: self._save_sale(
                product_id, product["name"], quantity, unit_price, customer_name, notes, create_receipt, print_receipt
            ),
        )

    def _save_sale(self, product_id, product_name, quantity, unit_price, customer_name, notes, create_receipt, print_receipt):
        sale_data = self.db.record_sale(product_id, quantity, unit_price, customer_name, notes)
        receipt_path = None
        if create_receipt or print_receipt:
            receipt_path = self.create_receipt_file(sale_data)
            self.last_receipt_path = receipt_path
            if print_receipt:
                self._print_receipt(receipt_path)
        self.refresh_all()
        if receipt_path:
            self.status_var.set(f"Recorded sale for {product_name} and created receipt")
            messagebox.showinfo("Sale saved", f"Sale recorded.\nReceipt saved to:\n{receipt_path}")
        else:
            self.status_var.set(f"Recorded sale for {product_name}")

    def delete_selected(self):
        if not self._require_admin("Deleting products"):
            return
        product_id = self._selected_product_id()
        if product_id is None:
            return
        product = self.db.fetch_product(product_id)
        if product is None:
            messagebox.showerror("Missing product", "That product could not be found.")
            return
        confirmed = messagebox.askyesno("Delete product", f"Delete {product['name']} from stock?")
        if not confirmed:
            return
        self.db.delete_product(product_id)
        self.refresh_all()
        self.status_var.set(f"Deleted {product['name']}")

    def export_inventory_report(self):
        default_name = f"inventory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = filedialog.asksaveasfilename(
            title="Save inventory report",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not file_path:
            return
        self.db.export_inventory_csv(file_path)
        self.status_var.set(f"Inventory report exported to {Path(file_path).name}")
        messagebox.showinfo("Export complete", f"Inventory report saved to:\n{file_path}")

    def export_sales_report(self):
        default_name = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = filedialog.asksaveasfilename(
            title="Save sales report",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV files", "*.csv")],
        )
        if not file_path:
            return
        self.db.export_sales_csv(file_path)
        self.status_var.set(f"Sales report exported to {Path(file_path).name}")
        messagebox.showinfo("Export complete", f"Sales report saved to:\n{file_path}")

    def create_receipt_file(self, sale_data):
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.strptime(sale_data["sold_at"], "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in sale_data["product_name"])
        receipt_path = RECEIPTS_DIR / f"receipt_{timestamp}_{safe_name}.txt"

        receipt_text = "\n".join(
            [
                "STOCK MANAGEMENT APP RECEIPT",
                "Powered by Idana Technologies and Projects PTY (LTD)",
                "-" * 48,
                f"Receipt No: {sale_data['sale_id']}",
                f"Date: {sale_data['sold_at']}",
                f"Product: {sale_data['product_name']}",
                f"SKU: {sale_data['sku']}",
                f"Quantity: {sale_data['quantity']}",
                f"Unit Price: R {sale_data['unit_price']:.2f}",
                f"Total: R {sale_data['total_amount']:.2f}",
                f"Customer: {sale_data['customer_name'] or 'Walk-in Customer'}",
                f"Notes: {sale_data['notes'] or '-'}",
                "-" * 48,
                "Thank you for your business.",
            ]
        )

        receipt_path.write_text(receipt_text, encoding="utf-8")
        return receipt_path

    def _print_receipt(self, receipt_path):
        try:
            os.startfile(str(receipt_path), "print")
        except OSError as error:
            messagebox.showerror("Print failed", f"Could not print the receipt.\n{error}")

    def open_last_receipt(self):
        if not self.last_receipt_path or not Path(self.last_receipt_path).exists():
            messagebox.showinfo("No receipt", "No receipt has been created yet in this session.")
            return
        os.startfile(str(self.last_receipt_path))

    def print_last_receipt(self):
        if not self.last_receipt_path or not Path(self.last_receipt_path).exists():
            messagebox.showinfo("No receipt", "No receipt has been created yet in this session.")
            return
        self._print_receipt(self.last_receipt_path)

    def backup_database_file(self):
        default_name = f"inventory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        file_path = filedialog.asksaveasfilename(
            title="Save database backup",
            defaultextension=".db",
            initialfile=default_name,
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
        )
        if not file_path:
            return

        self.db.backup_database(file_path)
        self.status_var.set(f"Database backup saved as {Path(file_path).name}")
        messagebox.showinfo("Backup complete", f"Database backup saved to:\n{file_path}")

    def restore_database_file(self):
        if not self._require_admin("Restoring the database"):
            return
        file_path = filedialog.askopenfilename(
            title="Select database backup to restore",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
        )
        if not file_path:
            return

        confirmed = messagebox.askyesno(
            "Restore database",
            "Restoring a backup will replace the current inventory and sales data. Continue?",
        )
        if not confirmed:
            return

        try:
            self.db.restore_database(file_path)
            self.refresh_all()
            self.status_var.set(f"Restored database from {Path(file_path).name}")
            messagebox.showinfo("Restore complete", f"Database restored from:\n{file_path}")
        except Exception as error:
            messagebox.showerror("Restore failed", str(error))


if __name__ == "__main__":
    app = StockManagementApp()
    app.mainloop()
