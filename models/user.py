import hashlib
import datetime

class User:
    def __init__(self, username, id=None, created_at=None):
        self.id = id
        self.username = username
        self.password_hash = None
        self.created_at = created_at or datetime.datetime.now()

    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def create_table(conn):
        cursor = conn.cursor()
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
            CREATE TABLE users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                username NVARCHAR(50) NOT NULL UNIQUE,
                password_hash NVARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL
            )
        """)
        conn.commit()

    def save(self, conn):
        cursor = conn.cursor()
        if self.id:
            cursor.execute("""
                UPDATE users 
                SET username = ?, password_hash = ?
                WHERE id = ?
            """, (self.username, self.password_hash, self.id))
        else:
            cursor.execute("""
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
            """, (self.username, self.password_hash, self.created_at))
            self.id = cursor.execute("SELECT @@IDENTITY").fetchone()[0]
        conn.commit()

    @staticmethod
    def get_by_id(conn, user_id):
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            user = User(username=row[1], id=row[0], created_at=row[3])
            user.password_hash = row[2]
            return user
        return None

    @staticmethod
    def get_by_username(conn, username):
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, created_at FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            user = User(username=row[1], id=row[0], created_at=row[3])
            user.password_hash = row[2]
            return user
        return None 