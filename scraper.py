import httpx
import json
import asyncio
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

# --- CONFIGURATION ---
GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "via" 
SOURCE_URL = "https://stra.viaplus.site/main"

# Path logic for GitHub Actions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def resolve_blood(client, embed_url):
    """
    Mimics the POST /blood handshake to extract direct .m3u8 links.
    """
    try:
        # Extract the ID from the end of the embed URL
        stream_id = embed_url.split('/')[-1]
        
        # Handshake endpoint identified from logs
        api_endpoint = "https://hddm.viaplus.site/blood"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://hmembeds.one",
            "Referer": embed_url
        }
        
        # The payload required by the server
        payload = {"id": stream_id}
        
        resp = await client.post(api_endpoint, json=payload, headers=headers, timeout=12.0)
        
        if resp.status_code == 200:
            data = resp.text.strip()
            # If the response is a direct link, return it
            if ".m3u8" in data:
                # Handle potential JSON wrapping
                if data.startswith('{'):
                    return resp.json().get('url', embed_url)
                return data
    except Exception:
        pass
    return embed_url # Fallback to original if handshake fails

async def scrape_via():
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/epg.xml"
    
    async with httpx.AsyncClient(timeout=40.0, verify=False) as client:
        try:
            print(f"Fetching source from {SOURCE_URL}...")
            response = await client.get(SOURCE_URL)
            
            if response.status_code != 200:
                print(f"Source down ({response.status_code}).")
                return

            data = response.json()
            valid_streams = []
            
            # Navigate Category -> Event/Channel -> Stream
            for category in data:
                cat_name = category.get('category', 'General')
                events = category.get('events', [])
                
                for event in events:
                    event_name = event.get('name', 'Unknown')
                    event_id = event.get('URL', '0')
                    logo = event.get('logo', '') 
                    
                    for stream in event.get('streams', []):
                        stream_name = stream.get('name', 'Stream')
                        url = stream.get('url', '')
                        
                        if url.startswith('http'):
                            print(f"Handshaking: {event_name} - {stream_name}")
                            # Resolve the embed into a direct link
                            direct_url = await resolve_blood(client, url)
                            
                            valid_streams.append({
                                "id": f"{event_id}-{stream_name.replace(' ', '')}", 
                                "name": f"{event_name} - {stream_name}", 
                                "url": direct_url,
                                "logo": logo,
                                "group": cat_name
                            })

            if not valid_streams: return

            # --- GENERATE EPG (XMLTV) ---
            root = ET.Element("tv")
            for item in valid_streams:
                channel = ET.SubElement(root, "channel", id=item["id"])
                ET.SubElement(channel, "display-name").text = item["name"]
                if item["logo"]:
                    ET.SubElement(channel, "icon", src=item["logo"])
                
                # Generic 6-hour guide block
                start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S +0000")
                stop = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).strftime("%Y%m%d%H%M%S +0000")
                prog = ET.SubElement(root, "programme", start=start, stop=stop, channel=item["id"])
                ET.SubElement(prog, "title", lang="en").text = item["name"]

            with open(os.path.join(BASE_DIR, "epg.xml"), "w", encoding="utf-8") as f:
                f.write(minidom.parseString(ET.tostring(root)).toprettyxml(indent="  "))

            # --- GENERATE M3U8 ---
            with open(os.path.join(BASE_DIR, "playlist.m3u8"), "w", encoding="utf-8") as f:
                f.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
                for item in valid_streams:
                    logo_attr = f' tvg-logo="{item["logo"]}"' if item["logo"] else ""
                    f.write(f'#EXTINF:-1 tvg-id="{item["id"]}"{logo_attr} group-title="{item["group"]}",{item["name"]}\n')
                    # TiviMate essential headers
                    f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n')
                    f.write(f'#EXTVLCOPT:http-referrer=https://timstreams.lol/\n')
                    f.write(f'{item["url"]}\n')

            print(f"Successfully updated {len(valid_streams)} direct streams.")

        except Exception as e:
            print(f"Scraper Error: {e}")

if __name__ == "__main__":
    asyncio.run(scrape_via())
