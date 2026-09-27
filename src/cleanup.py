from forge_backend.user_character_data_service import UserCharacterDataService
from forge_backend.storage import char_key, char_index_key


user_id = "a12345"
chars = [  
    "c0b2a29e",
    "29b40450",
]
userCharacterDataService = UserCharacterDataService()
for char in chars:
    userCharacterDataService.redis_client.delete(char_key(user_id, char)) # Delete the test character [7]
    userCharacterDataService.redis_client.delete(char_index_key(user_id))
s
# 33708  