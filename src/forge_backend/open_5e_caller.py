import requests


# Gets data from the Open5e API
class Open5eCaller:

    def get_races(self):
        response = requests.get("https://api.open5e.com/v1/races/")
        return response.json()

    def get_classes(self):
        response = requests.get("https://api.open5e.com/v1/classes/")
        return response.json()

    # def get_equipement #TODO: is it the armors? need clarification