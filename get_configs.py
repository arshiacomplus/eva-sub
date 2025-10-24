import requests
import json
import time
import os
import base64
from urllib.parse import urlparse, unquote

API_URL = "https://api.evavpn.com/connections"


HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjdmMTA2NWE3LTVlZWMtNGQ2Ny1iODM4LTA5OTFjODdkNWFhMyIsImlhdCI6MTc2MTMxMTA0MSwiZXhwIjoxNzYzOTAzMDQxfQ.m3YfTfTVyLulYz1YFmkzfT3bx_97uVwP3h7QPATQtTY",
    "Content-Type": "application/json; charset=UTF-8",
    "Host": "api.evavpn.com",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "User-Agent": "okhttp/4.9.2"
}


BASE_BODY = {
  "d_t": "android",
  "d_id": "d8b9e1ec-2165-40b1-8a06-82d264486119"
}

SS_OUTPUT_FILE = "configs.txt"
V2RAY_JSON_OUTPUT_FILE = "v2ray_configs.json"

V2RAY_JSON_TEMPLATE = {
  "remarks": "Placeholder Remark",
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "tag": "socks",
      "port": 10808,
      "protocol": "socks",
      "settings": {
        "auth": "noauth",
        "udp": True,
        "userLevel": 0
      },
      "sniffing": {
        "enabled": True,
        "destOverride": ["http", "tls"]
      }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "shadowsocks",
      "settings": {
        "servers": [
          {
            "address": "placeholder_address",
            "method": "placeholder_method",
            "password": "placeholder_password",
            "port": 0,
            "level": 0
          }
        ]
      },
      "streamSettings": {
        "network": "tcp"
      },
      "mux": {
        "enabled": False
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "UseIP"
      }
    },
    {
      "tag": "block",
      "protocol": "blackhole",
      "settings": {
        "response": {
          "type": "http"
        }
      }
    }
  ],
  "dns": {
    "servers": [
      "1.1.1.1",
      "8.8.8.8"
    ]
  },
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "ip": ["1.1.1.1", "8.8.8.8"],
        "port": "53",
        "outboundTag": "proxy"
      },
       {
        "type": "field",
        "domain": ["geosite:private"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "network": "udp",
        "port": "1-65535",
        "outboundTag": "proxy"
      },
      {
        "type": "field",
        "network": "tcp",
        "port": "1-65535",
        "outboundTag": "proxy"
      }
    ]
  }
}


def parse_ss_url(ss_url):
    try:
        if not ss_url.startswith("ss://"):
            print(f"Invalid SS URL format: {ss_url}")
            return None

        encoded_part = ss_url[len("ss://"):]

        parts = encoded_part.split('#', 1)
        if len(parts) == 2:
            encoded_server_info, remark = parts
            remark = unquote(remark)
        else:
            encoded_server_info = parts[0]
            remark = "No Remark"

        login_server_parts = encoded_server_info.split('@', 1)
        if len(login_server_parts) != 2:
            print(f"Invalid SS URL format (missing @): {ss_url}")
            return None

        encoded_login_info, server_address_port = login_server_parts

        decoded_login_info_bytes = None
        try:
            decoded_login_info_bytes = base64.urlsafe_b64decode(encoded_login_info + '===')
        except (base64.binascii.Error, ValueError):
             try:
                 decoded_login_info_bytes = base64.b64decode(encoded_login_info + '===')
             except (base64.binascii.Error, ValueError):
                 print(f"Failed to base64 decode login info using standard/urlsafe methods: {encoded_login_info}")
                 return None



        decoded_login_info = decoded_login_info_bytes.decode('utf-8')


        method_password_parts = decoded_login_info.split(':', 1)
        if len(method_password_parts) != 2:
             print(f"Invalid SS URL format (missing : in login info): {ss_url}")
             return None
        method, password = method_password_parts

        address_port_parts = server_address_port.split(':', 1)
        if len(address_port_parts) != 2:
            print(f"Invalid SS URL format (missing : in address:port): {ss_url}")
            return None
        address, port_str = address_port_parts


        try:
            port = int(port_str.split("/")[0])
        except ValueError:
            port = int(port_str)
            

        parsed_url = urlparse(ss_url)


        return {
            "method": method,
            "password": password,
            "address": address,
            "port": port,
            "remark": remark
        }

    except Exception as e:
        print(f"Error parsing SS URL {ss_url}: {e}")
        return None

