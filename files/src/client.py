import requests

# Simple client to test the server
# Usage: python client.py page1.png page2.png

import sys

if len(sys.argv) != 3:
    print("Usage: python client.py <page1.png> <page2.png>")
    sys.exit(1)

page1_path = sys.argv[1]
page2_path = sys.argv[2]

url = 'http://localhost:5001/score'

files = {
    'page1': open(page1_path, 'rb'),
    'page2': open(page2_path, 'rb')
}

response = requests.post(url, files=files)

if response.status_code == 200:
    data = response.json()
    print(f"Score: {data['score']}")
    print("Colored images:")
    for url in data['image_urls']:
        print(f"  {url}")
else:
    print(f"Error: {response.status_code} - {response.text}")