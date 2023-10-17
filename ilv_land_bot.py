import os
import requests
import time
import pandas as pd
import json
from pyilz.get_plots import get_plot_metadata
from discord import Webhook, Embed, File
import aiohttp
import asyncio
from cairosvg import svg2png
from dotenv import load_dotenv
import helpers
load_dotenv()

watched_plots = [
    (756,422),
    (614,472),
    (540,314),
    (760,286),
    (184,203),
    (756,422),
    (152,368),
    (668,358),
    (152,368),
]

discord_webook =  os.getenv('DISCORD_WEBHOOK_URL')
debug = os.getenv('DEBUG') == 'True'

usdc_conversion = helpers.get_usdc_price()
if debug: print('USDC-ETH conversion', usdc_conversion)
aud_conversion = helpers.get_aud_price()
if debug: print('ETH-AUD conversion', aud_conversion)

def get_illuvium_name(wallet):
    try:
        url = f'https://api.illuvium-game.io/gamedata/illuvitars/album/query?wallet={wallet}'
        response = requests.get(url)
        json = response.json()
        name = json['name']
    except Exception as e:
        name = ''
    return name


async def send_message(row, tokentrove_data):
    asset_id = row['asset_id']
    meta = get_plot_metadata(row['asset_id'])
    plot_name = row["name"]
    svg = meta['imageUrl'].replace('/game/','/illuvidex/')
    url = row['url']
    eth = row['eth']
    erc20 = row['erc20']
    aud = row['aud']
    tier = meta['tier']
    user = row['user']
    user_name = get_illuvium_name(user)
    balanced_element = helpers.is_balanced_elements(meta)
    balanced_fuel = helpers.is_balanced_fuel(meta)

    tier_floor_price = helpers.get_floor(tokentrove_data, int(meta['tier']))
    less_than_floor = row['eth'] < tier_floor_price
    
    x = row['x']
    y = row['y']
    timestamp = row['updated_timestamp']

    neighbouring = helpers.is_neighbour(int(x), int(y), watched_plots)
    svg_code = requests.get(svg).content
    name = svg.split('/')[-1].split('.')[0]
    svg2png(bytestring=svg_code,write_to=f'{name}.png')
    async with aiohttp.ClientSession() as session:
        file = File(f"{name}.png", filename=f'{name}.png')
        colour = 0x0099FF
        title = "New IMX Listing"
        
        if neighbouring:
            colour = 0xFF0000
            title = "Neighbouring Plot for Sale" 
        else:
            if tier == 1:
                if balanced_element:
                    colour = 0x00FF00
                    title = "Balanced Plot for Sale!"
            else:
                if balanced_element and balanced_fuel:
                    colour = 0x00FF00
                    title = "Balanced Plot for Sale!"

        embed = Embed(title=title, url=url, description=plot_name, color=colour, timestamp=timestamp)
        embed.set_image(url=f"attachment://{name}.png")
        if erc20 > 0:
            embed.add_field(name="USDC", value=erc20, inline=True)
        if eth > 0:
            embed.add_field(name="ETH", value=f"{eth:.6f}", inline=True)
        embed.add_field(name="AUD", value=f"${aud:.2f}", inline=True)
        embed.add_field(name="Balanced Elements", value=balanced_element, inline=False)
        if tier > 1:
            embed.add_field(name="Balanced Fuel", value=balanced_fuel, inline=False)
        embed.add_field(name=f"Less than Floor ({tier_floor_price:.4f} ETH)", value=less_than_floor, inline=True)
        embed.add_field(name=f"Listing User", value=f'[{user_name}](https://illuvidex.illuvium.io/ranger/{user_name})', inline=False)
        try:
            import_url = helpers.get_import_url(asset_id)
            embed.add_field(name="Simulator Link", value=f"[View Plot]({import_url})", inline=False)
        except Exception as e:
            print('Failed to generate simulator link')

        webhook = Webhook.from_url(discord_webook, session=session)
        await webhook.send(embed=embed, file=file)
    os.remove(f"{name}.png")


if __name__ == '__main__':
    tokentrove_data = helpers.load_tokentrove()
    delay = 60
    if not debug: last_timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - delay))
    else: last_timestamp = '2023-10-01T00:00:00Z'
    while True:
        try:
            if debug: print(f'Looking for new listings since {last_timestamp}')
            df = helpers.load_imx(last_timestamp, usdc_conversion, aud_conversion)
            if len(df) > 0:
                print(f'Found {len(df)} new listings')
                for index, row in df.iterrows():
                    if not debug: asyncio.run(send_message(row, tokentrove_data))
                    else: print(row)
                max_timestamp = df['updated_timestamp'].max()
                max_timestamp += pd.Timedelta(seconds=1)
                last_timestamp = max_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
                if debug: print('Updated timestamp to', last_timestamp)
            else:
                if debug: print('No new listings')
                pass
        except Exception as e:
            print(e)
        if debug: print(f'Sleeping for {delay} seconds')
        time.sleep(delay)
