import requests
from django.conf import settings


def fetch_coordinates(apikey, place):
    params = {"geocode": place, "apikey": apikey, "format": "json"}
    response = requests.get(settings.YANDEX_BASE_URL, params=params)
    response.raise_for_status()
    places_found = response.json()['response']['GeoObjectCollection']['featureMember']
    most_relevant = places_found[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat
