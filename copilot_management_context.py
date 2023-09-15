import os
import json
import yaml
from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from logging_util import get_logger
import function_calls
from token_utils import num_tokens_from_messages, num_tokens_from_functions, num_tokens_from_completions
from pfflow_client import PfFlowClient
from copilot_gpt_context import CopilotGPTContext

logger = get_logger()

class CopilotManagementContext:
    def __init__(self, copilot_setting) -> None:
        self.use_endpoint = copilot_setting.use_endpoint
        self.use_aoai = copilot_setting.use_aoai

        self.aoai_key = copilot_setting.aoai_setting.aoai_key
        self.aoai_deployment = copilot_setting.aoai_setting.aoai_deployment
        self.aoai_api_base = copilot_setting.aoai_setting.aoai_api_base

        self.openai_key = copilot_setting.openai_setting.openai_key
        self.openai_model = copilot_setting.openai_setting.openai_model

        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_prompt_tokens = 0

        self.flow_folder = None
        self.flow_description = None
        self.flow_yaml = None
        self.messages = []

        self.script_directory = os.path.dirname(os.path.abspath(__file__))

        if self.use_endpoint:
            self.pfflow_client = PfFlowClient(copilot_setting.pfflowclient_setting.url, copilot_setting.pfflowclient_setting.api_key, copilot_setting.pfflowclient_setting.azureml_model_deployment)
        else:
            jinja_env = Environment(loader=FileSystemLoader(self.script_directory), variable_start_string='[[', variable_end_string=']]')
            self.copilot_gpt_context = CopilotGPTContext(jinja_env.get_template('prompts/copilot_instruction.jinja2'),
                                                          jinja_env.get_template('prompts/rewrite_user_input.jinja2'),
                                                          jinja_env.get_template('prompts/refine_python_code.jinja2'),
                                                          jinja_env.get_template('prompts/find_python_package.jinja2'),
                                                          jinja_env.get_template('prompts/summarize_flow_name.jinja2'),
                                                          jinja_env.get_template('prompts/understand_flow_instruction.jinja2'),
                                                          jinja_env.get_template('prompts/json_string_fixer.jinja2'),
                                                          jinja_env.get_template('prompts/yaml_string_fixer.jinja2'),
                                                          jinja_env.get_template('prompts/function_call_instruction.jinja2'),
                                                          copilot_setting)

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
        if self.use_endpoint:
            logger.info('Skip check env because it will be checked in endpoint.')
            return True, ""
        else:
            return self.copilot_gpt_context.check_env()
            

    def reset(self):
        self.messages = []
        self.flow_folder = None
        self.flow_yaml = None
        self.flow_description = None
        self.completion_tokens = 0
        self.prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_prompt_tokens = 0


    async def ask_gpt_async(self, content, print_info_func):
        self.last_prompt_tokens = 0
        self.last_tokens = 0

        rewritten_user_intent = await self._rewrite_user_input(content)
        potential_function_calls = self.copilot_general_function_calls

        if self.flow_yaml:
            system_message = self._get_understand_flow_system_message()
            self.messages[0] = {'role':'system', 'content': system_message}
            potential_function_calls = [
                function_calls.dump_sample_inputs,
                function_calls.dump_evaluation_flow,
                function_calls.upsert_flow_files]
        elif len(self.messages) == 0:
            self.messages.append({'role':'system', 'content':self._get_system_instruction()})
            potential_function_calls = [
                function_calls.dump_flow,
                function_calls.read_flow_from_local_file,
                function_calls.read_flow_from_local_folder,
                function_calls.read_local_file,
                function_calls.read_local_folder]

        self.messages.append({'role':'user', 'content':rewritten_user_intent})
        self.messages.append({'role':'system', 'content': self._get_function_call_instruction(potential_function_calls)})

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

        if not self.use_endpoint: # if call gpt from local, use stream output
            async for chunk in response:
                if 'choices' in chunk and len(chunk['choices']) > 0:
                    delta = chunk.choices[0]['delta']
                    if 'content' in delta:
                        cur_message = delta['content']
                        message += cur_message
                        print_info_func(cur_message)
                    if 'function_call' in delta:
                        if "name" in delta.function_call:
                            function_name = delta.function_call["name"]
                        if "arguments" in delta.function_call:
                            function_call+= delta.function_call["arguments"]
                    if 'role' in delta:
                        role = delta['role']
                    finish_reason = chunk.choices[0].finish_reason
            completion_tokens = num_tokens_from_completions(message + function_call)
            self.completion_tokens += completion_tokens
            self.last_completion_tokens += completion_tokens
        else: # if call gpt from endpoint, the result should be JSON serializable and may not be async_generator, so don't use stream output
            response = response['choices'][0]
            message = response['message']['content'] if 'content' in response['message'] else ""
            finish_reason = response['finish_reason']
            function_call = response['message']['function_call']['arguments'] if 'function_call' in response['message'] else ""
            if function_call != "":
                function_name = response['message']['function_call']['name'] if 'name' in response['message']['function_call'] else ""

        if message:
            self.messages.append({'role':role, 'content':message})
        
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
                evaluation_flow_folder = await self.dump_evaluation_flow(**function_arguments, flow_folder=self.flow_folder, eval_flow_folder=self.flow_folder + '\\evaluation', print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f"{evaluation_flow_folder}"})
                if evaluation_flow_folder:
                    next_possible_function_calls = [function_calls.dump_evaluation_inputs]
                    function_call_choice = {'name':'dump_evaluation_inputs'}
            elif function_name == 'dump_evaluation_inputs':
                function_arguments = await self._smart_json_loads(function_call)
                evaluation_input_file = await self.dump_evaluation_inputs(**function_arguments, eval_flow_folder=self.flow_folder + '\\evaluation', print_info_func=print_info_func)
                self.messages.append({"role": "function", "name": function_name, "content": f"{evaluation_input_file}"})
                early_stop = True
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
                        if python_packages != None:
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

    async def dump_sample_inputs(self, sample_inputs, target_folder, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_sample_inputs reasoning: {reasoning}')

        if not target_folder or not os.path.exists(target_folder):
            print_info_func(f'\nBefore generate the sample inputs, please generate or provide the flow first')
            return

        sample_inputs_file = f'{target_folder}\\flow.sample_inputs.jsonl'
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

    async def dump_evaluation_inputs(self, evaluation_inputs, eval_flow_folder, flow_outputs_schema, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_evaluation_inputs reasoning: {reasoning}')

        with open(f'{eval_flow_folder}\\flow.sample_inputs.jsonl', 'w', encoding="utf-8") as f:
            for sample_input in evaluation_inputs:
                if sample_input is None:
                    continue
                else:
                    sample_input = await self._smart_json_loads(sample_input) if type(sample_input) == str else sample_input
                    for flow_output in flow_outputs_schema:
                        output_name = flow_output['name']
                        sample_input[output_name] = '<expected_output>'
                f.write(json.dumps(sample_input) + '\n')


    async def dump_evaluation_flow(self, flow_outputs_schema, flow_folder, eval_flow_folder, print_info_func, reasoning=None, **kwargs):
        if reasoning is not None:
            logger.info(f'function call dump_evaluation_flow reasoning: {reasoning}')

        if not flow_folder or not os.path.exists(flow_folder):
            print_info_func(f'\nBefore generate the evaluation flow, please generate or provide the flow first')
            return

        if not os.path.exists(eval_flow_folder):
            os.mkdir(eval_flow_folder)
            logger.info(f'Create flow folder:{eval_flow_folder}')

        logger.info('Dumping evalutaion flow...')
        evaluation_flow_template_folder = os.path.join(self.script_directory, '.\evaluation_template')
        file_list = os.listdir(evaluation_flow_template_folder)
        import shutil
        for file_name in file_list:
            source_file_path = os.path.join(evaluation_flow_template_folder, file_name)
            destination_file_path = os.path.join(eval_flow_folder, file_name)
            shutil.copy(source_file_path, destination_file_path)

        # currently only support one output
        first_output_column = 'flow_output'
        if flow_outputs_schema and len(flow_outputs_schema) > 0:
            first_output_column = flow_outputs_schema[0]['name']

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

        print_info_func(f'\nDumped evalutaion flow to {eval_flow_folder}. You can refer to the sample code in {eval_flow_folder}\\promptflow_sdk_sample_code.py to run the eval flow.')

        return eval_flow_folder

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

    # endregion

    # region functions
    async def _ask_openai_async(self, messages, functions, function_call, stream):
        if self.use_endpoint:
            response = self.pfflow_client.ask_openai_async(messages, functions, function_call)
        else:
            response = await self.copilot_gpt_context._ask_openai_async(messages, functions, function_call, stream)
        
        if not stream:
            response_ms = response.response_ms
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            self.completion_tokens += completion_tokens
            self.prompt_tokens += prompt_tokens
            self.last_completion_tokens += completion_tokens
            self.last_prompt_tokens += prompt_tokens

            logger.info(f'Get response from ChatGPT in {response_ms} ms!')
            logger.info(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

        return response

    async def _safe_load_flow_yaml(self, yaml_str):
        if self.use_endpoint:
            return self.pfflow_client.safe_load_flow_yaml(yaml_str)
        else:
            return await self.copilot_gpt_context._safe_load_flow_yaml(yaml_str)

    async def _rewrite_user_input(self, user_input):
        if self.use_endpoint:
            return self.pfflow_client.rewrite_user_input(user_input, self.messages)
        else:
            return await self.copilot_gpt_context._rewrite_user_input(user_input, self.messages)

    async def _refine_python_code(self, python_code):
        if self.use_endpoint:
            return self.pfflow_client.refine_python_code(python_code)
        else:
            return await self.copilot_gpt_context._refine_python_code(python_code)

    async def _find_dependent_python_packages(self, python_code):
        if self.use_endpoint:
            return self.pfflow_client.find_dependent_python_packages(python_code)
        else:
            return await self.copilot_gpt_context._find_dependent_python_packages(python_code)

    async def _summarize_flow_name(self, flow_description):
        if self.use_endpoint:
            return self.pfflow_client.summarize_flow_name(flow_description)
        else:
            return await self.copilot_gpt_context._summarize_flow_name(flow_description)

    async def _fix_json_string_and_loads(self, json_string, error, max_retry=3):
        if self.use_endpoint:
            return self.pfflow_client.fix_json_string_and_loads(json_string, error, max_retry)
        else:
            return await self.copilot_gpt_context._fix_json_string_and_loads(json_string, error, max_retry)

    async def _fix_yaml_string_and_loads(self, yaml_string, error, max_retry=3):
        if self.use_endpoint:
            return self.pfflow_client.fix_yaml_string_and_loads(yaml_string, error, max_retry)
        else:
            return await self.copilot_gpt_context._fix_yaml_string_and_loads(yaml_string, error, max_retry)

    async def _smart_yaml_loads(self, yaml_string):
        if self.use_endpoint:
            return self.pfflow_client.smart_yaml_loads(yaml_string)
        else:
            return await self.copilot_gpt_context._smart_yaml_loads(yaml_string)

    async def _smart_json_loads(self, json_string):
        if self.use_endpoint:
            return self.pfflow_client.smart_json_loads(json_string)
        else:
            return await self.copilot_gpt_context._smart_json_loads(json_string)
        
    def _get_understand_flow_system_message(self):
        if self.use_endpoint:
            return self.pfflow_client.get_understand_flow_system_message(self.flow_folder, self.flow_yaml, self.flow_description)
        else:
            return self.copilot_gpt_context.understand_flow_template.render(flow_directory=self.flow_folder, flow_yaml_path=os.path.join(self.flow_folder, 'flow.dag.yaml'), flow_yaml=self.flow_yaml, flow_description=self.flow_description)

    def _get_function_call_instruction(self, potential_function_calls):
        if self.use_endpoint:
            return self.pfflow_client.get_function_call_instruction(potential_function_calls)
        else:
            return self.copilot_gpt_context.function_call_instruction_template.render(functions=','.join([f['name'] for f in potential_function_calls]))
    
    def _get_system_instruction(self):
        if self.use_endpoint:
            return self.pfflow_client.get_system_instruction()
        else:
            return self.copilot_gpt_context.system_instruction
    # endregion