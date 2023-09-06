import traceback
import ssl
from copilot_context import CopilotContext

if __name__ == "__main__":
    # init CopilotContext
    copilot_context = CopilotContext()
    
    while True:
        goal = input(f'[USER]: \n')
        if goal == 'exit':
            print(f'[COPILOT]:' + '\n You are trying to end this chat, and it will be closed.')
            break
        else:
            print(f'[COPILOT]:')
            try:
                copilot_context.ask_gpt(goal, print)
            except Exception:
                trace_back = traceback.format_exc()
                print('Error occurred. Please fix the error and try again.\n' + trace_back)