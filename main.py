import os
import json
import openai
import argparse
from jinja2 import Environment, FileSystemLoader

parser = argparse.ArgumentParser(description="promptflow copilot arguments.")

parser.add_argument("--goal", type=str, help="the goal (or the text file that contains your goal) you want to accomplish with promptflow", required=True)
parser.add_argument("--dest", type=str, help="the destination folder you want to dump your promptflow", required=True)
parser.add_argument("--temperature", type=float, help="http port for flowmt", default=0)
parser.add_argument("--model", type=str, help="specify model name if you are using openai (make sure to use -0613 models). specify deployment name if you are using aoai (make sure your deployment is based on -0613 models).")
# parser.add_argument("--model", type=str, choices=["gpt-4-0613", "gpt-3.5-turbo-0613", "gpt-3.5-turbo-16k-0613", "gpt-4-32k-0613", "gpt-35-turbo", "gpt-35-turbo-16k", "gpt-35-turbo-0613", "gpt-35-turbo-16k-0613"], default="gpt-35-turbo-16k-0613", help="gpt model to use")
parser.add_argument('--aoai', action="store_true", help="Use aoai instead of openai")
parser.add_argument('--api-base', type=str, help='must provide the api base if using aoai')

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
    
def main():
    args = parser.parse_args()

    # goal = "given a person's hobby, find the best place for him or her to trval and generate a detailed traval plan"
    # goal = "answer a question give the related proof from wikipedia"
    # goal = "check if there are gramma mistakes in a github repo's files, the file may be written with python, c, go or any programming language; if found gramma mistakes, create a pull request to fix the gramma mistakes"
    # goal = "You work as a snake charmer and you want to impress the crowd with your skilful control of the snake. The snake comes out from the middle cell of a NxN grid. At each step, you can make its head move into any of the four adjacent (horizontally and vertically) cells. The snake cannot leave the grid or run into itself. The snake is divided into sections containing numbers, where each section is one grid cell in length. You get points based on the patterns that you make with the snake's sections. In particular, you get v^(m+1) points for each section, where v is the section's value and m is the number of adjacent (horizontally and vertically) cells with value v.Here is an example solution for seed=1, N=7, V=3, Snake=\"3444433322344332432434424422324243233232232424424\". This solution obtains a raw score of 3339. The black line shows the path that the snake travelled. The colour of a cell indicates the number of its matching neighbours. The head and the tail of the snake are shown inside a black square. Note that the entire snake does not need to come out."
    # goal = "detect and translate American Sign Language (ASL) fingerspelling into text"
    env = Environment(loader=FileSystemLoader('./'), variable_start_string='[[', variable_end_string=']]')
    template = env.get_template('pfplaner_v2.jinja2')

    goal = args.goal
    if os.path.isfile(args.goal):
        with open(args.goal, 'r') as f:
            goal = f.read()
    prompt = template.render(goal=goal)

    my_custom_functions = [
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

    chat_message = [
        {'role':'system', 'content':'you are helpful assitant and can help user to write high quality code based on the provided examples'},
        {'role':'user', 'content':prompt}
    ]



    print('Generating prompt flow for your goal...')

    request_args_dict = {
        "messages": chat_message,
        "functions": my_custom_functions,
        "function_call": {'name': 'dump_flow'},
        "stream": False,
        "temperature": args.temperature
    }    

    if args.aoai:
        if not args.api_base:
            raise Exception('You shoud provide api base for aoai')
        openai.api_key = os.environ.get("AOAI_API_KEY", "b0c7a86bece942a19a4ee970c0d27d79")
        if openai.api_key == "":
            raise Exception("Could not find your aoai key in env:AOAI_API_KEY")
        openai.api_type = "azure"
        openai.api_base = args.api_base
        openai.api_version = "2023-07-01-preview"
        request_args_dict['engine'] = args.model
    else:
        openai.api_key = os.environ.get("OPENAI_API_KEY", "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")
        if openai.api_key == "":
            raise Exception("Could not find your openai key in env:OPENAI_API_KEY")
        request_args_dict['model'] = args.model

    response = openai.ChatCompletion.create(**request_args_dict)

    response_ms = response.response_ms
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens
    print(f'Finished generating prompt flow for your goal from ChatGPT in {response_ms} ms!')
    print(f'total tokens:{total_tokens}\tprompt tokens:{prompt_tokens}\tcompletion tokens:{completion_tokens}')

    print(f'Dumping generated prompt flow to local folder')
    function_arguments = json.loads(getattr(response.choices[0].message.function_call, "arguments", ""))
    print(f"raw response:{function_arguments}")
    dump_flow(**function_arguments, target_folder=args.dest)
    print(f'Congratulations! Your prompt flow was successfully dumped to local folder')

if __name__ == '__main__':
    main()