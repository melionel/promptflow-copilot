import os
import json
import openai
from datetime import datetime
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

def generate_random_folder_name():
    # Get the current timestamp as a string
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    folder_name = f"generated_flow_{timestamp}"

    return folder_name

def dump_flow(flow_yaml, explaination, python_functions, prompts, requirements, target_folder):
    '''
    dump flow yaml and explaination and python functions into different files
    '''
    if not os.path.exists(target_folder):
        os.mkdir(target_folder)

    with open(f'{target_folder}\\flow.dag.yaml', 'w') as f:
        f.write(flow_yaml)

    with open(f'{target_folder}\\flow.explaination.txt', 'w') as f:
        f.write(explaination)

    for func in python_functions:
        fo =  func if type(func) == dict else json.loads(func)
        for k,v in fo.items():
            with open(f'{target_folder}\\{k}.py', 'w') as f:
                f.write(v)

    for prompt in prompts:
        po = prompt if type(prompt) == dict else json.loads(prompt)
        for k,v in po.items():
            with open(f'{target_folder}\\{k}.jinja2', 'w') as f:
                f.write(v)

    with open(f'{target_folder}\\requirements.txt', 'w') as f:
        f.write(requirements)

class CopilotContext:
    def __init__(self) -> None:
        load_dotenv('pfcopilot.env')
        self.use_aoai = os.environ.get("AOAI_BY_DEFAULT", "true").lower() == "true"
        self.aoai_key = os.environ.get("AOAI_API_KEY")
        self.aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
        self.aoai_api_base = os.environ.get("AOAI_API_BASE")

        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_API_KEY")

        self.local_folder = generate_random_folder_name()

        env = Environment(loader=FileSystemLoader('./'), variable_start_string='[[', variable_end_string=']]')
        self.template = env.get_template('pfplaner_v2.jinja2')

        self.my_custom_functions = [
            {
                'name': 'dump_flow',
                'description': 'dump flow yaml and explaination and python functions into different files',
                'parameters':{
                    'type': 'object',
                    'properties': {
                        'flow_yaml': {
                            'type': 'string',
                            'description': 'flow yaml string'
                        },
                        'explaination': {
                            'type': 'string',
                            'description': 'explaination about how the flow works'
                        },
                        'python_functions': {
                            'type': 'array',
                            'description': 'python function implementations',
                            'items': {
                                'type': 'string'
                            }
                        },
                        'prompts': {
                            'type': 'array',
                            'description': 'prompts',
                            'items': {
                                'type': 'string'
                            }
                        },
                        'requirements': {
                            'type': 'string',
                            'description': 'pip requirements'
                        },
                    },
                    'required': ['flow_yaml', 'explaination', 'python_functions', 'prompts', 'requirements']
                }
            }
        ]

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
            
    def ask_gpt(self, content, print_info_func):
        prompt = self.template.render(goal=content)
            
        chat_message = [
            {'role':'system', 'content':'you are helpful assitant and can help user to write high quality code based on the provided examples'},
            {'role':'user', 'content':prompt}
        ]

        request_args_dict = {
            "messages": chat_message,
            "functions": self.my_custom_functions,
            "function_call": {'name': 'dump_flow'},
            "stream": False,
            "temperature": 0
        }

        if self.use_aoai:
            openai.api_key = self.aoai_key
            openai.api_type = "azure"
            openai.api_base = self.aoai_api_base
            openai.api_version = "2023-07-01-preview"
            request_args_dict['engine'] = self.aoai_deployment
        else:
            openai.api_key = self.openai_key
            request_args_dict['model'] = self.openai_model

        print_info_func('Generating prompt flow for your goal, please wait...', 'Copilot')
        response = openai.ChatCompletion.create(**request_args_dict)

        response_ms = response.response_ms
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        print_info_func(f'Finished generating prompt flow for your goal from ChatGPT in {response_ms} ms!', 'Copilot')
        print_info_func(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}', 'Copilot')

        print_info_func(f'Dumping generated prompt flow to local folder...', 'Copilot')

        function_arguments = json.loads(getattr(response.choices[0].message.function_call, "arguments", ""))
        dump_flow(**function_arguments, target_folder=self.local_folder)

        print_info_func(f'Congratulations! Your prompt flow was successfully dumped to local folder: {self.local_folder}', 'Copilot')
        print_info_func(f'How the flow works: {function_arguments["explaination"]}', 'Copilot')
