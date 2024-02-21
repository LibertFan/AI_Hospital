import os
import openai
from openai import OpenAI
from utils.register import register_class
from .base_engine import Engine
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


@register_class(alias="Engine.HuatuoGPT")
class HuatuoGPTEngine(Engine):
    def __init__(self, model_name_or_path, temperature=0.0, max_tokens=1024, top_p=1, frequency_penalty=0, presence_penalty=0):

        self.model_name = model_name_or_path.split("/")[-1]
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path,
            use_fast=True, 
            trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            device_map="auto", 
            torch_dtype=torch.bfloat16, 
            trust_remote_code=True
        )

        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty

    def get_response(self, messages):
        response = self.model.HuatuoChat(self.tokenizer, messages)
        # i = 0
        # while i < 3:
        #     try:
        #         response = self.model.HuatuoChat(self.tokenizer, messages)
        #         break
        #     except Exception as e:
        #         print("Error: {}".format(e))
        #         i += 1
        #         continue
        return response

