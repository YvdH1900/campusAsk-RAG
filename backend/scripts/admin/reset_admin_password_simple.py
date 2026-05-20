"""
管理员密码重置脚本 - 简化版
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import SessionLocal
from app.models import User
from app.core.security import get_password_hash

def reset_admin(password):
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            admin.hashed_password = get_password_hash(password)
            db.commit()
            print("SUCCESS: Password reset to: " + password)
        else:
            print("ERROR: Admin not found")
    finally:
        db.close()

if __name__ == "__main__":
    new_password = os.environ.get("NEW_ADMIN_PASSWORD")
    if not new_password:
        print("ERROR: Please set NEW_ADMIN_PASSWORD environment variable")
        sys.exit(1)
    reset_admin(new_password)