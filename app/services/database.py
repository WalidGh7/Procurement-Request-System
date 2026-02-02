import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "procurement.db"


def get_connection():
    """Get a database connection"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_database():
    """Initialize database tables"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Document extraction cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_cache (
                file_hash TEXT PRIMARY KEY,
                filename TEXT,
                extracted_data TEXT,
                created_at TEXT
            )
        """)

        # Procurement requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procurement_requests (
                id TEXT PRIMARY KEY,
                requestor_name TEXT,
                title TEXT,
                vendor_name TEXT,
                vat_id TEXT,
                commodity_group_id TEXT,
                total_cost REAL,
                department TEXT,
                status TEXT DEFAULT 'Open',
                created_at TEXT
            )
        """)

        # Order lines table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                description TEXT,
                unit_price REAL,
                amount INTEGER,
                unit TEXT,
                total_price REAL,
                FOREIGN KEY (request_id) REFERENCES procurement_requests(id)
            )
        """)

        # Status history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                status TEXT,
                timestamp TEXT,
                FOREIGN KEY (request_id) REFERENCES procurement_requests(id)
            )
        """)


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content"""
    return hashlib.sha256(content).hexdigest()


# Document cache functions
def get_cached_extraction(file_hash: str) -> dict | None:
    """Get cached extraction result by file hash"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT extracted_data FROM document_cache WHERE file_hash = ?",
            (file_hash,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["extracted_data"])
        return None


def cache_extraction(file_hash: str, filename: str, extracted_data: dict):
    """Cache extraction result"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO document_cache (file_hash, filename, extracted_data, created_at)
               VALUES (?, ?, ?, ?)""",
            (file_hash, filename, json.dumps(extracted_data), datetime.now().isoformat())
        )


# Request counter management
def get_next_request_id() -> str:
    """Get next request ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM procurement_requests")
        count = cursor.fetchone()["count"]
        return f"REQ-{count + 1:04d}"


# Procurement request functions
def create_request(request_data: dict) -> dict:
    """Create a new procurement request"""
    request_id = get_next_request_id()
    created_at = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()

        # Insert main request
        cursor.execute(
            """INSERT INTO procurement_requests
               (id, requestor_name, title, vendor_name, vat_id, commodity_group_id, total_cost, department, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id,
                request_data["requestor_name"],
                request_data["title"],
                request_data["vendor_name"],
                request_data["vat_id"],
                request_data["commodity_group_id"],
                request_data["total_cost"],
                request_data["department"],
                "Open",
                created_at
            )
        )

        # Insert order lines
        for line in request_data["order_lines"]:
            cursor.execute(
                """INSERT INTO order_lines (request_id, description, unit_price, amount, unit, total_price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (request_id, line["description"], line["unit_price"], line["amount"], line["unit"], line["total_price"])
            )

        # Insert initial status history
        cursor.execute(
            "INSERT INTO status_history (request_id, status, timestamp) VALUES (?, ?, ?)",
            (request_id, "Open", created_at)
        )

    return get_request(request_id)


def get_request(request_id: str) -> dict | None:
    """Get a specific procurement request"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get main request
        cursor.execute("SELECT * FROM procurement_requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        if not row:
            return None

        # Get order lines
        cursor.execute("SELECT * FROM order_lines WHERE request_id = ?", (request_id,))
        order_lines = [
            {
                "description": line["description"],
                "unit_price": line["unit_price"],
                "amount": line["amount"],
                "unit": line["unit"],
                "total_price": line["total_price"]
            }
            for line in cursor.fetchall()
        ]

        # Get status history
        cursor.execute(
            "SELECT status, timestamp FROM status_history WHERE request_id = ? ORDER BY id",
            (request_id,)
        )
        status_history = [{"status": h["status"], "timestamp": h["timestamp"]} for h in cursor.fetchall()]

        return {
            "id": row["id"],
            "data": {
                "requestor_name": row["requestor_name"],
                "title": row["title"],
                "vendor_name": row["vendor_name"],
                "vat_id": row["vat_id"],
                "commodity_group_id": row["commodity_group_id"],
                "order_lines": order_lines,
                "total_cost": row["total_cost"],
                "department": row["department"]
            },
            "status": row["status"],
            "status_history": status_history,
            "created_at": row["created_at"]
        }


def get_all_requests() -> list[dict]:
    """Get all procurement requests"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM procurement_requests ORDER BY created_at DESC")
        request_ids = [row["id"] for row in cursor.fetchall()]

    return [get_request(rid) for rid in request_ids]


def update_request_status(request_id: str, status: str) -> dict | None:
    """Update the status of a procurement request"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if request exists
        cursor.execute("SELECT id FROM procurement_requests WHERE id = ?", (request_id,))
        if not cursor.fetchone():
            return None

        # Update status
        cursor.execute(
            "UPDATE procurement_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )

        # Add to status history
        cursor.execute(
            "INSERT INTO status_history (request_id, status, timestamp) VALUES (?, ?, ?)",
            (request_id, status, datetime.now().isoformat())
        )

    return get_request(request_id)
