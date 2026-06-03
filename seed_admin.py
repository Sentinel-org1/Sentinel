#!/usr/bin/env python
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from passlib.context import CryptContext

# Password hashing context (matching backend)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_admin():
    # Import models after ensuring DB connection
    from app.models.user import User
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not set")
        return
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Check if admin exists
            stmt = select(User).where(User.email == "admin@sentinel.ai")
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print("✓ Admin user already exists")
            else:
                admin = User(
                    email="admin@sentinel.ai",
                    hashed_password=pwd_context.hash("admin123"),
                    is_active=True,
                    is_superuser=True
                )
                session.add(admin)
                await session.commit()
                print("✓ Admin user created: admin@sentinel.ai / admin123")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_admin())
