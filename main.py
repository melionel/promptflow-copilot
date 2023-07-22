import tkinter as tk
from tkinter import ttk
from tkinter import Scrollbar

welcome_message = """
Copilot: Welcome to use promptflow copilot! I can help you to create a promptflow to accomplish your goal.
Although the auto generated flow might be not right or lack of some implementation details, it should be a good start to develop your own flow. Enjoy!

Before start, remember to set below variables in the pfcopilot.env file.
All set? Let's start!

Pleae tell me your goal you want to accomplish using promptflow.
"""

BG_GRAY = "#ABB2B9"
BG_COLOR = "#17202A"
TEXT_COLOR = "#EAECEE"
PILOT_TEXT_COLOR = "#6495ED"
 
FONT = "Helvetica 14"
FONT_BOLD = "Helvetica 13 bold"

def get_response():
    user_input = entry.get()
    add_to_chat("You: " + user_input, 'User')
    # Add your response logic here
    response = "Copilot: Thanks for your input!"
    add_to_chat(response, 'Copilot')
    chat_box.yview_moveto(1.0)

def add_to_chat(message, tag):
    chat_box.config(state=tk.NORMAL)
    chat_box.insert(tk.END, message + "\n", tag)
    chat_box.config(state=tk.DISABLED)
    entry.delete(0, tk.END)

# Create the main application window
app = tk.Tk()
app.title("Promptflow Copilot")

# Create a text widget to display the chat conversation
chat_box = tk.Text(app, width=100, bg=BG_COLOR, fg=PILOT_TEXT_COLOR, font=FONT)
chat_box.grid(row=1, column=0, columnspan=2)
chat_box.tag_config('User', background=BG_COLOR, foreground = TEXT_COLOR)
chat_box.tag_config('Copilot',  background=BG_COLOR, foreground = PILOT_TEXT_COLOR)

chat_box.insert(tk.END, welcome_message + "\n", 'Copilot')
chat_box.config(state=tk.DISABLED)
# scrollbar = Scrollbar(chat_box)
# scrollbar.place(relheight=1, relx=0.974)

# Create an entry widget to accept user input
entry = tk.Entry(app, width=90, bg="#2C3E50", fg=TEXT_COLOR, font=FONT)
entry.grid(row=2, column=0)

# Create a button with ttk style
button_style = ttk.Style()
button_style.configure('TButton', font=('Helvetica', 12))
button = ttk.Button(app, text="Send", command=get_response, style='TButton')
button.grid(row=2, column=1)

# Run the main event loop
app.mainloop()