import requests
import sys

def get_tags(repo):
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags"
    tags = []
    page = 1
    while url:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                print(f"Error {resp.status_code}")
                break
            data = resp.json()
            tags.extend([t['name'] for t in data.get('results', [])])
            url = data.get('next')
            if not url and page == 1 and len(tags) == 0:
                # maybe different API
                break
            page += 1
            if len(tags) > 30:
                break
        except Exception as e:
            print(f"Exception: {e}")
            break
    return tags

if __name__ == "__main__":
    repo = "bitnami/mlflow"
    tags = get_tags(repo)
    if tags:
        print(f"Found {len(tags)} tags for {repo}")
        for tag in tags[:10]:
            print(f"  {tag}")
        # pick a tag that looks like version
        for tag in tags:
            if tag.startswith('2.') and '-' not in tag:
                print(f"\nSuggested tag: {tag}")
                sys.exit(0)
        # else pick first
        print(f"\nFirst tag: {tags[0]}")
    else:
        print("No tags found")
        sys.exit(1)