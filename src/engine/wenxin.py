import requests
import os
import json
from .base_engine import Engine
from utils.register import register_class
import time
import random


@register_class(alias="Engine.WenXin")
class WenXinEngine(Engine):
    def __init__(self, api_key=None, sercet_key=None, temperature=0.95, top_p=0.8, penalty_score=1.0, *args, **kwargs):
        self.api_key = api_key if api_key is not None else os.environ.get('WENXIN_API_KEY')
        self.secret_key = sercet_key if sercet_key is not None else os.environ.get('WENXIN_SECRET_KEY')
        self.url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro?access_token=" + \
            self.get_access_token()
        self.temperature = temperature
        self.top_p = top_p
        self.penalty_score = penalty_score
        self.model_name = 'ERNIE-Bot4'

    def get_access_token(self):
        """
        使用 AK/SK 生成鉴权签名（Access Token）
        :return: access_token，或是 None(如果错误)
        """
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {"grant_type": "client_credentials", "client_id": self.api_key, "client_secret": self.secret_key}
        return str(requests.post(url, params=params).json().get("access_token"))

    def get_response(self, messages, system=None):
        # print("get response from wenxin")
        # print(messages)
        # print(system)
        payload = json.dumps({
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "penalty_score": self.penalty_score,
            "system": system
        })
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", self.url, headers=headers, data=payload)
        
        json_data = json.loads(response.text)
        print(json_data)
        json_data = json_data["result"]
        return json_data
    
        i = 0
        while i < 10:
            try:
                # print("get response from wenxin")
                # print(messages)
                # print(system)
                payload = json.dumps({
                    "messages": messages,
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "penalty_score": self.penalty_score,
                    "system": system
                })
                headers = {
                    'Content-Type': 'application/json'
                }
                response = requests.request("POST", self.url, headers=headers, data=payload)
                json_data = json.loads(response.text)["result"]
                break
            except:
                sleep_time = random.randint(5, 10)
                time.sleep(sleep_time)
                i += 1
            
        return json_data
