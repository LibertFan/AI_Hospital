import requests
from .base_engine import Engine
from utils.register import register_class


@register_class(alias="Engine.MiniMax")
class MiniMaxEngine(Engine):
    def __init__(self, minimax_api_key, minimax_group_id, minimax_model_name="abab5.5-chat", tokens_to_generate=1024, temperature=0.0, top_p=0.7, stream=True, *args, **kwargs):
        self.model_name = minimax_model_name
        self.url = f"https://api.minimax.chat/v1/text/chatcompletion_pro?GroupId={minimax_group_id}"
        self.headers = {"Authorization": f"Bearer {minimax_api_key}", "Content-Type": "application/json"}
        self.temperature = temperature
        self.top_p = top_p
        self.tokens_to_generate = tokens_to_generate
        self.stream = stream

    def get_response(self, messages, bot_setting):
        request_body = {
            "model": self.model_name,
            "tokens_to_generate": self.tokens_to_generate,
            "temperature": self.temperature,
            "top_p": self.top_p,
            # "stream": self.stream,
            "reply_constraints": {"sender_type": "BOT", "sender_name": "医生"},
            "messages": messages,
            "bot_setting": bot_setting
        }

        response = requests.post(self.url, headers=self.headers, json=request_body)
        reply = response.json()["reply"]
        return reply
