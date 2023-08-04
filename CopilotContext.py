import os
import json
import openai
import re
from pathlib import Path
from json import JSONDecodeError
from datetime import datetime
from dotenv import load_dotenv

def generate_random_folder_name():
    # Get the current timestamp as a string
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    folder_name = f"generated_flow_{timestamp}"

    return folder_name

def dump_flow(flow_yaml, explaination, python_functions, prompts, requirements, target_folder, print_info_func, flow_inputs_schema=None, flow_outputs_schema=None):
    '''
    dump flow yaml and explaination and python functions into different files
    '''
    if not os.path.exists(target_folder):
        os.mkdir(target_folder)
        print_info_func(f'Create flow folder:{target_folder}')

    print_info_func('Dumping flow.day.yaml')
    with open(f'{target_folder}\\flow.dag.yaml', 'w', encoding="utf-8") as f:
        f.write(flow_yaml)

    print_info_func('Dumping flow.explaination.txt')
    with open(f'{target_folder}\\flow.explaination.txt', 'w', encoding="utf-8") as f:
        f.write(explaination)

    print_info_func('Dumping python functions')
    for func in python_functions:
        fo =  func if type(func) == dict else json.loads(func)
        for k,v in fo.items():
            with open(f'{target_folder}\\{k}.py', 'w', encoding="utf-8") as f:
                f.write(v)

    print_info_func('Dumping prompts')
    for prompt in prompts:
        po = prompt if type(prompt) == dict else json.loads(prompt)
        for k,v in po.items():
            with open(f'{target_folder}\\{k}.jinja2', 'w', encoding="utf-8") as f:
                f.write(v)

    print_info_func('Dumping requirements.txt')
    with open(f'{target_folder}\\requirements.txt', 'w', encoding="utf-8") as f:
        f.write(requirements)

def read_local_file(path, print_info_func):
    if not os.path.exists(path):
        print_info_func(f'{path} does not exists')
        return
    else:
        print_info_func(f'read content from file:{path}')
        with open(path, 'r', encoding="utf-8") as f:
            return f.read()
        
def read_local_folder(path, print_info_func, included_file_types=['.ipynb', '.py']):
    if not os.path.exists(path):
        print_info_func(f'{path} does not exists')
        return
    else:
        print_info_func(f'read content from folder:{path}')
        file_contents_dict = {}

        for root, _, files in os.walk(path):
            for file_name in files:
                file_ext = Path(file_name).suffix
                if not file_ext in included_file_types:
                    continue
                subfolder_name = os.path.relpath(root, start=path)
                if subfolder_name == '.':
                    subfolder_name = ''  # Use an empty string for files in the root folder
                else:
                    subfolder_name += '/'  # Add a slash to separate subfolder name and file name
                file_path = os.path.join(root, file_name)
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_content = file.read()
                    key = subfolder_name + file_name
                    file_contents_dict[key] = file_content
        return json.dumps(file_contents_dict)

def read_flow_from_local_folder(path, print_info_func):
    if os.path.isfile(path):
        return read_local_file(path, print_info_func)
    print_info_func(f'read existing flow from folder:{path}')
    return read_local_folder(path, print_info_func, included_file_types=['.yaml', '.py', '.jinja2', '.txt'])

def read_flow_from_local_file(path, print_info_func):
    if os.path.isdir(path):
        return read_local_folder(path, print_info_func)
    print_info_func(f'read existing flow from file:{path}')
    return read_local_file(path, print_info_func)

def dump_sample_inputs(sample_inputs, target_folder, print_info_func):
    if not os.path.exists(target_folder):
        print_info_func(f'Before generate the sample inputs, please generate the flow first')
        return
    
    if sample_inputs is None:
        print_info_func('Failed to generate inputs for your flow, please try again')
    else:
        with open(f'{target_folder}\\flow.sample_inputs.jsonl', 'w', encoding="utf-8") as f:
            for sample_input in sample_inputs:
                if sample_input is None:
                    continue
                else:
                    sample_input = sample_input if type(sample_input) == str else json.dumps(sample_input)
                f.write(sample_input + '\n')
        print_info_func(f'Generated {len(sample_inputs)} sample inputs for your flow. And dump them into {target_folder}\\flow.sample_inputs.jsonl')

