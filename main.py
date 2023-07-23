import tkinter as tk
from tkinter import ttk
from tkinter import Scrollbar
from tkinter import messagebox
from CopilotContext import CopilotContext
import traceback

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
    try:
        user_input = input_box.get(1.0, tk.END).strip('\n')
        if user_input == entry_default_message:
            return
        add_to_chat(user_input, USER_TAG)
        update_label.config(text='Status: Talking to GPT...')
        app.update()
        copilot_context.ask_gpt(user_input, add_to_chat)
        chat_box.yview_moveto(1.0)
        update_label.config(text="Status: Waiting for user's input...")
    except Exception:
        trace_back = traceback.format_exc()
        messagebox.showerror("Error occurred. Please fix the error and try again.", trace_back)
        app.destroy()

def start_over():
    try:
        add_to_chat("Okay, let's satrt over. Pleae tell me your goal you want to accomplish using promptflow")
        chat_box.yview_moveto(1.0)
        copilot_context.reset()
    except Exception:
        trace_back = traceback.format_exc()
        messagebox.showerror("Error occurred. Please fix the error and try again.", trace_back)
        app.destroy()
        
def add_to_chat(message, tag=COPILOT_TAG):
    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, tag + ': ' + message + "\n\n", tag)
    chat_box.config(state=tk.DISABLED)
    chat_box.yview_moveto(1.0)
    input_box.delete(1.0, tk.END)
    input_box.see("1.0")
    input_box.mark_set(tk.INSERT, 1.0)
    app.update()

def ctrl_enter_pressed(event):
    get_response()

def on_entry_click(event):
    if input_box.get(1.0, "end-1c").strip('\n') == entry_default_message:
        input_box.delete(1.0, tk.END)
        input_box.config(fg=TEXT_COLOR)

def on_focus_out(event):
    if input_box.get(1.0, "end-1c").strip('\n') == "":
        input_box.insert(tk.END, entry_default_message)
        input_box.config(fg="gray")

# Create the main application window
app = tk.Tk()
app.title("Promptflow Copilot")
app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(1, weight=1)

app.rowconfigure(0, minsize=10)
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

# create a text box to accept user input
input_box = tk.Text(app, bg="#2C3E50", fg="grey", font=FONT, height=2)
input_box.grid(row=2, column=0, columnspan=9, sticky='nsew')
input_box.bind("<Control-Return>", ctrl_enter_pressed)
input_box.bind("<FocusIn>", on_entry_click)
input_box.bind("<FocusOut>", on_focus_out)

input_box.focus_set()
input_box.insert(1.0, entry_default_message)

# Create buttons with ttk style
button_style = ttk.Style()
button_style.configure('TButton', font=('Helvetica', 12))

reset_button = ttk.Button(app, text="Start over", command=start_over, style='TButton')
reset_button.grid(row=0, column=9, columnspan=1, sticky='nsew')
send_button = ttk.Button(app, text="Send", command=get_response, style='TButton')
send_button.grid(row=2, column=9, columnspan=1, sticky='nsew')

# check environment
env_ready, msg = copilot_context.check_env()
add_to_chat(checking_environment_message, COPILOT_TAG)
if env_ready:
    add_to_chat(environment_ready_message, COPILOT_TAG)
else:
    add_to_chat(environment_not_ready_message + msg + '\n', COPILOT_TAG)

# Run the main event loop
app.mainloop()