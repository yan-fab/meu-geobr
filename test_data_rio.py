import requests
import re

url = 'https://www.data.rio/datasets/PCRJ::limites-de-favelas-e-urbaniza%C3%A7%C3%A3o'
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(url, headers=headers)
    print('Status:', r.status_code)
    geojson_links = re.findall(r'https?://[^\s\"\'<>]*?\.geojson[^\s\"\'<>]*', r.text)
    zip_links = re.findall(r'https?://[^\s\"\'<>]*?\.zip[^\s\"\'<>]*', r.text)
    api_links = re.findall(r'https?://[^\s\"\'<>]*?FeatureServer[^\s\"\'<>]*', r.text)

    print('GeoJSON Links:', list(set(geojson_links)))
    print('ZIP Links:', list(set(zip_links)))
    print('API Links:', list(set(api_links)))
except Exception as e:
    print('Error:', e)