def dump_evaluation_flow(sample_inputs, flow_outputs_schema, flow_folder, eval_flow_folder, print_info_func):
    if not os.path.exists(flow_folder):
        print_info_func(f'Before generate the evaluation flow, please generate the flow first')
        return
    
    if not os.path.exists(eval_flow_folder):
        os.mkdir(eval_flow_folder)
        print_info_func(f'Create flow folder:{eval_flow_folder}')

    if sample_inputs is None:
        print_info_func('No sample inputs generated, you may need to generate the sample inputs manually')

    print_info_func('Dumping evalutaion flow...')
    evaluation_flow_template_folder = '.\evaluation_template'
    file_list = os.listdir(evaluation_flow_template_folder)
    import shutil
    for file_name in file_list:
        source_file_path = os.path.join(evaluation_flow_template_folder, file_name)
        destination_file_path = os.path.join(eval_flow_folder, file_name)
        shutil.copy(source_file_path, destination_file_path)

    # currently only support one output
    flow_outputs_schema = flow_outputs_schema[0]
    first_output_column = ''

    with open(f'{eval_flow_folder}\\flow.sample_inputs.jsonl', 'w', encoding="utf-8") as f:
        for sample_input in sample_inputs:
            if sample_input is None:
                continue
            else:
                sample_input = json.loads(sample_input)
                flow_outputs_schema = flow_outputs_schema if type(flow_outputs_schema) == dict else json.loads(flow_outputs_schema)
                for k,v in flow_outputs_schema.items():
                    sample_input[k] = 'expected_output'
                first_output_column = next(iter(flow_outputs_schema)) if flow_outputs_schema else ''
            f.write(json.dumps(sample_input) + '\n')

    goundtruth_name = f'data.{first_output_column}'
    prediction_name = f'run.outputs.{first_output_column}'

    sdk_eval_sample_code = f"""
import promptflow as pf
import json

# Set flow path and run input data
flow = "{flow_folder}" # set the flow directory
data= "{eval_flow_folder}\\\\flow.sample_inputs.jsonl" # set the data file

# create a run
base_run = pf.run(
    flow=flow,
    data=data,
)

# set eval flow path
eval_flow = "{eval_flow_folder}"
data= "{eval_flow_folder}\\\\flow.sample_inputs.jsonl"

# run the flow with exisiting run
eval_run = pf.run(
    flow=eval_flow,
    data=data,
    run=base_run,
    column_mapping={{"groundtruth": "${{{goundtruth_name}}}","prediction": "${{{prediction_name}}}"}},  # map the url field from the data to the url input of the flow
)

# stream the run until it's finished
pf.stream(eval_run)

# get the inputs/outputs details of a finished run.
details = pf.get_details(eval_run)
details.head(10)

# view the metrics of the eval run
metrics = pf.get_metrics(eval_run)
print(json.dumps(metrics, indent=4))

# visualize both the base run and the eval run
pf.visualize([base_run, eval_run])

"""
    with open(f'{eval_flow_folder}\\promptflow_sdk_sample_code.py', 'w', encoding="utf-8") as f: 
        f.write(sdk_eval_sample_code)

    print_info_func(f'Dumped evalutaion flow to {eval_flow_folder}. You can refer to the sample code in {eval_flow_folder}\\promptflow_sdk_sample_code.py to run the eval flow.')

def extract_functions_arguments(function_call):
    try:
        return json.loads(function_call)
    except JSONDecodeError as ex:
        pattern = r'\\\n'
        updated_function_call = re.sub(pattern, r'\\n', str(function_call))
        if updated_function_call == function_call:
            raise ex
        return extract_functions_arguments(updated_function_call)
        

