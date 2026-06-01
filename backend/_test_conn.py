import asyncio
import asyncpg

async def test():
    try:
        conn = await asyncpg.connect('postgresql://sentinel:sentinel@localhost:5433/sentinel')
        print('Connected OK!')
        row = await conn.fetchrow('SELECT 1 as ok')
        print(f'Query result: {row}')
        await conn.close()
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

asyncio.run(test())