def fetch_configs():

    valid_ss_urls = []
    print("Starting to fetch configs...")

    for region_id in range(1, 101):
        try:
            body = BASE_BODY.copy()
            body["regionId"] = region_id

            json_body = json.dumps(body)

            print(f"Requesting config for Region ID: {region_id}")

            response = requests.post(API_URL, headers=HEADERS, data=json_body, timeout=20)

            if response.status_code == 200:
                data = response.json()
                if not data.get('isError') and data.get('content'):
                    config_url = data['content'].get('access_url')
                    if config_url and config_url.startswith("ss://"):
                        print(f"  [SUCCESS] Found SS config for Region ID: {region_id}")
                        valid_ss_urls.append(config_url)
                    elif config_url:
                        print(f"  [INFO] Found a config for Region ID {region_id} but it's not an SS URL: {config_url}")
                    else:
                        print(f"  [INFO] No 'access_url' found for Region ID: {region_id}")
                else:
                    error_message = data.get('content', 'Unknown error')
                    print(f"  [ERROR] API returned an error for Region ID {region_id}: {error_message}")
            else:
                print(f"  [HTTP ERROR] Failed to get data for Region ID {region_id}. Status Code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"  [NETWORK ERROR] An error occurred for Region ID {region_id}: {e}")

        print("Waiting for 5 seconds...\n")
        time.sleep(5)

    return valid_ss_urls

def create_v2ray_json_configs(ss_urls):

    v2ray_configs_list = []
    print(f"\nProcessing {len(ss_urls)} SS URLs into V2Ray JSON configs...")

    for ss_url in ss_urls:
        parsed_data = parse_ss_url(ss_url)
        if parsed_data:

            config_json = json.loads(json.dumps(V2RAY_JSON_TEMPLATE)) 
            config_json["outbounds"][0]["settings"]["servers"][0]["address"] = parsed_data["address"]
            config_json["outbounds"][0]["settings"]["servers"][0]["method"] = parsed_data["method"]
            config_json["outbounds"][0]["settings"]["servers"][0]["password"] = parsed_data["password"]
            config_json["outbounds"][0]["settings"]["servers"][0]["port"] = parsed_data["port"]

            config_json["remarks"] = parsed_data.get("remark", "Unnamed Server")

            v2ray_configs_list.append(config_json)
            print(f"  Created JSON config for {parsed_data.get('remark', parsed_data['address'])}")

    return v2ray_configs_list

def save_ss_configs_to_file(configs):
    """
    لیست لینک های SS را در فایل متنی ذخیره می‌کند.
    """
    if os.path.exists(SS_OUTPUT_FILE):
        os.remove(SS_OUTPUT_FILE)

    if configs:
        with open(SS_OUTPUT_FILE, "w", encoding="utf-8") as f:
            for config in configs:
                f.write(config + "\n")

        print(f"\nSuccessfully saved {len(configs)} SS URLs to {SS_OUTPUT_FILE}")
    else:
        print(f"\nNo SS URLs to save. {SS_OUTPUT_FILE} will not be created.")


def save_v2ray_json_configs_to_file(v2ray_configs):

    if os.path.exists(V2RAY_JSON_OUTPUT_FILE):
        os.remove(V2RAY_JSON_OUTPUT_FILE)

    if v2ray_configs: 
        try:
            with open(V2RAY_JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(v2ray_configs, f, ensure_ascii=False, indent=4)
            print(f"Successfully saved {len(v2ray_configs)} V2Ray JSON configs to {V2RAY_JSON_OUTPUT_FILE}")
        except Exception as e:
            print(f"Error saving V2Ray JSON configs: {e}")
    else:
         print(f"No V2Ray JSON configs to save. {V2RAY_JSON_OUTPUT_FILE} will not be created.")


if __name__ == "__main__":
    ss_urls = fetch_configs()

    save_ss_configs_to_file(ss_urls)

    v2ray_json_configs = create_v2ray_json_configs(ss_urls)

    save_v2ray_json_configs_to_file(v2ray_json_configs)

    print("\nScript finished.")
