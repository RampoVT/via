import httpx
import json
import re
import asyncio
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

# --- UPDATE THESE TO MATCH YOUR NEW REPO ---
GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "YOUR_REPO_NAME_HERE" 
DEFAULT_LOGO = "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/powerstreams.png?raw=true"
# -------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def scrape_via():
    api_url = "https://stra.viaplus.site/main"
    # This URL must match your repo name for TiviMate to find the EPG automatically
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/epg.xml"
    
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        try:
            response = await client.get(api_url)
            data = response.json()
            
            valid_streams = []
            
            # Process the specific JSON structure provided
            for category in data:
                cat_name = category.get('category', 'General')
                
                # Skip categories with no events (like Replays)
                events = category.get('events', [])
                if not events: continue
                
                for event in events:
                    event_name = event.get('name', 'Unknown Event')
                    event_id = event.get('URL', '0')
                    logo = event.get('logo', DEFAULT_LOGO)
                    
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
                ET.SubElement(channel, "icon", src=item["logo"])
                
                start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                stop = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).strftime("%Y%m%d%H%M%S +0000")
                prog = ET.SubElement(root, "programme", start=start, stop=stop, channel=item["id"])
                ET.SubElement(prog, "title", lang="en").text = item["name"]
                ET.SubElement(prog, "icon", src=item["logo"])

            with open(os.path.join(BASE_DIR, "epg.xml"), "w") as f:
                f.write(minidom.parseString(ET.tostring(root)).toprettyxml(indent="  "))

            # --- GENERATE M3U8 WITH TIVIMATE HEADERS ---
            with open(os.path.join(BASE_DIR, "playlist.m3u8"), "w") as f:
                f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
                for item in valid_streams:
                    f.write(f'#EXTINF:-1 tvg-id="{item["id"]}" tvg-logo="{item["logo"]}" group-title="{item["group"]}",{item["name"]}\n')
                    # Set headers for timstreams.lol
                    f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n')
                    f.write(f'#EXTVLCOPT:http-referrer=https://timstreams.lol/\n')
                    f.write(f'{item["url"]}\n')

            print(f"Update Success: {len(valid_streams)} streams processed.")

        except Exception as e:
            print(f"Scraper Error: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_via())
