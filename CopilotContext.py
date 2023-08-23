import os
import json
import openai
import re
import yaml
import asyncio
from pathlib import Path
from json import JSONDecodeError
from datetime import datetime
from dotenv import load_dotenv

from jinja2 import Environment, FileSystemLoader
from logging_util import get_logger
import function_calls

logger = get_logger()

class CopilotContext:
    def __init__(self) -> None:
        load_dotenv('pfcopilot.env')
        self.use_aoai = os.environ.get("AOAI_BY_DEFAULT", "true").lower() == "true"
        self.aoai_key = os.environ.get("AOAI_API_KEY")
        self.aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
        self.aoai_api_base = os.environ.get("AOAI_API_BASE")

        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openai_model = os.environ.get("OPENAI_MODEL")

        self.flow_folder = None
        self.flow_description = None
        self.flow_yaml = None

        jinja_env = Environment(loader=FileSystemLoader('./'), variable_start_string='[[', variable_end_string=']]')
        self.copilot_instruction_template = jinja_env.get_template('prompts/copilot_instruction.jinja2')
        self.rewrite_user_input_template = jinja_env.get_template('prompts/rewrite_user_input.jinja2')
        self.refine_python_code_template = jinja_env.get_template('prompts/refine_python_code.jinja2')
        self.find_python_package_template = jinja_env.get_template('prompts/find_python_package.jinja2')
        self.summarize_flow_name_template = jinja_env.get_template('prompts/summarize_flow_name.jinja2')
        self.understand_flow_template = jinja_env.get_template('prompts/understand_flow_instruction.jinja2')
        self.json_string_fixer_template = jinja_env.get_template('prompts/json_string_fixer.jinja2')

        self.system_instruction = self.copilot_instruction_template.render()
        self.messages = []

        self.copilot_general_function_calls = [
            function_calls.dump_flow,
            function_calls.read_local_file,
            function_calls.read_local_folder,
            function_calls.read_flow_from_local_file,
            function_calls.read_flow_from_local_folder,
            function_calls.dump_sample_inputs,
            function_calls.dump_evaluation_flow
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
        self.messages = []
        self.flow_folder = None    

    def _format_request_dict(self, messages=[], functions=None, function_call=None):
        request_args_dict = {
            "messages": messages,
            "stream": False,
            "temperature": 0
        }

        if functions:
            request_args_dict['functions'] = functions

        if functions and function_call:
            request_args_dict['function_call'] = function_call

        if self.use_aoai:
            request_args_dict['engine'] = self.aoai_deployment
        else:
            request_args_dict['model'] = self.openai_model

        return request_args_dict 

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
        request_args_dict = self._format_request_dict(messages=chat_message)
        response = await openai.ChatCompletion.acreate(**request_args_dict)
        message = getattr(response.choices[0].message, "content", "")
        logger.info(f"rewrite_user_input: {message}")
        return message
    
    async def _refine_python_code(self, python_code):
        refine_python_code_instruction = self.refine_python_code_template.render()
        chat_message = [
            {'role':'system', 'content': refine_python_code_instruction},
            {'role':'user', 'content': python_code}
        ]

        request_args_dict = self._format_request_dict(messages=chat_message)
        response = await openai.ChatCompletion.acreate(**request_args_dict)
        message = getattr(response.choices[0].message, "content", "")
        return message
    
    async def _find_dependent_python_packages(self, python_code):
        find_dependent_python_packages_instruction = self.find_python_package_template.render()
        chat_message = [
            {'role':'system', 'content': find_dependent_python_packages_instruction},
            {'role':'user', 'content': python_code}
        ]

        request_args_dict = self._format_request_dict(messages=chat_message)
        response = await openai.ChatCompletion.acreate(**request_args_dict)
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

        request_args_dict = self._format_request_dict(messages=chat_message)
        response = await openai.ChatCompletion.acreate(**request_args_dict)
        message = getattr(response.choices[0].message, "content", "")
        return message

    async def _fix_json_string(self, json_string, error, max_retry=3):
        try:
            fix_json_string_instruction = self.json_string_fixer_template.render(original_string=json_string, error_message=error)
            chat_message = [
                {'role':'system', 'content': fix_json_string_instruction},
            ]
            request_args_dict = self._format_request_dict(messages=chat_message)
            response = await openai.ChatCompletion.acreate(**request_args_dict)
            message = getattr(response.choices[0].message, "content", "")
            json.loads(message)
            return message
        except JSONDecodeError as ex:
            logger.error(f'Failed to fix json string {json_string} with error {error}')
            if max_retry > 0 and message != json_string:
                return await self._fix_json_string(message, str(ex), max_retry=max_retry-1)
            raise ex

    async def _smart_json_loads(self, json_string):
        try:
            return json.loads(json_string)
        except JSONDecodeError as ex:
            pattern = r'\\\n'
            updated_function_call = re.sub(pattern, r'\\n', str(json_string))
            if updated_function_call == json_string:
                logger.error(f'Failed to load json string {json_string}')
                updated_function_call = await self._fix_json_string(json_string, str(ex))
            return await self._smart_json_loads(updated_function_call)
        
    async def ask_gpt_async(self, content, print_info_func):
        rewritten_user_intent = await self._rewrite_user_input(content)
        potential_function_calls = self.copilot_general_function_calls

        if self.flow_folder:
            system_message = self.understand_flow_template.render(flow_yaml=self.flow_yaml, flow_description=self.flow_description)
            self.messages[0] = {'role':'system', 'content': system_message}
            potential_function_calls = self.copilot_general_function_calls
        elif len(self.messages) == 0:
            self.messages.append({'role':'system', 'content':self.system_instruction})
            potential_function_calls = [
                function_calls.dump_flow,
                function_calls.read_flow_from_local_file, 
                function_calls.read_flow_from_local_folder, 
                function_calls.read_local_file, 
                function_calls.read_local_folder]

        self.messages.append({'role':'user', 'content':rewritten_user_intent})
        request_args_dict = self._format_request_dict(
            messages=self.messages, functions=potential_function_calls, function_call='auto')
        
        response = await openai.ChatCompletion.acreate(**request_args_dict)
        await self.parse_gpt_response(response, print_info_func)

        # clear function message if we have already got the flow
        if self.flow_folder:
            self._clear_function_message()

    async def parse_gpt_response(self, response, print_info_func):
        response_ms = response.response_ms
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        message = getattr(response.choices[0].message, "content", "")
        finish_reason = response.choices[0].finish_reason
        early_stop = False
        next_possible_function_calls = None

        print_info_func(f'Get response from ChatGPT in {response_ms} ms!')
        print_info_func(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

        if message:
            self.messages.append({'role':response.choices[0].message.role, 'content':message})
            print_info_func(f'{message}')
        
        function_call = getattr(response.choices[0].message.function_call, "arguments", "") if hasattr(response.choices[0].message, 'function_call') else ""
        if function_call != "":
            function_name = getattr(response.choices[0].message.function_call, "name", "")
            if function_name == 'dump_flow':
                function_arguments = await self._smart_json_loads(function_call)
                flow_folder = await self.dump_flow(**function_arguments, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f'{flow_folder}'})
                early_stop = True
            elif function_name == 'read_local_file':
                function_arguments = await self._smart_json_loads(function_call)
                file_content = self.read_local_file(**function_arguments, print_info_func=print_info_func)
                if not file_content:
                    print_info_func('you ask me to read code from a file, but the file does not exists')
                    early_stop = True
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":file_content})
                    self.messages.append({"role": "system", "content": "You have read the file content, understand it first and then determine your next step."})
                    next_possible_function_calls = [function_calls.dump_flow]
            elif function_name == 'read_local_folder':
                function_arguments = await self._smart_json_loads(function_call)
                files_content = self.read_local_folder(**function_arguments, print_info_func=print_info_func)
                if not files_content:
                    print_info_func('you ask me to read code from a folder, but the folder does not exists')
                    early_stop = True
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":files_content})
                    self.messages.append({"role": "system", "content": "You have read all the files in the folder, understand it first and then determine your next step."})
                    next_possible_function_calls = [function_calls.dump_flow]
            elif function_name == 'dump_sample_inputs':
                function_arguments = await self._smart_json_loads(function_call)
                sample_input_file = await self.dump_sample_inputs(**function_arguments, target_folder=self.flow_folder, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f"{sample_input_file}"})
                early_stop = True
            elif function_name == 'dump_evaluation_flow':
                function_arguments = await self._smart_json_loads(function_call)
                evaluation_flow_folder = await self.dump_evaluation_flow(**function_arguments, flow_folder=self.flow_folder, eval_flow_folder=self.flow_folder + '\\evaluation', print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f"{evaluation_flow_folder}"})
                early_stop = True
            elif function_name == 'read_flow_from_local_file':
                function_arguments = await self._smart_json_loads(function_call)
                file_content = self.read_flow_from_local_file(**function_arguments, print_info_func=print_info_func)
                if not file_content:
                    print_info_func('you ask me to read flow from a file, but the file does not exists')
                    early_stop = True
                else:
                    self.flow_folder = os.path.dirname(function_arguments['path'])
                    self.messages.append({"role": "function", "name": function_name, "content":file_content})
                    next_possible_function_calls = [function_calls.dump_flow_definition_and_description]
            elif function_name == 'read_flow_from_local_folder':
                function_arguments = await self._smart_json_loads(function_call)
                self.flow_folder = function_arguments['path']
                files_content = self.read_flow_from_local_folder(**function_arguments, print_info_func=print_info_func)
                if not files_content:
                    print_info_func('you ask me to read flow from a folder, but the folder does not exists')
                    early_stop = True
                else:
                    self.messages.append({"role": "function", "name": function_name, "content":files_content})
                    next_possible_function_calls = [function_calls.dump_flow_definition_and_description]
            elif function_name == 'dump_flow_definition_and_description':
                function_arguments = await self._smart_json_loads(function_call)
                self.dump_flow_definition_and_description(**function_arguments, print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": ""})
                next_possible_function_calls = [function_calls.dump_sample_inputs, function_calls.dump_evaluation_flow]
            elif function_name == 'python':
                self.messages.append({"role": "function", "name": function_name, "content":"error: python unavailable"})
            else:
                self.messages.append({"role": "system", "content":"do not try to call functions that does not exist!"})
            
        if finish_reason != 'stop' and not early_stop:
            request_args_dict = self._format_request_dict(
                messages=self.messages, functions=next_possible_function_calls, function_call='auto')
            new_response = await openai.ChatCompletion.acreate(**request_args_dict)
            await self.parse_gpt_response(new_response, print_info_func)    

    def _clear_function_message(self):
        '''
        clear some function message from messages to reduce chat history size
        '''
        for message in self.messages:
            if message['role'] == 'function' and message['name'] in ['read_local_file', 'read_local_folder', 'read_flow_from_local_file', 'read_flow_from_local_folder']:
                self.messages.remove(message)

    # region functions
    async def dump_flow(self, print_info_func, flow_yaml, explaination, python_functions=None, prompts=None, flow_inputs_schema=None, flow_outputs_schema=None, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_flow reasoning: {reasoning}')

        if not self.flow_folder:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            flow_name = await self._summarize_flow_name(explaination)
            self.flow_folder = f'flow_{flow_name}_{timestamp}'

        target_folder = self.flow_folder

        if not os.path.exists(target_folder):
            os.mkdir(target_folder)
            print_info_func(f'Create flow folder:{target_folder}')

        parsed_flow_yaml = yaml.safe_load(flow_yaml)
        python_nodes_path_dict = {}
        llm_nodes_path_dict = {}
        for node in parsed_flow_yaml['nodes']:
            if node['type'] == 'python':
                python_nodes_path_dict[node['name']] = node['source']['path']
            elif node['type'] == 'llm':
                llm_nodes_path_dict[node['name']] = node['source']['path']
                if 'prompt' in node['inputs']:
                    del node['inputs']['prompt']

        print_info_func('Dumping flow.dag.yaml')
        with open(f'{target_folder}\\flow.dag.yaml', 'w', encoding="utf-8") as f:
            yaml.dump(parsed_flow_yaml, f, allow_unicode=True, sort_keys=False, indent=2)
            self.flow_yaml = yaml.dump(parsed_flow_yaml, allow_unicode=True, sort_keys=False, indent=2)

        print_info_func('Dumping flow.explaination.txt')
        with open(f'{target_folder}\\flow.explaination.txt', 'w', encoding="utf-8") as f:
            f.write(explaination)
            self.flow_description = explaination

        requirement_python_packages = set()
        if python_functions:
            print_info_func('Dumping python functions')
            for func in python_functions:
                fo =  func if type(func) == dict else await self._smart_json_loads(func)
                for k,v in fo.items():
                    if k in python_nodes_path_dict:
                        with open(f'{target_folder}\\{python_nodes_path_dict[k]}', 'w', encoding="utf-8") as f:
                            refined_codes = await self._refine_python_code(v)
                            f.write(refined_codes)
                            python_packages = await self._find_dependent_python_packages(refined_codes)
                            requirement_python_packages.update(python_packages)
                    else:
                        logger.info(f'Function {k} is not used in the flow, skip dumping it')

        if prompts:
            print_info_func('Dumping prompts')
            for prompt in prompts:
                po = prompt if type(prompt) == dict else await self._smart_json_loads(prompt)
                for k,v in po.items():
                    if k in llm_nodes_path_dict:
                        with open(f'{target_folder}\\{llm_nodes_path_dict[k]}', 'w', encoding="utf-8") as f:
                            f.write(v)
                    else:
                        logger.info(f'Prompt {k} is not used in the flow, skip dumping it')

        if requirement_python_packages:
            print_info_func('Dumping requirements.txt')
            with open(f'{target_folder}\\requirements.txt', 'w', encoding="utf-8") as f:
                f.write('\n'.join(requirement_python_packages))

        print_info_func(f'finish dumping flow to folder:{self.flow_folder}')
        return self.flow_folder

    def read_local_file(self, path, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_local_file reasoning: {reasoning}')

        if os.path.isdir(path):
            return self.read_local_folder(path, print_info_func)

        if not os.path.exists(path):
            print_info_func(f'{path} does not exists')
            return
        else:
            print_info_func(f'read content from file:{path}')
            with open(path, 'r', encoding="utf-8") as f:
                return f.read()

    def read_local_folder(self, path, print_info_func, included_file_types=['.ipynb', '.py'], reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_local_folder reasoning: {reasoning}')

        if os.path.isfile(path):
            return self.read_local_file(path, print_info_func)

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

    def read_flow_from_local_folder(self, path, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_flow_from_local_folder reasoning: {reasoning}')

        if os.path.isfile(path):
            return self.read_local_file(path, print_info_func)
        print_info_func(f'read existing flow from folder:{path}')
        self.flow_folder = path
        return self.read_local_folder(path, print_info_func, included_file_types=['.yaml'])

    def read_flow_from_local_file(self, path, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call read_flow_from_local_file reasoning: {reasoning}')

        if os.path.isdir(path):
            return self.read_flow_from_local_folder(path, print_info_func)
        print_info_func(f'read existing flow from file:{path}')
        self.flow_folder = os.path.dirname(path)
        return self.read_local_file(path, print_info_func)

    async def dump_sample_inputs(self, sample_inputs, target_folder, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_sample_inputs reasoning: {reasoning}')

        if not os.path.exists(target_folder):
            print_info_func(f'Before generate the sample inputs, please generate the flow first')
            return

        sample_inputs_file = f'{target_folder}\\flow.sample_inputs.jsonl'
        if sample_inputs is None:
            print_info_func('Failed to generate inputs for your flow, please try again')
        else:
            with open(sample_inputs_file, 'w', encoding="utf-8") as f:
                for sample_input in sample_inputs:
                    if sample_input is None:
                        continue
                    else:
                        sample_input = await self._smart_json_loads(sample_input) if type(sample_input) == str else sample_input
                        sample_input = json.dumps(sample_input)
                    f.write(sample_input + '\n')
            print_info_func(f'Generated {len(sample_inputs)} sample inputs for your flow. And dump them into {target_folder}\\flow.sample_inputs.jsonl')
        
        return sample_inputs_file

    async def dump_evaluation_flow(self, sample_inputs, flow_outputs_schema, flow_folder, eval_flow_folder, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_evaluation_flow reasoning: {reasoning}')

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
                    sample_input = await self._smart_json_loads(sample_input) if type(sample_input) == str else sample_input
                    flow_outputs_schema = flow_outputs_schema if type(flow_outputs_schema) == dict else await self._smart_json_loads(flow_outputs_schema)
                    for k,v in flow_outputs_schema.items():
                        sample_input[k] = 'expected_output'
                    first_output_column = next(iter(flow_outputs_schema)) if flow_outputs_schema else ''
                f.write(json.dumps(sample_input) + '\n')

        goundtruth_name = f'data.{first_output_column}'
        prediction_name = f'run.outputs.{first_output_column}'

        sdk_eval_sample_code = f"""
    from promptflow import PFClient
    import json

    def main():
        # Set flow path and run input data
        flow = "{flow_folder}" # set the flow directory
        data= "{eval_flow_folder}\\\\flow.sample_inputs.jsonl" # set the data file

        pf = PFClient()

        # create a run
        base_run = pf.run(
            flow=flow,
            data=data,
            stream=True
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

    if __name__ == "__main__":
        main()

    """
        with open(f'{eval_flow_folder}\\promptflow_sdk_sample_code.py', 'w', encoding="utf-8") as f: 
            f.write(sdk_eval_sample_code)

        print_info_func(f'Dumped evalutaion flow to {eval_flow_folder}. You can refer to the sample code in {eval_flow_folder}\\promptflow_sdk_sample_code.py to run the eval flow.')

        return eval_flow_folder

    def dump_flow_definition_and_description(self, flow_yaml, description, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_flow_definition_and_description reasoning: {reasoning}')

        self.flow_yaml = flow_yaml
        self.flow_description = description
        print_info_func(description)
    # endregion