from CopilotContext import CopilotContext

copilot = CopilotContext()

copilot.check_and_init_env()

qq = "How can you manage dependencies between cascading inputs in multiple levels?"

ans, ctx = copilot.ask_gpt(qq)

print(ans)