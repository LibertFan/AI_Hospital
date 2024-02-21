from http import HTTPStatus
import dashscope
import os
import time
from .base_engine import Engine
from utils.register import register_class


# [qwen-max, qwen-plus-gamma] 分别是200B和70B的模型 
@register_class(alias="Engine.Qwen")
class QwenEngine(Engine):
    def __init__(self, api_key=None, model_name="qwen-plus-gamma", seed=1, *args, **kwargs):
        self.api_key = api_key if api_key is not None else os.environ.get('DASHSCOPE_API_KEY')
        self.model_name = model_name
        self.seed = seed

    def get_response(self, messages):
        i = 0
        while i < 3:
            try:
                response = dashscope.Generation.call(
                    model=self.model_name,
                    messages=messages,
                    seed=self.seed,
                    result_format='message', 
                )
                # print(response)
                answer = response["output"]["choices"][0]["message"]["content"]
                break
            except:
                i += 1
                time.sleep(10)
                continue

        return answer