import requests

API_URL = "https://randomuser.me/api/?nat={}"

def fetch_fake_address(country_code: str):
    r = requests.get(API_URL.format(country_code), timeout=10)
    r.raise_for_status()
    data = r.json()["results"][0]

    name = data["name"]
    loc = data["location"]

    return {
        "name": f'{name["title"]} {name["first"]} {name["last"]}',
        "gender": data["gender"],
        "street": f'{loc["street"]["number"]} {loc["street"]["name"]}',
        "city": loc["city"],
        "state": loc["state"],
        "country": loc["country"],
        "postcode": loc["postcode"],
        "email": data["email"],
        "phone": data["phone"],
        "username": data["login"]["username"],
        "password": data["login"]["password"],
        "nat": data["nat"]
    }

