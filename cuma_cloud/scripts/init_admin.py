import asyncio
import os
import sys

# Add the root directory to Python path to ensure imports work
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy.future import select

from cuma_cloud.core.database import async_sessionmaker_factory
from cuma_cloud.core.security import get_password_hash
from cuma_cloud.models import User, RoleEnum

async def init_admin():
    async with async_sessionmaker_factory() as session:
        result = await session.execute(select(User).where(User.email == "admin@cuma.com"))
        admin = result.scalars().first()
        
        # Use the system's existing hash function
        hashed_pw = get_password_hash("cuma123")
        
        if admin:
            print("Found existing admin account. Force resetting password and role...")
            admin.hashed_password = hashed_pw
            admin.role = RoleEnum.QCQ_ADMIN
            # If your model adds is_active in the future, uncomment below:
            # admin.is_active = True
        else:
            print("Creating new admin account...")
            admin = User(
                email="admin@cuma.com",
                hashed_password=hashed_pw,
                role=RoleEnum.QCQ_ADMIN,
                # is_active=True # (is_active not found in User model based on current schema)
            )
            session.add(admin)
            
        await session.commit()
        print("\n✅ Success! The admin account is initialized:")
        print("👉 Email: admin@cuma.com")
        print("👉 Password: cuma123")

if __name__ == "__main__":
    asyncio.run(init_admin())
