import httpx
import json
import re
import asyncio
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

# Configuration
GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "via" 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def scrape_via():
    api_url = "https://stra.viaplus.site/main"
    # EPG URL pointing to the 'via' repo
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/epg.xml"
    
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.get(api_url)
            data = response.json()
            
            valid_streams = []
            
            for category in data:
                cat_name = category.get('category', 'General')
                events = category.get('events', [])
                
                for event in events:
                    event_name = event.get('name', 'Unknown Event')
                    event_id = event.get('URL', '0')
                    # Pulling logo directly from the JSON
                    logo = event.get('logo', '') 
                    
                    for stream in event.get('streams', []):
                        stream_name = stream.get('name', 'Stream')
                        full_name = f"{event_name} - {stream_name}"
                        url = stream.get('url', '')
                        
                        if url.startswith('http'):
                            valid_streams.append({
                                "id": f"{event_id}-{stream_name.replace(' ', '')}", 
                                "name": full_name, 
                                "url": url,
                                "logo": logo,
                                "group": cat_name
                            })

            # --- GENERATE EPG (XMLTV) ---
            root = ET.Element("tv")
            for item in valid_streams:
                channel = ET.SubElement(root, "channel", id=item["id"])
                ET.SubElement(channel, "display-name").text = item["name"]
                if item["logo"]:
                    ET.SubElement(channel, "icon", src=item["logo"])
                
                # 6-hour window for current programming
                start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                stop = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).strftime("%Y%m%d%H%M%S +0000")
                prog = ET.SubElement(root, "programme", start=start, stop=stop, channel=item["id"])
                ET.SubElement(prog, "title", lang="en").text = item["name"]
                if item["logo"]:
                    ET.SubElement(prog, "icon", src=item["logo"])

            with open(os.path.join(BASE_DIR, "epg.xml"), "w") as f:
                f.write(minidom.parseString(ET.tostring(root)).toprettyxml(indent="  "))

            # --- GENERATE M3U8 ---
            with open(os.path.join(BASE_DIR, "playlist.m3u8"), "w") as f:
                f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
                for item in valid_streams:
                    logo_attr = f' tvg-logo="{item["logo"]}"' if item["logo"] else ""
                    
                    f.write(f'#EXTINF:-1 tvg-id="{item["id"]}"{logo_attr} group-title="{item["group"]}",{item["name"]}\n')
                    f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n')
                    f.write(f'#EXTVLCOPT:http-referrer=https://timstreams.lol/\n')
                    f.write(f'{item["url"]}\n')

            print(f"Success: Found {len(valid_streams)} streams.")

        except Exception as e:
            print(f"Scraper Error: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_via())
