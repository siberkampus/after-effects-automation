# test_mcp.py
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# MCP Sunucumuzun yolu
SERVER_SCRIPT = r"C:\Users\ACER\Documents\ae-motion\dist\index.js"

async def main():
    print("MCP Sunucusuna bağlanılıyor...")
    
    # Node.js sunucusunu başlatmak için parametreler
    server_params = StdioServerParameters(
        command="node",
        args=[SERVER_SCRIPT],
        env={**os.environ, "AE_MCP_ALLOW_JSX": "1"} # JSX çalıştırma iznini veriyoruz
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Bağlantıyı başlat
                await session.initialize()
                print("BAĞLANTI BAŞARILI!\n")

                # Mevcut araçları listele
                tools = await session.list_tools()
                print(f"Kullanılabilir Araç Sayısı: {len(tools.tools)}")
                print("İlk 5 Araç:")
                for tool in tools.tools[:5]:
                    print(f" - {tool.name}: {tool.description[:60]}...")
                
                print("\nAfter Effects'ten Proje Bilgisi İsteniyor...")
                # Örnek bir araç çağrısı (Proje bilgilerini al)
                result = await session.call_tool("get_project", arguments={})
                
                for content in result.content:
                    print("\nAE'den Gelen Cevap:")
                    print(content.text)

    except Exception as e:
        print(f"\nBağlantı Hatası: {e}")

if __name__ == "__main__":
    asyncio.run(main())