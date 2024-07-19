import json
import requests
import pandas as pd
from pyilz.get_plots import get_plot_metadata
from urllib.parse import quote


def is_balanced_fuel(metadata):
    tier = metadata['tier']
    s = metadata['solon']
    cr = metadata['crypton']
    hy = metadata['hyperion']
    if tier == 1:
        return False
    if s == 0 or cr == 0 or hy == 0:
        return False
    if s == cr == hy:
        return True
    return False


def is_balanced_elements(metadata):
    c = metadata['carbon']
    si = metadata['silicon']
    h = metadata['hydrogen']
    if c == 0 or si == 0 or h == 0:
        return False
    if c == si == h:
        return True
    return False


def is_neighbour(x, y, plots):
    for plot in plots:
        if abs(plot[0] - x) <= 1 and abs(plot[1] - y) <= 1:
            return True
    return False


# def get_usdc_price():
#     response = requests.get(
#         'https://api.coingecko.com/api/v3/simple/price?ids=usd-coin&vs_currencies=eth').json()
#     usdc_conversion = float(response['usd-coin']['eth'])
#     return usdc_conversion


def get_usdc_price():
    response = requests.get(
        'https://api.coinbase.com/v2/prices/usdc-eth/spot').json()
    usdc_conversion = float(response['data']['amount'])
    return usdc_conversion

# def get_aud_price():
#     response = requests.get(
#         'https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=aud').json()
#     aud_conversion = float(response['ethereum']['aud'])
#     return aud_conversion


def get_aud_price():
    response = requests.get(
        'https://api.coinbase.com/v2/prices/eth-aud/spot').json()
    aud_conversion = float(response['data']['amount'])
    return aud_conversion


def usdc_to_eth(usdc_amount, usdc_conversion):
    return usdc_amount * usdc_conversion


def eth_to_aud(eth, aud_conversion):
    return eth * aud_conversion


def load_imx_erc20(timestamp, usdc_conversion, aud_conversion):
    url = f'https://api.x.immutable.com/v3/orders?sell_token_address=0x9e0d99b864e1ac12565125c5a82b59adea5a09cd&buy_token_type=ERC20&include_fees=true&status=active&order_by=updated_at&min_timestamp={timestamp}'
    response = requests.get(url, timeout=5).json()
    df = pd.DataFrame(response['result'])
    if len(df) == 0:
        return df
    df['data'] = df['sell'].apply(lambda x: x['data'])
    df['buy_data'] = df['buy'].apply(lambda x: x['data'])
    df['decimals'] = df['buy_data'].apply(lambda x: x['decimals'])
    df['erc20'] = df['buy_data'].apply(
        lambda x: int(x['quantity_with_fees'])/1e6)
    df['eth'] = df['erc20'].apply(
        lambda x: usdc_to_eth(x, usdc_conversion) if x > 0 else 0)
    df['aud'] = df['eth'].apply(lambda x: eth_to_aud(
        x, aud_conversion) if x > 0 else 0)
    return df


def load_imx_eth(timestamp, aud_conversion):
    url = f'https://api.x.immutable.com/v3/orders?sell_token_address=0x9e0d99b864e1ac12565125c5a82b59adea5a09cd&buy_token_type=ETH&include_fees=true&status=active&order_by=updated_at&min_timestamp={timestamp}'
    response = requests.get(url, timeout=5).json()
    df = pd.DataFrame(response['result'])
    if len(df) == 0:
        return df
    df['data'] = df['sell'].apply(lambda x: x['data'])
    df['buy_data'] = df['buy'].apply(lambda x: x['data'])
    df['decimals'] = df['buy_data'].apply(lambda x: x['decimals'])
    df['eth'] = df['buy_data'].apply(
        lambda x: int(x['quantity_with_fees'])/1e18)
    df['erc20'] = 0
    df['aud'] = df['eth'].apply(lambda x: eth_to_aud(
        x, aud_conversion) if x > 0 else 0)
    return df


def load_imx(timestamp, usdc_conversion, aud_conversion):
    erc20 = load_imx_erc20(timestamp, usdc_conversion, aud_conversion)
    eth = load_imx_eth(timestamp, aud_conversion)
    df = pd.concat([erc20, eth])
    if len(df) == 0:
        return df

    df['asset_id'] = df['data'].apply(lambda x: x['token_id'])
    df['url'] = df['asset_id'].apply(
        lambda x: f'https://illuvidex.illuvium.io/asset/0x9e0d99b864e1ac12565125c5a82b59adea5a09cd/{x}')
    df['properties'] = df['data'].apply(lambda x: x['properties'])
    df['name'] = df['properties'].apply(lambda x: x['name'])
    df['region'] = df['name'].apply(lambda x: x.split('(')[0].strip())
    df['coordinates'] = df['name'].apply(
        lambda x: x.split('(')[1].split(')')[0])
    df['x'] = df['coordinates'].apply(lambda x: x.split(',')[0])
    df['y'] = df['coordinates'].apply(lambda x: x.split(',')[1])
    df['updated_timestamp'] = pd.to_datetime(df['updated_timestamp'])
    return df


def load_tokentrove():
    url = 'https://api.tokentrove.com/cached/metadata-stats?tokenAddress=0x9e0d99b864e1ac12565125c5a82b59adea5a09cd&currencyAddress=ETH'
    headers = {
        'x-api-key': 'Np8BV2d5QR9TSFEr9EvF66FWcJf0wIxy2qBpOH6s',
        'referer': 'https://tokentrove.com/',
    }
    response = requests.get(url, headers=headers, timeout=5).json()
    return json.loads(response[0]['ninety_day_data'])


def get_floor(data, tier=1):
    tier_data = data[str(tier)]
    last_key = [*tier_data.keys()][-1]
    floorprice = tier_data[last_key]['floorPrice']/1e18
    return floorprice


def get_import_string(landId):
    land = get_plot_metadata(landId)

    mapping = {
        "HYDROGEN": "HYDROGEN_PUMP_1",
        "SILICON": "MINE_1",
        "CARBON": "SEDIMENT_EXCAVATOR_1",
        "HYPERION": "HYPERION_EXTRACTOR_1",
        "SOLON": "SOLON_DREDGE_1",
        "CRYPTON": "CRYPTON_GATE_1"
    }

    output = ""
    for site in land["sites"]:
        output += f"[\"{mapping[site['siteType']]}\",{site['coordinates']['y']},{site['coordinates']['x']}],"
    output = f'[{output[:-1]}]'
    return output


def get_import_url(landId):
    return "https://ilz.land/"
    import_string = get_import_string(landId)
    data = {
        "0": {
            "json": {
                "jsonExport": import_string
            }
        }
    }
    s = f'https://illuvitect.com/api/trpc/example.generateUrl?batch=1&input={quote(json.dumps(data).replace(" ",""))}'
    response = requests.get(s).json()[0]
    url = response['result']['data']['json']['url']
    return url
