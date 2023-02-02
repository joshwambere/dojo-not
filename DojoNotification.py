import json
import os
import time
import requests
from dotenv import load_dotenv
import redis


load_dotenv()

CODE_DOJO_URL = os.getenv("CODE_DOJO_URL")
SIGNAL_CI_URL = os.getenv("SIGNAL_CI_URL")
CODE_DOJO_AUTH_ENDPOINT = "api-token-auth/"
CODE_DOJO_PRODUCT_ENDPOINT = "products/"
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
REDIS_CLIENT = redis.Redis(host='redis', port=6379, db=0)



class AuthException(Exception):

    def __init__(self, message):
        self.message = message

class RedisCache():
    @classmethod
    def get_cached_response(cls,key):
        response = REDIS_CLIENT.get(key)
        if response:
            return json.loads(response.decode('utf-8'))
        return None

    @classmethod
    def set_cached_response(cls,key, value, ttl):
        REDIS_CLIENT.set(key, json.dumps(value), ex=ttl)

    @classmethod
    def update_cache(cls,key, value, ttl):
        current_time = int(time.time())
        last_updated = REDIS_CLIENT.get(f'{key}_last_updated')
        if not last_updated or int(last_updated) + ttl <= current_time:
            RedisCache.set_cached_response(key, value, ttl)
            RedisCache.redis_client.set(f'{key}_last_updated', current_time)
    @classmethod
    def get_all_cached_responses(cls):
        responses = {}
        cursor = 0
        while cursor != 0:
            cursor, keys = REDIS_CLIENT.scan(cursor=cursor, match=None)
            for key in keys:
                response = REDIS_CLIENT.get(key)
                if response:
                    responses[key] = json.loads(response.decode('utf-8'))
        return responses

class DojoNotification:
    
    
    
    @classmethod
    def index(cls):
        cache =  RedisCache.get_all_cached_responses()
        if cache:
            RedisCache.update_cache('New',DojoNotification.get_response(), 90)
        else:
            RedisCache.set_cached_response('New',DojoNotification.get_response(), 90)
        
        
        while True:
            new_response = DojoNotification.get_response()
            last_cached_response = RedisCache.get_cached_response('New')
            # Check for new objects in the response
            new_objects = [
                item for item in new_response['results']
                if item not in last_cached_response['results']
            ]
            if new_objects:
                # Call signal_cli function
                DojoNotification.signal_cli(new_objects, "+250788336717")
                # Update the cache with  the new response
                last_cached_response = new_response
                time.sleep(60)

    @classmethod
    def authentication(cls):
        url = CODE_DOJO_URL + CODE_DOJO_AUTH_ENDPOINT
        headers = {'content-type': 'application/json'}
        payload = {"username": USERNAME, "password": PASSWORD}
        response = requests.post(url,
                                 headers=headers,
                                 data=json.dumps(payload))

        if response.status_code != 200:
            raise AuthException("Authentication failed")
        return response.json()

    @classmethod
    def create_alert_message(cls, data):
        if not data:
            raise Exception("Unsupported data Type")
        elif isinstance(data, list):
            try:
                for item in data:
                    if len(item["name"]) > 0:
                        product_name = item["name"]
                        criticality = item.get("business_criticality", "None")
                        message = "New vulnerability found in '{}' with a {} business criticality. Please address immediately.".format(
                            product_name, criticality)
                        return message
            except KeyError as e:
                print(
                    "An error occurred while accessing the data: {}".format(e))
            except Exception as e:
                print("An unknown error occurred: {}".format(e))
        else:
            raise Exception("Unsupported data Type")

    @classmethod
    def get_response(cls):
        # Call authentication function
        token = DojoNotification.authentication()
        url = CODE_DOJO_URL + CODE_DOJO_PRODUCT_ENDPOINT
        headers = {
            'content-type': 'application/json',
            'Authorization': 'Token ' + token['token']
        }
        response = requests.get(url, headers=headers)
        return response.json()

    @classmethod
    def signal_cli(cls, message, phone_number, message_group="default"):
        if not message:
            raise Exception("Unkown message Type")
        else:
            try:
                # Get group ID

                url = SIGNAL_CI_URL + 'v1/groups/{}'.format(phone_number)
                response = requests.get(url,
                                        headers={'accept': 'application/json'})

                response.raise_for_status()
                groups = response.json()
                group_found = [
                    group for group in groups if group['name'] == message_group
                ]
                group_id = groups[0][
                    'id'] if message_group == "default" else group_found

                # Send message
                url = SIGNAL_CI_URL + 'v2/send'

                data = {
                    "message": DojoNotification.create_alert_message(message),
                    "number": phone_number,
                    "recipients": [group_id]
                }
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url,
                                         data=json.dumps(data),
                                         headers=headers)

                response.raise_for_status()
                return response.status_code
            except requests.exceptions.HTTPError as err:

                raise Exception("HTTPError: {}".format(err))
            except Exception as err:
                raise Exception("System Error: {}".format(err))



