import sqlite3
import os
from datetime import datetime
import config

DATABASE = config.DATABASE

def ensure_db_dir(db_path: str):
    """Safely ensures the parent directory for the SQLite database exists."""
    if not db_path or db_path == ":memory:":
        return
    try:
        dir_name = os.path.dirname(os.path.abspath(db_path))
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create directory for database '{db_path}': {e}")

def get_db_connection():
    # Resolves dynamically to allow test monkeypatching of database.DATABASE or config.DATABASE
    db_path = globals().get('DATABASE') or getattr(config, 'DATABASE', 'lost_found.db')
    ensure_db_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Safely upgrades database schema without dropping existing items."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Ensure items table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        cursor.execute('''
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL, -- 'lost' or 'found'
                item_name TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                description TEXT,
                color TEXT,
                brand TEXT,
                distinctive_features TEXT,
                location TEXT,
                item_date TEXT,
                status TEXT DEFAULT 'active', -- 'active', 'resolved'
                student_name TEXT NOT NULL,
                registration_number TEXT NOT NULL,
                contact_number TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                department TEXT,
                year_of_study TEXT,
                reported_at TEXT NOT NULL
            )
        ''')
    else:
        # Check existing columns and run safe migrations
        cursor.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        column_defs = {
            "category": "TEXT DEFAULT 'Other'",
            "color": "TEXT",
            "brand": "TEXT",
            "distinctive_features": "TEXT",
            "item_date": "TEXT",
            "status": "TEXT DEFAULT 'active'"
        }
        
        for col, col_type in column_defs.items():
            if col not in columns:
                cursor.execute(f"ALTER TABLE items ADD COLUMN {col} {col_type}")

    # 2. Create matches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lost_item_id INTEGER NOT NULL,
            found_item_id INTEGER NOT NULL,
            similarity_score REAL NOT NULL,
            match_confidence TEXT NOT NULL, -- 'Strong potential match', 'Possible match', 'Low similarity'
            explanation TEXT,
            matching_evidence TEXT,
            status TEXT DEFAULT 'pending', -- 'pending', 'dismissed', 'resolved'
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(lost_item_id, found_item_id),
            FOREIGN KEY(lost_item_id) REFERENCES items(id) ON DELETE CASCADE,
            FOREIGN KEY(found_item_id) REFERENCES items(id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Create claims table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            match_id INTEGER,
            claimant_name TEXT NOT NULL,
            claimant_contact TEXT NOT NULL,
            claimant_email TEXT NOT NULL,
            verification_details TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE
        )
    ''')

    # 4. Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_type_status ON items(type, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_pairs ON matches(lost_item_id, found_item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status)")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized/migrated successfully!")
