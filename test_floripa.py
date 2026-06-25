import requests
import re

url = 'https://geoportal.pmf.sc.gov.br/map'
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get(url, headers=headers, timeout=10)
    print('Status:', r.status_code)
    
    if 'arcgis' in r.text.lower():
        print('Contains ArcGIS')
    if 'geonode' in r.text.lower():
        print('Contains GeoNode')
    if 'geoserver' in r.text.lower():
        print('Contains GeoServer')
    
    geojson_links = re.findall(r'https?://[^\s\"\'<>]*?\.geojson[^\s\"\'<>]*', r.text)
    print('GeoJSON Links:', list(set(geojson_links)))
except Exception as e:
    print('Error:', e)
