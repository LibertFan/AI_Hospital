import os
import openai
from openai import OpenAI
from utils.register import register_class
from .base_engine import Engine
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation.utils import GenerationConfig


@register_class(alias="Engine.HF")
class HFEngine(Engine):
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
        self.model.generation_config = GenerationConfig.from_pretrained(model_name_or_path)

    def get_response(self, messages):
        response = self.model.chat(self.tokenizer, messages)
        return response

