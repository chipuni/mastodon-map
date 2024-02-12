import http.client
import json
import multiprocessing
import pickle
import sys
import requests
import robots
import time

PICKLE_FILE_NAME = "connections.p"
PROLOG_FILE_NAME = "peers.pl"
SEEN_FILE_NAME = "seen.p"
NOT_SEEN_FILE_NAME = "notseen.p"


# May we scrape your site?
def check_robots(site, url, q):
    site_robots = f"http://{site}/robots.txt"
    try:
        rp = robots.RobotsParser.from_uri(site_robots)
        q.put(rp.can_fetch(useragent="*", url=url))
    except UnicodeDecodeError:
        print(f"Could not decode {site_robots}. Being kind and not scanning.")
        q.put(False)
    except http.client.BadStatusLine:
        print(f"Bad status line for {site_robots}. Being kind and not scanning.")
        q.put(False)
    except UnicodeEncodeError:
        print(f"Could not encode {site_robots}. Being kind and not scanning.")
        q.put(False)
    except ConnectionResetError:
        print(f"Connection reset in {site_robots}. Not scanning.")
        q.put(False)
    except http.client.InvalidURL:
        print(f"Invalid URL in {site_robots}, not scanning.")
        q.put(False)


def check_robots_guard(site, url):
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=check_robots, name="check_robots", args=(site, url, q))
    p.start()
    p.join(10)
    if p.is_alive():
        print("Took more than 10 seconds to read robots.txt. Killing and returning no.")
        p.terminate()
        return False
    else:
        return q.get()


# List all the connections that a site federates with.
# This method makes https requests, so it should not be used in testing.
def get_connections(site):
    url = f"https://{site}/api/v1/instance/peers"
    print(f"url = {url}")
    try:
        if not check_robots_guard(site, url):
            print(f"Error: {site} does not allow robots to read peers.")
            return []
        text_response = requests.get(url=url, timeout=60)
        if text_response.status_code == 200:
            try:
                json_response = json.loads(text_response.text)
                return json_response
            except json.decoder.JSONDecodeError:
                print(f"Error: {site} did not return JSON.")
                return []
        else:
            print(f"Error: {site} did not respond to the peers request.")
            return []
    except OSError:
        print(f"Error: {site} could not be reached.")
        return []


# Updates the map of connections.

def convert_list_to_prolog(site, peers):
    result = ""
    for peer in peers:
        result += f"peer('{site}', '{peer}').\n"
    return result


def write_to_files(seen, not_seen, site, peers):
    prolog_file = open(PROLOG_FILE_NAME, "a")
    prolog_list = convert_list_to_prolog(site, peers)
    prolog_file.write(prolog_list)
    prolog_file.close()

    seen.add(site)
    not_seen.update(set(peers) - seen)

    seen_file = open(SEEN_FILE_NAME, "wb")
    pickle.dump(seen, seen_file)
    seen_file.close()

    not_seen_file = open(NOT_SEEN_FILE_NAME, "wb")
    pickle.dump(not_seen, not_seen_file)
    not_seen_file.close()


def print_time():
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)
    print(current_time)


def drop_site(site):
    return site is None or site.endswith("activitypub-troll.cf") or site.endswith("noho.st") or \
        site.endswith("jpbutler.com")


def create_map(func_connector, seen, not_seen):
    while len(not_seen) > 0:
        site = not_seen.pop()
        seen.add(site)
        if drop_site(site):
            continue
        print_time()
        print(f"Examining site {site}. {len(seen)} sites seen, {len(not_seen)} sites remaining.")
        try:
            peers = func_connector(site)
        except BaseException:
            peers = []
            print(f"Exception happened. Skipping.")
        safe_peers = set(filter(lambda s: not drop_site(s), peers))
        not_seen.update(set(safe_peers) - seen)
        write_to_files(seen, not_seen, site, safe_peers)


# What everything calls
def main():
    if len(sys.argv) > 1:
        seen = set()
        not_seen_safe = set([sys.argv[1]])
    else:
        seen_file = open(SEEN_FILE_NAME, 'rb')
        seen = pickle.load(seen_file)
        seen_file.close()

        not_seen_file = open(NOT_SEEN_FILE_NAME, "rb")
        not_seen = pickle.load(not_seen_file)
        not_seen_file.close()

        not_seen_safe = set(filter(lambda s: not drop_site(s), not_seen))

    create_map(func_connector=get_connections, seen=seen, not_seen=not_seen_safe)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
