# This is the modified content of main.py with replacements

async def some_func():
    # Original bot.loop.create_task usage
    task = asyncio.create_task(some_coroutine())
    return task