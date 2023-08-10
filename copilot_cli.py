import colorama
import traceback
from termcolor import colored
from dotenv import load_dotenv
from constants import USER_TAG, COPILOT_TAG, welcome_message, checking_environment_message, environment_ready_message, environment_not_ready_message
from CopilotContext import CopilotContext
colorama.init(autoreset=False)


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
    
    while True:
        goal = input(colored(f'[{USER_TAG}]: \n', 'red'))
        if goal == 'exit':
            print(colored(f'[{COPILOT_TAG}]:', 'red') + '\n You are trying to end this chat, and it will be closed.')
            break
        else:
            print(colored(f'[{COPILOT_TAG}]:', 'red'))
            try:
                copilot_context.ask_gpt(goal, print)
            except Exception:
                trace_back = traceback.format_exc()
                print('Error occurred. Please fix the error and try again.\n' + trace_back)

if __name__ == '__main__':
    main()