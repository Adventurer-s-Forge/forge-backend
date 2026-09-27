import requests


# Gets data from the Open5e API
class Open5eCaller:
    def pagination_data(self, url):
        all_data = []

        while url:
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()
            all_data.extend(data["results"])
            url = data["next"]

        return all_data

    def get_races(self):
        return self.pagination_data("https://api.open5e.com/v2/species/")

    def get_classes(self):
        return self.pagination_data("https://api.open5e.com/v2/classes/")

    def get_backgrounds(self):
        return self.pagination_data("https://api.open5e.com/v2/backgrounds/")

    def get_items(self):
        return self.pagination_data("https://api.open5e.com/v2/items/")

    def get_spells(self):
        return self.pagination_data("https://api.open5e.com/v2/spells/")
