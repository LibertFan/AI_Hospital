import zhipuai
from .base_engine import Engine
from utils.register import register_class


@register_class(alias="Engine.ChatGLM")
class ChatGLMEngine(Engine):
    def __init__(self, chatglm_api_key, model_name="chatglm_pro", temperature=0.0, top_p=0.7, incremental=True, *args, **kwargs):
        zhipuai.api_key = chatglm_api_key
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        self.incremental = incremental

    def get_response(self, messages):
        response = zhipuai.model_api.sse_invoke(
            model=self.model_name,
            prompt=messages,
            temperature=self.temperature,
            top_p=self.top_p,
            incremental=self.incremental
        )
        
        data = ""
        for event in response.events():
            data += event.data
            if event.event == "finish":
                meta = event.meta
                break
        return data