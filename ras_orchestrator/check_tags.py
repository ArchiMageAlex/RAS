import requests
import json

def list_tags(repo):
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags"
    tags = []
    while url:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            break
        data = resp.json()
        tags.extend([t['name'] for t in data.get('results', [])])
        url = data.get('next')
    return tags

if __name__ == "__main__":
    repos = ["mlflow/mlflow", "bitnami/mlflow"]
    for repo in repos:
        print(f"\n=== Tags for {repo} ===")
        try:
            tags = list_tags(repo)
            print(f"Total tags: {len(tags)}")
            # Show first 10 tags
            for tag in tags[:10]:
                print(f"  - {tag}")
        except Exception as e:
            print(f"Failed: {e}")