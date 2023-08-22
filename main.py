from tkinter import messagebox
import tkinter as tk
from async_tkinter_loop import async_handler, async_mainloop
import customtkinter
from PIL import Image, ImageTk
from CopilotContext import CopilotContext
import traceback
from constants import USER_TAG, COPILOT_TAG, IMAGE_TAG, USER_TEXT_COLOR, LABEL_COLOR, PILOT_TEXT_COLOR
from constants import entry_default_message, welcome_message, checking_environment_message, environment_ready_message, environment_not_ready_message
from logging_util import get_logger
from tool_tip import ToolTip

current_tag = USER_TAG

def handle_exception(exc_traceback):
    messagebox.showerror("Error occurred. Please try again.", exc_traceback)
    add_to_chat("Error occurred. Please try again.")
    update_label.configure(text="Waiting for user's input...")
    logger.error(exc_traceback)

async def get_response_async():
    try:
        user_input = input_box.get().strip()
        if user_input == entry_default_message or user_input == '':
            return
        add_to_chat(user_input, USER_TAG)
        update_label.configure(text='Talking to GPT...')
        send_button.configure(state=tk.DISABLED)
        reset_button.configure(state=tk.DISABLED)
        app.update()
        await copilot_context.ask_gpt_async(user_input, add_to_chat)
    except Exception:
        trace_back = traceback.format_exc()
        handle_exception(trace_back)
    finally:
        chat_box.yview_moveto(1.0)
        update_label.configure(text="Waiting for user's input...")
        send_button.configure(state=tk.NORMAL)
        reset_button.configure(state=tk.NORMAL)
        app.update()

def start_over():
    try:
        chat_box.configure(state=tk.NORMAL)
        chat_box.delete(1.0, tk.END)
        add_image_to_chat()
        add_to_chat("Okay, let's satrt over. Pleae tell me your goal you want to accomplish using promptflow")
        chat_box.yview_moveto(1.0)
        copilot_context.reset()
        chat_box.configure(state=tk.DISABLED)
    except Exception:
        trace_back = traceback.format_exc()
        handle_exception(trace_back)
        
def add_to_chat(message, tag=COPILOT_TAG):
    global current_tag
    chat_box.configure(state=tk.NORMAL)
    if tag != current_tag:
        add_image_to_chat(tag)
        current_tag = tag
    chat_box.insert(tk.END, message + "\n", tag)
    chat_box.configure(state=tk.DISABLED)
    chat_box.yview_moveto(1.0)
    input_box.delete(0, tk.END)
    app.update()

def add_image_to_chat(tag=COPILOT_TAG):
    chat_box.image_create(tk.END, image=images_dict[tag], padx=10, pady=5)
    chat_box.insert(tk.END, f"{tag}\n", IMAGE_TAG)

async def ctrl_enter_pressed(event):
    button_state = send_button.cget('state')
    if button_state == tk.NORMAL:
        await get_response_async()

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

CHAT_FONT = customtkinter.CTkFont('system ui', 16)
INPUT_FONT = customtkinter.CTkFont('Helvetica', 14)
LABEL_FONT = customtkinter.CTkFont('Helvetica', 14)
IMAGE_FONT = customtkinter.CTkFont('Helvetica', 12, 'bold')

app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(1, weight=1)

app.rowconfigure(0, minsize=10)
app.rowconfigure(1, minsize=200)

app.geometry("1280x800")
app.minsize(400, 400)

tk_image = ImageTk.PhotoImage(Image.open("icon.png"))
app.wm_iconbitmap()
app.iconphoto(False, tk_image)

copilot_image = ImageTk.PhotoImage(Image.open("bot.png"))
user_image = ImageTk.PhotoImage(Image.open("user.png"))
images_dict = {USER_TAG: user_image, COPILOT_TAG: copilot_image}

update_label = customtkinter.CTkLabel(app, text="Status: Waiting for user's input...", text_color=LABEL_COLOR, font=LABEL_FONT, padx=10)
update_label.grid(row=0, sticky='nwse')

# init CopilotContext
copilot_context = CopilotContext()

# Create a text widget to display the chat conversation
chat_box = tk.Text(app, font=CHAT_FONT)
chat_box.grid(row=1, column=0, columnspan=10, sticky='nsew')
chat_box.tag_config(USER_TAG, foreground=USER_TEXT_COLOR, lmargin1=10, lmargin2=10, rmargin=50, spacing1=5, spacing3=10, wrap=tk.WORD)
chat_box.tag_config(COPILOT_TAG, foreground = PILOT_TEXT_COLOR, lmargin1=10, lmargin2=10, rmargin=50, spacing1=5, spacing3=10, wrap=tk.WORD)
chat_box.tag_config(IMAGE_TAG, lmargin1=10, lmargin2=10, rmargin=50, spacing1=5, spacing3=10, wrap=tk.WORD, font=IMAGE_FONT)

chat_box.tag_bind("User", "<Button-1>", handle_selection)
chat_box.tag_bind("Copilot", "<Button-1>", handle_selection)

# create an entry box to accept user input
input_box = customtkinter.CTkEntry(app, font=INPUT_FONT, placeholder_text=entry_default_message, corner_radius=5, height=5)
input_box.grid(row=2, column=0, columnspan=8, sticky='nsew', padx=(5, 5), pady=(5, 5))
input_box.bind("<Control-Return>", command=async_handler(ctrl_enter_pressed))
input_box.bind("<Return>", command=async_handler(ctrl_enter_pressed))

reset_button = customtkinter.CTkButton(app, text="Start over", command=start_over)
reset_button.grid(row=0, column=9, columnspan=1, sticky='nsew', padx=(0, 10), pady=(5, 5))
reset_button_tooltip = ToolTip(reset_button, normal_text="reset copilot context", disabled_text="please wait until the current request is completed")

send_button = customtkinter.CTkButton(app, text="Send", command=async_handler(get_response_async), border_width=0, corner_radius=5)
send_button.grid(row=2, column=9, columnspan=1, sticky='nsew', padx=(0, 10), pady=(5, 5))
send_button_tooltip = ToolTip(send_button, normal_text="send user input", disabled_text="please wait until the current request is completed")

# check environment
env_ready, msg = copilot_context.check_env()
add_to_chat(welcome_message, COPILOT_TAG)
add_to_chat(checking_environment_message, COPILOT_TAG)
if env_ready:
    add_to_chat(environment_ready_message, COPILOT_TAG)
else:
    add_to_chat(environment_not_ready_message + msg, COPILOT_TAG)


# setup logging
logger = get_logger()

# Run the main event loop
async_mainloop(app)