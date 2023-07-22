import os
import json
import openai
import argparse
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

class CopilotContext:
    def __init__(self) -> None:
        load_dotenv('pfcopilot.env')
        self.use_aoai = os.environ.get("AOAI_BY_DEFAULT", "true").lower() == "true"
        self.aoai_key = os.environ.get("AOAI_API_KEY")
        self.aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
        self.aoai_api_base = os.environ.get("AOAI_API_BASE")

        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_API_KEY")

    def check_env(self):
        if self.use_aoai:
            if not self.aoai_key or not self.aoai_deployment or not self.aoai_api_base:
                return False, "You configured to use AOAI, but one or more of the following environment variables were not set: AOAI_API_KEY, AOAI_DEPLOYMENT, AOAI_API_BASE"
            else:
                return True, ""
        else:
            if not self.openai_key or not self.openai_model:
                return False, "You configured to use OPENAI, but one or more of the following environment variables were not set: OPENAI_API_KEY, OPENAI_API_KEY"
            else:
                return True, ""
            
