import os
import argparse
from dotenv import load_dotenv
from CopilotContext import CopilotContext
from constants import checking_environment_message, environment_ready_message, environment_not_ready_message

parser = argparse.ArgumentParser(description="promptflow copilot arguments.")

parser.add_argument("--goal", type=str, help="the goal (or the text file that contains your goal) you want to accomplish with promptflow", required=True)
parser.add_argument("--destination", type=str, help="the destination folder you want to dump your promptflow", required=False)
parser.add_argument("--temperature", type=float, help="http port for flowmt", default=0)
parser.add_argument("--model", type=str, help="specify model name if you are using openai (make sure to use -0613 models). specify deployment name if you are using aoai (make sure your deployment is based on -0613 models).")


def main():
    load_dotenv('pfcopilot.env')
    args = parser.parse_args()
    goal = args.goal
    destination = args.destination
    temperature = args.temperature
    model = args.model

    if os.path.isfile(args.goal):
        with open(args.goal, 'r') as f:
            goal = f.read()

    # init CopilotContext
    copilot_context = CopilotContext()

    # check environment
    env_ready, msg = copilot_context.check_env()
    print(checking_environment_message)
    if env_ready:
        print(environment_ready_message)
    else:
        print(environment_not_ready_message + msg)

    copilot_context.ask_gpt(goal, print, destination, model, temperature)

if __name__ == '__main__':
    main()