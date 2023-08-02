from tkinter import messagebox
import tkinter as tk

import customtkinter
from PIL import Image, ImageTk
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
FONT_BOLD = ('Helvetica bold', 13)

def get_response():
    try:
        user_input = input_box.get()
        if user_input == entry_default_message:
            return
        add_to_chat(user_input, USER_TAG)
        update_label.configure(text='Status: Talking to GPT...')
        app.update()
        copilot_context.ask_gpt(user_input, add_to_chat)
        chat_box.yview_moveto(1.0)
        update_label.configure(text="Status: Waiting for user's input...")
    except Exception:
        trace_back = traceback.format_exc()
        messagebox.showerror("Error occurred. Please fix the error and try again.", trace_back)
        add_to_chat("Error occurred. Please fix the error and try again if it is possible.")

def start_over():
    try:
        add_to_chat("Okay, let's satrt over. Pleae tell me your goal you want to accomplish using promptflow")
        chat_box.yview_moveto(1.0)
        copilot_context.reset()
    except Exception:
        trace_back = traceback.format_exc()
        messagebox.showerror("Error occurred. Please fix the error and try again.", trace_back)
        add_to_chat("Error occurred. Please fix the error and try again if it is possible.")
        
def add_to_chat(message, tag=COPILOT_TAG):
    chat_box.configure(state=tk.NORMAL)
    chat_box.insert(tk.END, tag + ': ' + message + "\n\n", tag)
    chat_box.configure(state=tk.DISABLED)
    chat_box.yview_moveto(1.0)
    input_box.delete(0, tk.END)
    app.update()

def ctrl_enter_pressed(event):
    get_response()

def handle_selection(event):
    widget = event.widget
    index = widget.index("@%s,%s" % (event.x, event.y))
    widget.tag_remove("sel", "1.0", "end")
    widget.tag_add("sel", index, "%s+%dc" % (index, 1))

customtkinter.set_appearance_mode("system")  # Modes: system (default), light, dark
customtkinter.set_default_color_theme("blue")  # Themes: blue (default), dark-blue, green

# Create the main application window
app = customtkinter.CTk()
app.title("Promptflow Copilot")

app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(1, weight=1)

app.rowconfigure(0, minsize=10)
app.rowconfigure(1, minsize=200)

app.geometry("1280x800")
app.minsize(400, 400)

tk_image = ImageTk.PhotoImage(Image.open("copilot.ico"))
app.wm_iconbitmap()
app.iconphoto(False, tk_image)

update_label = customtkinter.CTkLabel(app, text="Status: Waiting for user's input...", fg_color='green', font=('Helvetica', 14), height=2)
update_label.grid(row=0, sticky='nw')

# init CopilotContext
copilot_context = CopilotContext()

# Create a text widget to display the chat conversation
chat_box = customtkinter.CTkTextbox(app, font=('Helvetica', 14))
chat_box.grid(row=1, column=0, columnspan=10, sticky='nsew')
chat_box.tag_config('User', justify='right')
chat_box.tag_config('Copilot', foreground = PILOT_TEXT_COLOR)

chat_box.insert(tk.END, welcome_message, COPILOT_TAG)
chat_box.configure(state=tk.DISABLED)
chat_box.tag_bind("User", "<Button-1>", handle_selection)
chat_box.tag_bind("Copilot", "<Button-1>", handle_selection)

# create an entry box to accept user input
input_box = customtkinter.CTkEntry(app, font=('Helvetica', 14), placeholder_text=entry_default_message, corner_radius=5, height=5)
input_box.grid(row=2, column=0, columnspan=8, sticky='nsew', padx=(10, 10), pady=(5, 5))
input_box.bind("<Control-Return>", ctrl_enter_pressed)
input_box.bind("<Return>", ctrl_enter_pressed)

reset_button = customtkinter.CTkButton(app, text="Start over", command=start_over)
reset_button.grid(row=0, column=9, columnspan=1, sticky='nsew', padx=(0, 10), pady=(5, 5))
send_button = customtkinter.CTkButton(app, text="Send", command=get_response, border_width=0, corner_radius=5)
send_button.grid(row=2, column=9, columnspan=1, sticky='nsew', padx=(0, 10), pady=(5, 5))

# check environment
env_ready, msg = copilot_context.check_env()
add_to_chat(checking_environment_message, COPILOT_TAG)
if env_ready:
    add_to_chat(environment_ready_message, COPILOT_TAG)
else:
    add_to_chat(environment_not_ready_message + msg + '\n', COPILOT_TAG)

# Run the main event loop
app.mainloop()