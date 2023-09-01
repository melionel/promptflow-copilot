import colorama
import traceback
from termcolor import colored
from dotenv import load_dotenv
from constants import USER_TAG, COPILOT_TAG, welcome_message, checking_environment_message, environment_ready_message, environment_not_ready_message
from CopilotContext import CopilotContext
import asyncio
colorama.init(autoreset=False)

def print_no_newline(msg):
    print(msg, end="")

def main():
    print(colored(f'[{COPILOT_TAG}]:', 'red'))
    print(welcome_message + 'You can type `exit` to end this chat.')

    load_dotenv('pfcopilot.env')
    
    # init CopilotContext
    copilot_context = CopilotContext()
    
    # check environment
    print(checking_environment_message)
    env_ready, msg = copilot_context.check_env()
    if env_ready:
        print(environment_ready_message)
    else:
        print(environment_not_ready_message + msg)

    loop = asyncio.get_event_loop()
    while True:
        goal = input(colored(f'\n[{USER_TAG}]: \n', 'red'))
        if goal.lower() == 'exit':
            print('\n' + colored(f'[{COPILOT_TAG}]:', 'red') + '\n You are trying to end this chat, and it will be closed.')
            break
        if goal.lower() == 'new chat':
            copilot_context.reset()
            print('\n' + colored(f'[{COPILOT_TAG}]:', 'red') + "Okay, let's satrt over. What can I do for you?")
        else:
            print(colored(f'[{COPILOT_TAG}]:', 'red'))
            try:
                loop.run_until_complete(copilot_context.ask_gpt_async(goal, print_no_newline))
            except Exception:
                trace_back = traceback.format_exc()
                print('\nError occurred. Please fix the error and try again.\n' + trace_back)

if __name__ == '__main__':
    main()