import asyncio
import aiohttp

async def upload():
    with open('runtime/domainpacks/ACME_CAPITAL/CapitalMarketsTrading/1.0.0.json', 'r') as f:
        file_data = f.read()
    
    data = aiohttp.FormData()
    data.add_field('file', file_data, filename='capitalmarkets.json', content_type='application/json')
    data.add_field('version', '1.1.0')
    
    async with aiohttp.ClientSession() as session:
        url = 'http://localhost:8000/admin/domainpacks/ACME_CAPITAL'
        headers = {'x-api-key': 'demo_acme_capital'}
        
        async with session.post(url, data=data, headers=headers) as resp:
            result = await resp.text()
            print(f'Status: {resp.status}')
            if resp.status == 200:
                print('Success! Playbooks extracted to database.')
            else:
                print(f'Response: {result[:500]}')

asyncio.run(upload())
