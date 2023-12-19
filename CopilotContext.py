import os
import json
import re
import yaml
import asyncio
from pathlib import Path
from json import JSONDecodeError
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types import CompletionUsage

from jinja2 import Environment, FileSystemLoader
from logging_util import get_logger
import function_calls
from token_utils import num_tokens_from_messages, num_tokens_from_functions, num_tokens_from_completions

logger = get_logger()

class CopilotContext:
    def __init__(self) -> None:
        self.script_directory = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(self.script_directory, 'pfcopilot.env'))
        self.use_aoai = os.environ.get("AOAI_BY_DEFAULT", "true").lower() == "true"
        self.aoai_key = os.environ.get("AOAI_API_KEY")
        self.aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
        self.aoai_api_base = os.environ.get("AOAI_API_BASE")

        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_MODEL")

        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_prompt_tokens = 0

        self.flow_folder = None
        self.flow_description = None
        self.flow_yaml = None

        jinja_env = Environment(loader=FileSystemLoader(self.script_directory), variable_start_string='[[', variable_end_string=']]')
        self.copilot_instruction_template = jinja_env.get_template('prompts/copilot_instruction.jinja2')
        self.rewrite_user_input_template = jinja_env.get_template('prompts/rewrite_user_input.jinja2')
        self.refine_python_code_template = jinja_env.get_template('prompts/refine_python_code.jinja2')
        self.find_python_package_template = jinja_env.get_template('prompts/find_python_package.jinja2')
        self.summarize_flow_name_template = jinja_env.get_template('prompts/summarize_flow_name.jinja2')
        self.understand_flow_template = jinja_env.get_template('prompts/understand_flow_instruction.jinja2')
        self.json_string_fixer_template = jinja_env.get_template('prompts/json_string_fixer.jinja2')
        self.yaml_string_fixer_template = jinja_env.get_template('prompts/yaml_string_fixer.jinja2')
        self.function_call_instruction_template = jinja_env.get_template('prompts/function_call_instruction.jinja2')
        self.gen_sample_inputs_template = jinja_env.get_template('prompts/gen_sample_data.jinja2')
        self.gen_eval_flow_inputs_template = jinja_env.get_template('prompts/gen_eval_flow_inputs.jinja2')
        self.gen_eval_flow_functions = jinja_env.get_template('prompts/gen_eval_flow_functions.jinja2')

        self.system_instruction = self.copilot_instruction_template.render()
        self.messages = []

        self.copilot_general_function_calls = [
            function_calls.dump_flow,
            function_calls.read_local_file,
            function_calls.read_local_folder,
            function_calls.read_flow_from_local_file,
            function_calls.read_flow_from_local_folder,
            function_calls.dump_sample_inputs,
            function_calls.dump_evaluation_flow,
            function_calls.upsert_flow_files
        ]

    @property
    def total_money_cost(self):
        return self.prompt_tokens * 0.000003 + self.completion_tokens * 0.00000004

    def check_env(self):
        if self.use_aoai:
            if not self.aoai_key or not self.aoai_deployment or not self.aoai_api_base:
                return False, "You configured to use AOAI, but one or more of the following environment variables were not set: AOAI_API_KEY, AOAI_DEPLOYMENT, AOAI_API_BASE"
            else:
                self.llm_client = AsyncAzureOpenAI(
                    azure_endpoint=self.aoai_api_base,
                    api_version="2023-07-01-preview",
                    api_key=self.aoai_key)
                return True, ""
        else:
            if not self.openai_key or not self.openai_model:
                return False, "You configured to use OPENAI, but one or more of the following environment variables were not set: OPENAI_API_KEY, OPENAI_API_KEY"
            else:
                self.llm_client = AsyncOpenAI(api_key=self.openai_key)
                return True, ""

    def reset(self):
        self.messages = []
        self.flow_folder = None
        self.flow_yaml = None
        self.flow_description = None
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_prompt_tokens = 0

    async def _ask_openai_async(self, messages=[], functions=None, function_call=None, stream=False):
        function_calls = {}
        if functions:
            function_calls['functions'] = functions

        if functions and function_call:
            function_calls['function_call'] = function_call

        if self.use_aoai:
            deployment = self.aoai_deployment
        else:
            deployment = self.openai_model

        response = await self.llm_client.chat.completions.create(
            messages=messages,
            model=deployment,
            stream=stream,
            **function_calls
        )

        if not stream:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            self.completion_tokens += completion_tokens
            self.prompt_tokens += prompt_tokens
            self.last_completion_tokens += completion_tokens
            self.last_prompt_tokens += prompt_tokens

            logger.info(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

        return response

    async def _safe_load_flow_yaml(self, yaml_str):
        try:
            parsed_flow_yaml = await self._smart_yaml_loads(yaml_str)
            if 'nodes' in parsed_flow_yaml:
                for node in parsed_flow_yaml['nodes']:
                    if 'type' in node and node['type'] == 'llm':
                        if 'inputs' in node and 'prompt' in node['inputs']:
                            del node['inputs']['prompt']
            if 'node_variants' in parsed_flow_yaml:
                for _, v in parsed_flow_yaml['node_variants'].items():
                    for _, variant in v['variants'].items():
                        if 'inputs' in variant['node'] and 'prompt' in variant['node']['inputs']:
                            del variant['node']['inputs']['prompt']
            self.flow_yaml = yaml.dump(parsed_flow_yaml, allow_unicode=True, sort_keys=False, indent=2)
            return parsed_flow_yaml
        except Exception as ex:
            logger.error(ex)
            raise ex

    async def _rewrite_user_input(self, user_input):
        # construct conversation message, only keep the last four messages for user and assistant
        cur_len = 0
        conversation_message_array = []
        for message in reversed(self.messages):
            role = message['role']
            if role != 'system' and role != 'function' and cur_len < 4:
                cur_len += 1
                if role == 'user':
                    conversation_message_array.append(f'User: {message["content"]}')
                else:
                    conversation_message_array.append(f'PF copilot: {message["content"]}')
        conversation_message_array.reverse()
        conversation_message = '\n'.join(conversation_message_array)

        rewrite_user_input_instruction = self.rewrite_user_input_template.render(conversation=conversation_message)
        chat_message = [
            {'role':'system', 'content': rewrite_user_input_instruction},
            {'role':'user', 'content': user_input}
        ]
        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        logger.info(f"rewrite_user_input: {message}")
        return message

    async def _refine_python_code(self, python_code):
        refine_python_code_instruction = self.refine_python_code_template.render()
        chat_message = [
            {'role':'system', 'content': refine_python_code_instruction},
            {'role':'user', 'content': python_code}
        ]

        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        return message

    async def _find_dependent_python_packages(self, python_code):
        find_dependent_python_packages_instruction = self.find_python_package_template.render()
        chat_message = [
            {'role':'system', 'content': find_dependent_python_packages_instruction},
            {'role':'user', 'content': python_code}
        ]

        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "").replace(' ', '')
        packages = []
        for p in message.split(','):
            if p != 'None':
                packages.append(p)
        return packages

    async def _summarize_flow_name(self, flow_description):
        summarize_flow_name_instruction = self.summarize_flow_name_template.render()
        chat_message = [
            {'role':'system', 'content': summarize_flow_name_instruction},
            {'role':'user', 'content': flow_description}
        ]

        response = await self._ask_openai_async(messages=chat_message)
        message = getattr(response.choices[0].message, "content", "")
        return message

    async def _fix_json_string_and_loads(self, json_string, error, max_retry=3):
        try:
            fix_json_string_instruction = self.json_string_fixer_template.render(original_string=json_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_json_string_instruction},
            ]
            response = await self._ask_openai_async(messages=chat_message)
            message = getattr(response.choices[0].message, "content", "")
            return json.loads(message)
        except JSONDecodeError as ex:
            logger.error(f'Failed to fix json string {json_string} with error {error}')
            if max_retry > 0 and message != json_string:
                return await self._fix_json_string_and_loads(message, str(ex), max_retry=max_retry-1)
            raise ex

    async def _fix_yaml_string_and_loads(self, yaml_string, error, max_retry=3):
        try:
            fix_yaml_string_instruction = self.yaml_string_fixer_template.render(original_string=yaml_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_yaml_string_instruction},
            ]
            response = await self._ask_openai_async(messages=chat_message)
            message = getattr(response.choices[0].message, "content", "")
            return yaml.safe_load(message)
        except yaml.MarkedYAMLError as ex:
            logger.error(f'Failed to fix yaml string {yaml_string} with error {error}')
            if max_retry > 0 and message != yaml_string:
                return await self._fix_yaml_string_and_loads(message, str(ex), max_retry=max_retry-1)
            raise ex

    async def _smart_yaml_loads(self, yaml_string):
        try:
            return yaml.safe_load(yaml_string)
        except yaml.MarkedYAMLError as ex:
            return await self._fix_yaml_string_and_loads(yaml_string, str(ex))

    async def _smart_json_loads(self, json_string):
        try:
            return json.loads(json_string)
        except JSONDecodeError as ex:
            pattern = r'\\\n'
            updated_function_call = re.sub(pattern, r'\\n', str(json_string))
            if updated_function_call == json_string:
                logger.error(f'Failed to load json string {json_string}')
                return await self._fix_json_string_and_loads(json_string, str(ex))
            else:
                return await self._smart_json_loads(updated_function_call)

    async def ask_gpt_async(self, content, print_info_func):
        self.last_prompt_tokens = 0
        self.last_tokens = 0

        rewritten_user_intent = await self._rewrite_user_input(content)
        potential_function_calls = self.copilot_general_function_calls

        if self.flow_yaml:
            system_message = self.understand_flow_template.render(flow_directory=self.flow_folder, flow_yaml_path=os.path.join(self.flow_folder, 'flow.dag.yaml'), flow_yaml=self.flow_yaml, flow_description=self.flow_description)
            self.messages[0] = {'role':'system', 'content': system_message}
            potential_function_calls = [
                function_calls.dump_sample_inputs,
                function_calls.dump_evaluation_flow,
                function_calls.upsert_flow_files]
        elif len(self.messages) == 0:
            self.messages.append({'role':'system', 'content':self.system_instruction})
            potential_function_calls = [
                function_calls.dump_flow,
                function_calls.read_flow_from_local_file,
                function_calls.read_flow_from_local_folder,
                function_calls.read_local_file,
                function_calls.read_local_folder]

        self.messages.append({'role':'user', 'content':rewritten_user_intent})
        self.messages.append({'role':'system', 'content': self.function_call_instruction_template.render(functions=','.join([f['name'] for f in potential_function_calls]))})

        prompt_tokens = num_tokens_from_messages(self.messages) + num_tokens_from_functions(potential_function_calls)
        self.prompt_tokens += prompt_tokens
        self.last_prompt_tokens += prompt_tokens
        response = await self._ask_openai_async(messages=self.messages, functions=potential_function_calls, function_call='auto', stream=True)
        await self.parse_gpt_response(response, print_info_func)

        # clear function message if we have already got the flow
        if self.flow_yaml:
            self._clear_function_message()

        # clear function call messages since we will append it every time
        self._clear_system_message()

        logger.info(f'answer finished. completion tokens: {self.completion_tokens}, prompt tokens: {self.prompt_tokens}, last completion tokens: {self.last_completion_tokens}, last prompt tokens: {self.last_prompt_tokens}')

    async def parse_gpt_response(self, response, print_info_func):
        role = "assistant"
        message = ""
        function_call = ""
        function_name = ""
        early_stop = False
        next_possible_function_calls = None
        function_call_choice = 'auto'

        async for chunk in response:
            if len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    cur_message = delta.content
                    message += cur_message
                    print_info_func(cur_message)
                if delta.function_call:
                    if delta.function_call.name:
                        function_name = delta.function_call.name
                    if delta.function_call.arguments:
                        function_call+= delta.function_call.arguments
                if delta.role:
                    role = delta.role
                finish_reason = chunk.choices[0].finish_reason

        if message:
            self.messages.append({'role':role, 'content':message})

        completion_tokens = num_tokens_from_completions(message + function_call)
        self.completion_tokens += completion_tokens
        self.last_completion_tokens += completion_tokens

        if function_call != "":
            if function_name == 'dump_flow':
                function_arguments = await self._smart_json_loads(function_call)
                flow_folder = await self.dump_flow(**function_arguments, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f'{flow_folder}'})
                early_stop = True
            elif function_name == 'read_local_file':
                function_arguments = await self._smart_json_loads(function_call)
                file_content = self.read_local_file(**function_arguments, print_info_func=print_info_func)
                if not file_content:
                    print_info_func('\nyou ask me to read code from a file, but the file does not exists')
                    early_stop = True
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":file_content})
                    self.messages.append({"role": "system", "content": "You have read the file content, understand it first and then determine your next step."})
                    next_possible_function_calls = [function_calls.dump_flow, function_calls.upsert_flow_files]
            elif function_name == 'read_local_folder':
                function_arguments = await self._smart_json_loads(function_call)
                files_content = self.read_local_folder(**function_arguments, print_info_func=print_info_func)
                if not files_content:
                    print_info_func('\nyou ask me to read code from a folder, but the folder does not exists')
                    early_stop = True
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":files_content})
                    self.messages.append({"role": "system", "content": "You have read all the files in the folder, understand it first and then determine your next step."})
                    next_possible_function_calls = [function_calls.dump_flow, function_calls.upsert_flow_files]
            elif function_name == 'dump_sample_inputs':
                function_arguments = await self._smart_json_loads(function_call)
                sample_input_file = await self.dump_sample_inputs(**function_arguments, target_folder=self.flow_folder, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f"{sample_input_file}"})
                early_stop = True
            elif function_name == 'dump_evaluation_flow':
                function_arguments = await self._smart_json_loads(function_call)
                evaluation_flow_folder = await self.dump_evaluation_flow(**function_arguments, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f"{evaluation_flow_folder}"})
            elif function_name == 'read_flow_from_local_file':
                function_arguments = await self._smart_json_loads(function_call)
                file_content = self.read_flow_from_local_file(**function_arguments, print_info_func=print_info_func)
                if not file_content:
                    print_info_func('\nyou ask me to read flow from a file, but the file does not exists')
                    early_stop = True
                else:
                    self.flow_folder = os.path.dirname(function_arguments['path'])
                    self.messages.append({"role": "function", "name": function_name, "content":file_content})
                    next_possible_function_calls = [function_calls.dump_flow_definition_and_description]
                    function_call_choice = {'name':'dump_flow_definition_and_description'}
            elif function_name == 'read_flow_from_local_folder':
                function_arguments = await self._smart_json_loads(function_call)
                self.flow_folder = function_arguments['path']
                files_content = self.read_flow_from_local_folder(**function_arguments, print_info_func=print_info_func)
                if not files_content:
                    print_info_func('\nyou ask me to read flow from a folder, but the folder does not exists')
                    early_stop = True
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":files_content})
                    next_possible_function_calls = [function_calls.dump_flow_definition_and_description]
                    function_call_choice = {'name':'dump_flow_definition_and_description'}
            elif function_name == 'dump_flow_definition_and_description':
                function_arguments = await self._smart_json_loads(function_call)
                self.dump_flow_definition_and_description(**function_arguments, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": ""})
                next_possible_function_calls = [function_calls.dump_sample_inputs, function_calls.dump_evaluation_flow, function_calls.upsert_flow_files]
            elif function_name == 'upsert_flow_files':
                function_arguments = await self._smart_json_loads(function_call)
                await self.upsert_flow_files(**function_arguments, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": ""})
                early_stop = True
            else:
                logger.info(f'GPT try to call unavailable function: {function_name}')
                self.messages.append({"role": "system", "content":"do not try to call functions that does not exist! Call the function that exists!"})

        if finish_reason != 'stop' and not early_stop:
            prompt_tokens = num_tokens_from_messages(self.messages) + num_tokens_from_functions(next_possible_function_calls)
            self.prompt_tokens += prompt_tokens
            self.last_prompt_tokens += prompt_tokens
            new_response = await self._ask_openai_async(messages=self.messages, functions=next_possible_function_calls, function_call=function_call_choice, stream=True)
            await self.parse_gpt_response(new_response, print_info_func)

    def _clear_function_message(self):
        '''
        clear some function message from messages to reduce chat history size
        '''
        for message in self.messages:
            if message['role'] == 'function' and message['name'] in ['read_local_file', 'read_local_folder', 'read_flow_from_local_file', 'read_flow_from_local_folder', 'upsert_flow_files']:
                self.messages.remove(message)

    def _clear_system_message(self):
        '''
        clear some system message from messages to reduce chat history size
        '''
        for message in self.messages:
            if message['role'] == 'system' and message['content'].startswith("You can also calling the functions listed in [FUNCTIONS] directly on behalf of the user"):
                self.messages.remove(message)

    # region functions
    async def dump_flow(self, print_info_func, flow_yaml, explaination=None, python_functions=None, prompts=None, flow_inputs_schema=None, flow_outputs_schema=None, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_flow reasoning: {reasoning}')

        if not self.flow_folder:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            flow_name = await self._summarize_flow_name(explaination) if explaination else 'flow_generated'
            self.flow_folder = f'flow_{flow_name}_{timestamp}'

        target_folder = self.flow_folder

        if not os.path.exists(target_folder):
            os.mkdir(target_folder)
            logger.info(f'Create flow folder:{target_folder}')

        parsed_flow_yaml = await self._safe_load_flow_yaml(flow_yaml)
        python_nodes_path_dict = {}
        python_path_nodes_dict = {}
        llm_nodes_path_dict = {}
        llm_path_nodes_dict = {}
        for node in parsed_flow_yaml['nodes']:
            if node['type'] == 'python':
                python_nodes_path_dict[node['name']] = node['source']['path']
                python_path_nodes_dict[node['source']['path']] = node['name']
            elif node['type'] == 'llm':
                llm_nodes_path_dict[node['name']] = node['source']['path']
                llm_path_nodes_dict[node['source']['path']] = node['name']

        logger.info('Dumping flow.dag.yaml')
        with open(f'{target_folder}\\flow.dag.yaml', 'w', encoding="utf-8") as f:
            yaml.dump(parsed_flow_yaml, f, allow_unicode=True, sort_keys=False, indent=2)

        if explaination:
            logger.info('Dumping flow.explaination.txt')
            with open(f'{target_folder}\\flow.explaination.txt', 'w', encoding="utf-8") as f:
                f.write(explaination)
                self.flow_description = explaination

        requirement_python_packages = set()
        if python_functions and len(python_functions) > 0:
            logger.info('Dumping python functions')
            for func in python_functions:
                python_node_name = func['name']
                python_code = func['content']
                python_file_name = None
                if python_node_name in python_path_nodes_dict:
                    python_file_name = python_path_nodes_dict[python_node_name]['source']['path']
                elif python_node_name in python_nodes_path_dict:
                    python_file_name = python_nodes_path_dict[python_node_name]
                if python_file_name:
                    with open(f'{target_folder}\\{python_file_name}', 'w', encoding="utf-8") as f:
                        refined_codes = await self._refine_python_code(python_code)
                        f.write(refined_codes)
                        python_packages = await self._find_dependent_python_packages(refined_codes)
                        requirement_python_packages.update(python_packages)
                else:
                    logger.info(f'python function for {python_node_name} is not used in the flow, skip dumping it')

        if prompts and len(prompts) > 0:
            logger.info('Dumping prompts')
            for prompt in prompts:
                prompt_node_name = prompt['name']
                prompt_content = prompt['content']
                prompt_file_name = None
                if prompt_node_name in llm_path_nodes_dict:
                    prompt_file_name = llm_path_nodes_dict[prompt_node_name]['source']['path']
                elif prompt_node_name in llm_nodes_path_dict:
                    prompt_file_name = llm_nodes_path_dict[prompt_node_name]
                if prompt_file_name:
                    with open(f'{target_folder}\\{prompt_file_name}', 'w', encoding="utf-8") as f:
                        f.write(prompt_content)
                else:
                    logger.info(f'Prompt {prompt_node_name} is not used in the flow, skip dumping it')

        if requirement_python_packages and len(requirement_python_packages) > 0:
            logger.info('Dumping requirements.txt')
            with open(f'{target_folder}\\requirements.txt', 'w', encoding="utf-8") as f:
                f.write('\n'.join(requirement_python_packages))

        print_info_func(f'\nfinish dumping flow to folder:{self.flow_folder}')
        return self.flow_folder

    def read_local_file(self, print_info_func, path=None, file_path=None, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_local_file reasoning: {reasoning}')

        path = path if path else file_path
        if os.path.isdir(path):
            return self.read_local_folder(path=path, print_info_func=print_info_func)

        if not os.path.exists(path):
            logger.info(f'{path} does not exists')
            return
        else:
            logger.info(f'read content from file:{path}')
            with open(path, 'r', encoding="utf-8") as f:
                return f.read()

    def read_local_folder(self, print_info_func, path=None, file_path=None, included_file_types=['.py'], reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_local_folder reasoning: {reasoning}')

        path = path if path else file_path
        if os.path.isfile(path):
            return self.read_local_file(path=path, print_info_func=print_info_func)

        if not os.path.exists(path):
            logger.info(f'{path} does not exists')
            return
        else:
            logger.info(f'read content from folder:{path}')
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

    def read_flow_from_local_folder(self, path, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_flow_from_local_folder reasoning: {reasoning}')

        if os.path.isfile(path):
            return self.read_local_file(path=path, print_info_func=print_info_func)
        logger.info(f'read existing flow from folder:{path}')
        self.flow_folder = path
        return self.read_local_folder(path=path, print_info_func=print_info_func, included_file_types=['.yaml'])

    def read_flow_from_local_file(self, path, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_flow_from_local_file reasoning: {reasoning}')

        if os.path.isdir(path):
            return self.read_flow_from_local_folder(path, print_info_func)
        logger.info(f'read existing flow from file:{path}')
        self.flow_folder = os.path.dirname(path)
        return self.read_local_file(path=path, print_info_func=print_info_func)

    async def dump_sample_inputs(self, file_name, total_count, extra_requirements, target_folder, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_sample_inputs reasoning: {reasoning}')

        if not target_folder or not os.path.exists(target_folder):
            print_info_func(f'\nBefore generate the sample inputs, please generate or provide the flow first')
            return

        sample_inputs_file = f'{target_folder}\\{file_name}'
        if not total_count or total_count < 1 or total_count > 1000:
            logger.info(f'invalid sample inputs count: {total_count}, Set to default 5')
            total_count = 5

        system_instruction = self.gen_sample_inputs_template.render(flow_yaml=self.flow_yaml)
        user_input = f"Generate bulktest data with {total_count} items for the flow and then dump the data to my local disk for me."
        if extra_requirements:
            user_input += extra_requirements

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_input},
            ]
        
        response = await self._ask_openai_async(messages=messages, functions=[function_calls.generate_sample_inputs], function_call={"name": "generate_sample_inputs"})
        function_call = getattr(response.choices[0].message.function_call, "arguments", "") if hasattr(response.choices[0].message, 'function_call') else ""
        function_arguments = await self._smart_json_loads(function_call)
        sample_inputs = function_arguments['sample_inputs']

        if sample_inputs is None:
            print_info_func('\nFailed to generate inputs for your flow, please try again')
        else:
            with open(sample_inputs_file, 'w', encoding="utf-8") as f:
                for sample_input in sample_inputs:
                    if sample_input is None:
                        continue
                    else:
                        sample_input = await self._smart_json_loads(sample_input) if type(sample_input) == str else sample_input
                        sample_input = json.dumps(sample_input)
                    f.write(sample_input + '\n')
            print_info_func(f'\nGenerated {len(sample_inputs)} sample inputs for your flow. And dump them into {target_folder}\\flow.sample_inputs.jsonl')

        return sample_inputs_file

    async def dump_evaluation_inputs(self, evaluation_inputs, eval_flow_folder, print_info_func, **kwargs):
        evaluation_test_data_name = 'evaluation_test_data.jsonl'

        with open(f'{eval_flow_folder}\\{evaluation_test_data_name}', 'w', encoding="utf-8") as f:
            for sample_input in evaluation_inputs:
                if sample_input is None:
                    continue
                else:
                    sample_input = await self._smart_json_loads(sample_input) if type(sample_input) == str else sample_input
                    sample_input = json.dumps(sample_input)
                f.write(sample_input + '\n')

        print_info_func(f'\nGenerated {len(evaluation_inputs)} sample evaluation inputs for your flow. And dump them into {eval_flow_folder}\\{evaluation_test_data_name}')


    async def dump_evaluation_flow(self, evaluation_flow_folder, target_output, total_count, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_evaluation_flow reasoning: {reasoning}')

        if not self.flow_folder or not os.path.exists(self.flow_folder):
            print_info_func(f'\nBefore generate the evaluation flow, please generate or provide the flow first')
            return

        if not evaluation_flow_folder:
            evaluation_flow_folder = self.flow_folder + '\\evaluation'

        if not total_count or total_count < 1 or total_count > 1000:
            logger.info(f'invalid sample inputs count: {total_count}, Set to default 5')
            total_count = 5

        flow = await self._safe_load_flow_yaml(self.flow_yaml)
        if 'outputs' not in flow:
            raise Exception("Cannot generate evaluation flow for a flow without outputs")

        if target_output:
            if target_output not in flow['outputs']:
                raise Exception(f"Cannot find the specified output to evaluate in the flow. Output name: {target_output}")

        if not os.path.exists(evaluation_flow_folder):
            os.mkdir(evaluation_flow_folder)
            logger.info(f'Create evaluation flow folder:{evaluation_flow_folder}')

        # generate evaluation inputs
        system_instruction = self.gen_eval_flow_inputs_template.render(flow_yaml=self.flow_yaml)
        evaluation_data_count = total_count
        user_input = f"Generate evaluation evalution input for me with {evaluation_data_count} items"
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_input},
            ]

        response = await self._ask_openai_async(messages=messages, functions=[function_calls.dump_evaluation_input], function_call={"name": "dump_evaluation_input"})
        function_call = getattr(response.choices[0].message.function_call, "arguments", "") if hasattr(response.choices[0].message, 'function_call') else ""
        function_arguments = await self._smart_json_loads(function_call)
        evaluation_inputs = function_arguments['evaluation_inputs']
        await self.dump_evaluation_inputs(evaluation_inputs, evaluation_flow_folder, print_info_func)

        # generate line_process and aggreate functions
        flow_output = f"flow output named {target_output}" if target_output else "flow outputs"
        system_instruction = self.gen_eval_flow_functions.render(flow_yaml=self.flow_yaml, flow_output=flow_output)
        messages = [{"role": "system", "content": system_instruction}]
        response = await self._ask_openai_async(messages=messages, functions=[function_calls.dump_evaluation_functions], function_call={"name": "dump_evaluation_functions"})
        function_call = getattr(response.choices[0].message.function_call, "arguments", "") if hasattr(response.choices[0].message, 'function_call') else ""
        function_arguments = await self._smart_json_loads(function_call)

        await self.dump_evaluation_functions(**function_arguments, target_folder=evaluation_flow_folder)

        await self.dump_evaluation_flow_yaml_and_sdk_code(flow, evaluation_flow_folder, self.flow_folder, target_output)
        print_info_func(f"Successfully generated evaluation flow to {evaluation_flow_folder}")

        return evaluation_flow_folder

    async def dump_evaluation_flow_yaml_and_sdk_code(self, original_flow, target_folder, flow_dir, specified_output, **kwargs):
        evaluation_flow_template_folder = os.path.join(self.script_directory, '.\evaluation_template')
        evaluation_flow_yaml = os.path.join(evaluation_flow_template_folder, "flow.dag.yaml")
        with open(evaluation_flow_yaml, 'r') as f:
            yaml_str = f.read()
            evaluation_flow = await self._safe_load_flow_yaml(yaml_str)

        evaluation_flow['inputs'] = {}
        for k,v in original_flow['outputs'].items():
            if not specified_output or k == specified_output:
                evaluation_flow['inputs'][k] = {'type': v['type']}
                evaluation_flow['inputs'][f"expected_{k}"] = {'type': v['type']}

        for node in evaluation_flow['nodes']:
            if node['name'] == 'line_process':
                node['inputs'] = {}
                for k in evaluation_flow['inputs'].keys():
                    node['inputs'][k] = f"${{inputs.{k}}}"

        # dump modified yaml to local file
        modified_yaml_path = os.path.join(target_folder, "flow.dag.yaml")
        with open(modified_yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(evaluation_flow, f)

        # dump sample sdk code
        # generate column mapping string
        column_mappings = []
        for k in original_flow['outputs'].keys():
            if not specified_output or k == specified_output:
                column_mappings.append(f'"{k}": "${{run.outputs.{k}}}"')
                column_mappings.append(f'"expected_{k}": "${{data.expected_{k}}}"')

        column_mapping_string = ",".join(column_mappings)

        evaluation_flow_folder_string = target_folder.replace("\\", "\\\\")
        flow_dir_string = flow_dir.replace("\\", "\\\\")
        target_folder_string = target_folder.replace("\\", "\\\\")
        sdk_eval_sample_code = f"""
from promptflow import PFClient
import json

def main():
    # Set flow path and run input data
    flow = "{flow_dir_string}" # set the flow directory
    data= "{target_folder_string}\\\\evaluation_test_data.jsonl" # set the data file

    pf = PFClient()

    # create a run
    base_run = pf.run(
        flow=flow,
        data=data,
        stream=True
    )

    # set eval flow path
    eval_flow = "{evaluation_flow_folder_string}"
    data= "{evaluation_flow_folder_string}\\\\evaluation_test_data.jsonl"

    # run the flow with exisiting run
    eval_run = pf.run(
        flow=eval_flow,
        data=data,
        run=base_run,
        column_mapping={{{column_mapping_string}}},  # map the url field from the data to the url input of the flow
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

if __name__ == "__main__":
    main()

    """
        with open(f'{target_folder}\\promptflow_sdk_sample_code.py', 'w', encoding="utf-8") as f:
            f.write(sdk_eval_sample_code)

    def dump_flow_definition_and_description(self, flow_yaml, description, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_flow_definition_and_description reasoning: {reasoning}')

        self.flow_yaml = flow_yaml
        self.flow_description = description
        print_info_func(description)
        self.messages.append({'role':'assistant', 'content':description})

    async def upsert_flow_files(self, files_name_content, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call upsert_flow_files reasoning: {reasoning}')

        for upsert_flow_files in files_name_content:
            file_name = upsert_flow_files.get('name') or upsert_flow_files.get('file_name')
            if file_name is None:
                file_name = upsert_flow_files['file_name'] if 'file_name' in upsert_flow_files else None
            if file_name is None:
                logger.info(f'file name is not specified, skip.')
                break
            if self.flow_folder not in file_name:
                file_name = os.path.join(self.flow_folder, file_name)
            file_content = upsert_flow_files.get('content') or upsert_flow_files.get('file_content')
            if os.path.exists(file_name):
                logger.info(f'file {file_name} already exists, update existing file')
                print_info_func(f'\nupdate existing file {file_name}')
            else:
                logger.info(f'file {file_name} does not exist, create new file')
                print_info_func(f'\ncreate new file {file_name}')
            with open(file_name, 'w', encoding="utf-8") as f:
                f.write(file_content)

            if file_name.endswith('dag.yaml'):
                logger.info('update flow yaml')
                await self._safe_load_flow_yaml(file_content)

    async def dump_evaluation_functions(self, line_process, aggregate, target_folder):
        requirement_python_packages = set()
        with open(f'{target_folder}\\line_process.py', 'w', encoding="utf-8") as f:
            refined_codes = await self._refine_python_code(line_process)
            f.write(refined_codes)
            packages = await self._find_dependent_python_packages(refined_codes)
            requirement_python_packages.update(packages)
        with open(f'{target_folder}\\aggregate.py', 'w', encoding="utf-8") as f:
            refined_codes = await self._refine_python_code(aggregate)
            f.write(refined_codes)
            packages = await self._find_dependent_python_packages(refined_codes)
            requirement_python_packages.update(packages)

        # dump requirements.txt
        if requirement_python_packages and len(requirement_python_packages) > 0:
            with open(f'{target_folder}\\requirements.txt', 'w', encoding="utf-8") as f:
                f.write('\n'.join(requirement_python_packages))

    # endregion