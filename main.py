import tkinter as tk
from tkinter import ttk
from tkinter import Scrollbar
from CopilotContext import CopilotContext

welcome_message = """
Copilot: Welcome to use promptflow copilot! I can help you to create a promptflow to accomplish your goal.
Although the auto generated flow might be not right or lack of some implementation details, it should be a good start to develop your own flow. Enjoy!

Before start, remember to set below variables in the pfcopilot.env file.

"""

checking_environment_message = "Checking your environment..."

environment_ready_message = """You are all set, let's start! Pleae tell me your goal you want to accomplish using promptflow.
"""

environment_not_ready_message = """
Your environment is not ready, please configure your environment and restart the window.
"""

entry_default_message = "Send a message..."

BG_GRAY = "#ABB2B9"
BG_COLOR = "#17202A"
TEXT_COLOR = "#EAECEE"
PILOT_TEXT_COLOR = "#6495ED"

USER_TAG = 'User'
COPILOT_TAG = 'Copilot'
 
FONT = "Helvetica 14"
FONT_BOLD = "Helvetica 13 bold"

def get_response():
    user_input = entry.get()
    add_to_chat(user_input, USER_TAG)
    update_label.config(text='Status: Talking to GPT...')
    app.update()
    copilot_context.ask_gpt(user_input, add_to_chat)
    chat_box.yview_moveto(1.0)
    update_label.config(text="Status: Waiting for user's input...")

def add_to_chat(message, tag=COPILOT_TAG):
    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, tag + ': ' + message + "\n\n", tag)
    chat_box.config(state=tk.DISABLED)
    entry.delete(0, tk.END)
    app.update()

def entry_on_enter_pressed(event):
    get_response()

def on_entry_click(event):
    if entry.get() == entry_default_message:
        entry.delete(0, "end")
        entry.config(fg=TEXT_COLOR)

def on_focus_out(event):
    if entry.get() == "":
        entry.insert(0, entry_default_message)
        entry.config(fg="gray")

# Create the main application window
app = tk.Tk()
app.title("Promptflow Copilot")
app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(0, weight=1)
app.rowconfigure(0, minsize=20)
app.rowconfigure(1, minsize=200)

update_label = tk.Label(app, text="Status: Waiting for user's input...", foreground='green', font=FONT_BOLD, height=2)
update_label.grid(row=0, sticky='nw')

# init CopilotContext
copilot_context = CopilotContext()

# Create a text widget to display the chat conversation
chat_box = tk.Text(app, bg=BG_COLOR, fg=PILOT_TEXT_COLOR, font=FONT)
chat_box.grid(row=1, column=0, columnspan=10, sticky='nsew')
chat_box.tag_config('User', background=BG_COLOR, foreground = TEXT_COLOR)
chat_box.tag_config('Copilot',  background=BG_COLOR, foreground = PILOT_TEXT_COLOR)

chat_box.insert(tk.END, welcome_message, COPILOT_TAG)
chat_box.config(state=tk.DISABLED)
# scrollbar = Scrollbar(chat_box)
# scrollbar.place(relheight=1, relx=0.974)

# Create an entry widget to accept user input
entry = tk.Entry(app, bg="#2C3E50", fg="grey", font=FONT)
entry.grid(row=2, column=0, columnspan=9, sticky='nsew')
entry.insert(0, entry_default_message)
entry.bind("<Return>", entry_on_enter_pressed)
entry.bind("<FocusIn>", on_entry_click)
entry.bind("<FocusOut>", on_focus_out)
entry.focus_set()
entry.icursor(0)

# Create a button with ttk style
button_style = ttk.Style()
button_style.configure('TButton', font=('Helvetica', 12))
button = ttk.Button(app, text="Send", command=get_response, style='TButton')
button.grid(row=2, column=9, columnspan=1, sticky='nsew')

# check environment
env_ready, msg = copilot_context.check_env()
add_to_chat(checking_environment_message, COPILOT_TAG)
if env_ready:
    add_to_chat(environment_ready_message, COPILOT_TAG)
else:
    add_to_chat(environment_not_ready_message + msg + '\n', COPILOT_TAG)

# Run the main event loop
app.mainloop()