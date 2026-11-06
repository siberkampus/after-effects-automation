# list_tools.py
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = r"C:\Users\ACER\Documents\ae-motion\dist\index.js"

async def main():
    server_params = StdioServerParameters(
        command="node",
        args=[SERVER_SCRIPT],
        env={**os.environ, "AE_MCP_ALLOW_JSX": "1"}
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("=== KULLANILABİLİR ARAÇLAR ===")
            for t in tools.tools:
                print(f"- {t.name}")
                
if __name__ == "__main__":
    asyncio.run(main())