class CopilotContext:
    def __init__(self) -> None:
        load_dotenv('pfcopilot.env')
        self.use_aoai = os.environ.get("AOAI_BY_DEFAULT", "true").lower() == "true"
        self.aoai_key = os.environ.get("AOAI_API_KEY")
        self.aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
        self.aoai_api_base = os.environ.get("AOAI_API_BASE")

        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_MODEL")

        self.local_folder = generate_random_folder_name()
        
        with open('system_instruction_v2.txt', 'r', encoding='utf-8') as f:
            self.system_instruction = f.read()

        self.messages = [
            {'role':'system', 'content': self.system_instruction},
        ]

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
                        'flow_inputs_schema': {
                            'type': 'array',
                            'description': 'flow inputs schemas',
                            'items': {
                                'type': 'string'
                            }
                        },
                        'flow_outputs_schema': {
                            'type': 'array',
                            'description': 'flow outputs schemas',
                            'items': {
                                'type': 'string'
                            }
                        },
                    },
                    'required': ['flow_yaml', 'explaination', 'python_functions', 'prompts', 'requirements']
                }
            },
            {
                'name': 'read_local_file',
                'description': 'read file content from local disk',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                            'description': 'path to local file'
                        }
                    },
                    'required': ['path']
                }
            },
            {
                'name': 'read_local_folder',
                'description': 'read all files content from local folder',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                            'description': 'path to local folder'
                        }
                    },
                    'required': ['path']
                }
            },
            {
                'name': 'read_flow_from_local_file',
                'description': 'read an existing flow from a local file',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                            'description': 'path to local file'
                        }
                    },
                    'required': ['path']
                }
            },
            {
                'name': 'read_flow_from_local_folder',
                'description': 'read an existing flow from local folder',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'path': {
                            'type': 'string',
                            'description': 'path to local folder'
                        }
                    },
                    'required': ['path']
                }
            },
            {
                'name': 'dump_sample_inputs',
                'description': 'dump generate sample inputs into local file',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'sample_inputs': {
                            'type': 'array',
                            'description': 'generated sample inputs',
                            'items': {
                                'type': 'string'
                            }
                        },
                    },
                    'required': ['sample_inputs']
                }
            },
            {
                'name': 'dump_evaluation_flow',
                'description': 'create evaluation flow',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'sample_inputs': {
                            'type': 'array',
                            'description': 'generated sample inputs',
                            'items': {
                                'type': 'string'
                            }
                        },
                        'flow_outputs_schema': {
                            'type': 'array',
                            'description': 'flow outputs schemas',
                            'items': {
                                'type': 'string'
                            }
                        },
                    },
                    'required': ['sample_inputs', 'flow_outputs_schema']
                }
            },
        ]

    def check_env(self):
        if self.use_aoai:
            if not self.aoai_key or not self.aoai_deployment or not self.aoai_api_base:
                return False, "You configured to use AOAI, but one or more of the following environment variables were not set: AOAI_API_KEY, AOAI_DEPLOYMENT, AOAI_API_BASE"
            else:
                openai.api_key = self.aoai_key
                openai.api_type = "azure"
                openai.api_base = self.aoai_api_base
                openai.api_version = "2023-07-01-preview"
                return True, ""
        else:
            if not self.openai_key or not self.openai_model:
                return False, "You configured to use OPENAI, but one or more of the following environment variables were not set: OPENAI_API_KEY, OPENAI_API_KEY"
            else:
                openai.api_key = self.openai_key
                return True, ""

    def reset(self):
        self.messages = [
            {'role':'system', 'content': self.system_instruction},
        ]
        self.local_folder = generate_random_folder_name()

    def format_request_dict(self, function_call=None):
        request_args_dict = {
            "messages": self.messages,
            "functions": self.my_custom_functions,
            "stream": False,
            "temperature": 0
        }

        if function_call:
            request_args_dict['function_call'] = function_call

        if self.use_aoai:
            request_args_dict['engine'] = self.aoai_deployment
        else:
            request_args_dict['model'] = self.openai_model

        return request_args_dict         

    def ask_gpt(self, content, print_info_func):
        self.messages.append({'role':'user', 'content':content})
        request_args_dict = self.format_request_dict('auto')
        
        response = openai.ChatCompletion.create(**request_args_dict)
        self.parse_gpt_response(response, print_info_func)

    def parse_gpt_response(self, response, print_info_func):
        response_ms = response.response_ms
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        message = getattr(response.choices[0].message, "content", "")
        finish_reason = response.choices[0].finish_reason

        print_info_func(f'Get response from ChatGPT in {response_ms} ms!')
        print_info_func(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

        if message:
            self.messages.append({'role':response.choices[0].message.role, 'content':message})
            print_info_func(f'{message}')
        
        if finish_reason == 'function_call':
            function_call = getattr(response.choices[0].message.function_call, "arguments", "") if hasattr(response.choices[0].message, 'function_call') else ""
            function_name = getattr(response.choices[0].message.function_call, "name", "")
            if function_name == 'dump_flow':
                function_arguments = extract_functions_arguments(function_call)
                dump_flow(**function_arguments, target_folder=self.local_folder, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": ''})
            elif function_name == 'read_local_file':
                function_arguments = extract_functions_arguments(function_call)
                file_content = read_local_file(**function_arguments, print_info_func=print_info_func)
                if not file_content:
                    print_info_func('you ask me to read code from a file, but the file does not exists')
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":file_content})
                    request_args_dict = self.format_request_dict('auto')
                    new_response = openai.ChatCompletion.create(**request_args_dict)
                    self.parse_gpt_response(new_response, print_info_func)
            elif function_name == 'read_local_folder':
                function_arguments = extract_functions_arguments(function_call)
                files_content = read_local_folder(**function_arguments, print_info_func=print_info_func)
                if not files_content:
                    print_info_func('you ask me to read code from a folder, but the folder does not exists')
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":files_content})
                    request_args_dict = self.format_request_dict('auto')
                    new_response = openai.ChatCompletion.create(**request_args_dict)
                    self.parse_gpt_response(new_response, print_info_func)
            elif function_name == 'dump_sample_inputs':
                function_arguments = extract_functions_arguments(function_call)
                dump_sample_inputs(**function_arguments, target_folder=self.local_folder, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": ""})
            elif function_name == 'dump_evaluation_flow':
                function_arguments = extract_functions_arguments(function_call)
                dump_evaluation_flow(**function_arguments, flow_folder=self.local_folder, eval_flow_folder=self.local_folder + '\\evaluation', print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": ""})
            elif function_name == 'read_flow_from_local_file':
                function_arguments = extract_functions_arguments(function_call)
                file_content = read_flow_from_local_file(**function_arguments, print_info_func=print_info_func)
                if not file_content:
                    print_info_func('you ask me to read flow from a file, but the file does not exists')
                else:
                    self.local_folder = os.path.dirname(function_arguments['path'])
                    self.messages.append({"role": "function", "name": function_name, "content":file_content})
                    request_args_dict = self.format_request_dict('auto')
                    new_response = openai.ChatCompletion.create(**request_args_dict)
                    self.parse_gpt_response(new_response, print_info_func)
            elif function_name == 'read_flow_from_local_folder':
                function_arguments = extract_functions_arguments(function_call)
                self.local_folder = function_arguments['path']
                files_content = read_flow_from_local_folder(**function_arguments, print_info_func=print_info_func)
                if not files_content:
                    print_info_func('you ask me to read flow from a folder, but the folder does not exists')
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":files_content})
                    request_args_dict = self.format_request_dict('auto')
                    new_response = openai.ChatCompletion.create(**request_args_dict)
                    self.parse_gpt_response(new_response, print_info_func)
            elif function_name == 'python':
                execution_result = {}
                exec(function_call, globals(), execution_result)
                str_result = {}
                for key, value in execution_result.items():
                    str_result[key] = str(value)
                self.messages.append({"role": "function", "name": function_name, "content":json.dumps(str_result)})
                request_args_dict = self.format_request_dict('auto')
                new_response = openai.ChatCompletion.create(**request_args_dict)
                self.parse_gpt_response(new_response, print_info_func)
            else:
                raise Exception(f'Invalid function name:{function_name}')