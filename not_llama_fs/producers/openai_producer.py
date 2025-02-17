import base64
import json
import logging
import pathlib
import os

import openai
import magic
import openai
from llama_index.core import SimpleDirectoryReader

from .interface import ABCProducer, clean_filename
from ..fs.tree import TreeObject


class OpenAIProducer(ABCProducer):
    def __init__(self, host: str = "https://api.openai.com/v1", api_key: str = None):
        super().__init__()
        self.host = host
        self.prompt = None
        self.model = None
        self.options = {}
        self._client = None
        self.api_key = api_key

    def setup(
            self,
            prompt: str,
            model: str = "gpt-3.5-turbo",
            options: dict | None = None,
    ):
        self.prompt = prompt
        self.model = model
        if options is not None:
            self.options = options
        if self.options is None:
            self.options = {}

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(api_key=self.api_key, base_url=self.host)
        return self._client

    def prepare_files(self, path, ignore):
        if self.model is None:
            raise ValueError("Model is not set")
        if self.prompt is None:
            raise ValueError("Prompt is not set")
        if self.options is None:
            raise ValueError("Options are not set")
		
        # Split ignore to take a single string as input
        if ignore is not None:
            ignore = ignore.split(',')
            for i in range(len(ignore)):
                ignore[i] = os.path.join(path, ignore[i].strip())
            print(f"Ignoring files/folder: {ignore}")
        else:
            print("Nothing was ignored")
            ignore = []

        reader = SimpleDirectoryReader(path, filename_as_id=True, recursive=True, exclude=ignore) 

        for file in reader.iter_data():
            result = self.client.with_options(**self.options).chat.completions.create(
                messages=[
                    {"content": self.prompt, "role": "system"},
                    {"role": "user", "content": str(file)[:1000]}
                ],
                temperature=1,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                model=self.model,
                response_format={"type": "json_object"}
            )

            filepath = clean_filename(file[0].doc_id)

            print(f"Prepared {filepath}")
            self.prepared_files.append((filepath, result.choices[0].message.content))

    def produce(self) -> TreeObject:
        if self.model is None:
            raise ValueError("Model is not set")
        if self.prompt is None:
            raise ValueError("Prompt is not set")
        if self.options is None:
            raise ValueError("Options are not set")

        openai_response = self.client.with_options(**self.options).chat.completions.create(
            messages=[
                {"content": self.prompt, "role": "system"},
                {"content": json.dumps(self.prepared_files), "role": "user"}
            ],
            model=self.model,
            response_format={"type": "json_object"}
        ).choices[0].message.content

        try:
            openai_response_json = json.loads(openai_response)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON response: {e}")
            logging.error(f"Response: {openai_response}")
            raise e

        return openai_response_json, TreeObject.from_json(openai_response_json)


