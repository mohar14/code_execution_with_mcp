"""Gradio UI for Code Execution with MCP Agent."""

import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import gradio as gr
import httpx
from dotenv import load_dotenv
from loguru import logger
from openai import AsyncOpenAI

# Get project root directory (before loading env)
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

# Configuration
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4-5-20250929")

# Initialize OpenAI client
client = AsyncOpenAI(
    base_url=f"{AGENT_API_URL}/v1",
    api_key="",  # Not used but required by the SDK
)

# Track which users have initialized containers (persists across chats)
user_containers_initialized = set()


# Custom CSS for better styling
CUSTOM_CSS = """
.container {
    max-width: 1400px;
    margin: 0 auto;
}

.header {
    text-align: center;
    padding: 2rem 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 10px;
    margin-bottom: 2rem;
}

.header h1 {
    margin: 0;
    font-size: 2.5rem;
    font-weight: bold;
}

.header p {
    margin: 0.5rem 0 0 0;
    font-size: 1.1rem;
    opacity: 0.9;
}

.info-box {
    background: #f8f9fa;
    border-left: 4px solid #667eea;
    padding: 1.5rem;
    border-radius: 8px;
    margin: 1rem 0;
}

.info-box h3 {
    margin-top: 0;
    color: #667eea;
}

.status-indicator {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-healthy {
    background-color: #28a745;
}

.status-degraded {
    background-color: #ffc107;
}

.status-error {
    background-color: #dc3545;
}

.tool-call {
    background: #e3f2fd;
    border-left: 4px solid #2196f3;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 4px;
    font-family: monospace;
}

.tool-call-header {
    font-weight: bold;
    color: #1976d2;
    margin-bottom: 0.5rem;
}

.docker-info {
    background: #f3e5f5;
    border-left: 4px solid #9c27b0;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 4px;
}

.reasoning-step {
    background: #fff3e0;
    border-left: 4px solid #ff9800;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 4px;
}

.code-block {
    background: #263238;
    color: #aed581;
    padding: 1rem;
    border-radius: 4px;
    overflow-x: auto;
    font-family: 'Courier New', monospace;
    margin: 0.5rem 0;
}

.activity-section {
    margin: 0.75rem 0;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    overflow: hidden;
}

.activity-section-header {
    background: #f5f5f5;
    padding: 0.75rem 1rem;
    cursor: pointer;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background 0.2s;
}

.activity-section-header:hover {
    background: #ececec;
}

.activity-section-content {
    padding: 1rem;
    background: white;
}

.section-icon {
    font-size: 1.2em;
    margin-right: 0.5rem;
}

.toggle-icon {
    font-size: 0.8em;
    transition: transform 0.3s;
}
"""


async def check_health() -> dict:
    """Check health of Agent API."""
    health_status = {
        "agent_api": {"status": "unknown", "message": ""},
    }

    try:
        async with httpx.AsyncClient() as http_client:
            # Check Agent API
            try:
                response = await http_client.get(f"{AGENT_API_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    # Note: mcp_server_connected is often false even when working
                    # It only checks at startup, not during active use
                    health_status["agent_api"] = {
                        "status": "healthy"
                        if response.status_code == 200
                        else data.get("status", "unknown"),
                        "message": "Connected",
                    }
                else:
                    health_status["agent_api"] = {
                        "status": "error",
                        "message": f"HTTP {response.status_code}: {response.text}",
                    }
            except Exception as e:
                health_status["agent_api"] = {
                    "status": "error",
                    "message": f"Connection failed: {e!s}",
                }

    except Exception as e:
        logger.error(f"Health check error: {e}")

    return health_status


def format_health_status(health: dict) -> str:
    """Format health status for display."""
    html = "<div style='font-family: monospace;'>"

    for service, info in health.items():
        status = info["status"]
        message = info["message"]

        if status == "healthy":
            icon = "🟢"
            color = "#28a745"
        elif status == "degraded":
            icon = "🟡"
            color = "#ffc107"
        else:
            icon = "🔴"
            color = "#dc3545"

        html += "<div style='margin: 0.5rem 0;'>"
        html += f"<span style='color: {color};'>{icon}</span> "
        html += f"<strong>{service.replace('_', ' ').title()}:</strong> "
        html += f"<span>{message}</span>"
        html += "</div>"

    html += "</div>"
    return html


async def parse_stream_event(line: str) -> dict | None:
    """Parse SSE event line."""
    if not line.strip() or line.startswith(":"):
        return None

    if line.startswith("data: "):
        data = line[6:]  # Remove "data: " prefix
        if data.strip() == "[DONE]":
            return {"type": "done"}
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    return None


def format_tool_call(tool_name: str, arguments: str) -> str:
    """Format tool call for display."""
    html = "<div class='tool-call'>"
    html += f"<div class='tool-call-header'>🔧 Tool Call: {tool_name}</div>"

    try:
        args = json.loads(arguments)
        html += "<div style='margin-top: 0.5rem;'>"
        html += "<strong>Arguments:</strong><br>"
        for key, value in args.items():
            # Truncate long values
            value_str = str(value)
            if len(value_str) > 200:
                value_str = value_str[:200] + "..."
            html += f"  • <strong>{key}:</strong> <code>{value_str}</code><br>"
        html += "</div>"
    except json.JSONDecodeError:
        html += f"<div style='margin-top: 0.5rem;'><code>{arguments}</code></div>"

    html += "</div>"
    return html


def format_reasoning_step(content: str) -> str:
    """Format reasoning step for display."""
    html = "<div class='reasoning-step'>"
    html += "<div><strong>🤔 Agent Reasoning:</strong></div>"
    html += f"<div style='margin-top: 0.5rem;'>{content}</div>"
    html += "</div>"
    return html


def is_debug_content(text: str) -> bool:
    """Check if text appears to be debug/internal content."""
    debug_patterns = [
        "parts=[Part(",
        "function_call=FunctionCall(",
        "args={",
        'content: """',
        "Part(",
        "FunctionCall(",
        "), Part(",
    ]
    return any(pattern in text for pattern in debug_patterns)


def clean_response_text(text: str) -> str:
    """Clean response text by removing debug content."""
    if not text or not text.strip():
        return text

    # If it looks like debug content, return empty
    if is_debug_content(text):
        return ""

    return text


def create_collapsible_section(
    title: str, icon: str, content: str, section_id: str, default_open: bool = True
) -> str:
    """Create a collapsible section with HTML."""
    display_style = "block" if default_open else "none"
    toggle_char = "▼" if default_open else "▶"

    html = f"""
    <div class='activity-section'>
        <div class='activity-section-header' data-section-id='{section_id}' style='cursor: pointer; user-select: none;'>
            <span><span class='section-icon'>{icon}</span>{title}</span>
            <span class='toggle-icon' id='{section_id}-toggle'>{toggle_char}</span>
        </div>
        <div class='activity-section-content' id='{section_id}-content' style='display: {display_style};'>
            {content if content else "<em style='color: #999;'>No activity yet...</em>"}
        </div>
    </div>
    """
    return html


def format_docker_action(action: str, details: str = "") -> str:
    """Format Docker action for display."""
    html = "<div class='docker-info'>"
    html += f"<div><strong>🐳 Docker:</strong> {action}</div>"
    if details:
        html += f"<div style='margin-top: 0.5rem; font-size: 0.9em;'>{details}</div>"
    html += "</div>"
    return html


async def chat_with_agent(
    message: str, history: list[tuple[str, str]], user_id: str
) -> AsyncIterator[tuple[list[tuple[str, str]], str, str, str, str, str, str]]:
    """Chat with the agent and stream responses."""
    global client

    if not message.strip():
        yield (
            history,
            "",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>No reasoning steps yet...</em>",
            "<em style='color: #999;'>Ready...</em>",
            "Please enter a message.",
        )
        return

    # Check if client is initialized
    if client is None:
        error_msg = "Services not initialized. Please wait for startup to complete."
        yield (
            history,
            "",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>No reasoning steps yet...</em>",
            "<em style='color: #999;'>Ready...</em>",
            f"<div style='color: red;'>{error_msg}</div>",
        )
        return

    # Add user message to history
    history.append((message, ""))

    # Initialize tracking with separate sections
    docker_activities = []
    tool_calls_list = []
    reasoning_steps = []
    status_updates = []
    debug_outputs = []

    current_response = ""
    tool_calls_buffer = {}
    displayed_tool_calls = set()  # Track which tool calls we've already displayed
    seen_first_tool_call = False  # Track if we've seen any tool calls
    current_reasoning_text = ""  # Buffer for text before tool calls (represents reasoning)

    # Check if this user already has an initialized container
    global user_containers_initialized
    is_first_execution = user_id not in user_containers_initialized

    # Show initial container status
    if is_first_execution:
        docker_activities.append(format_docker_action("Preparing container", f"User: {user_id}"))
    else:
        docker_activities.append(
            format_docker_action("Container ready", f"✅ Using existing container for {user_id}")
        )

    try:
        # Create chat completion stream
        stream = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": message}],
            stream=True,
            user=user_id,
        )

        # Build organized activity log - returns individual sections for Gradio Accordions
        def build_activity_logs():
            docker_html = (
                "".join(docker_activities)
                if docker_activities
                else "<em style='color: #999;'>No activity yet...</em>"
            )
            tools_html = (
                "".join(tool_calls_list)
                if tool_calls_list
                else "<em style='color: #999;'>No activity yet...</em>"
            )
            reasoning_html = (
                "".join(reasoning_steps)
                if reasoning_steps
                else "<em style='color: #999;'>No reasoning steps yet...</em>"
            )
            status_html = (
                "".join(status_updates)
                if status_updates
                else "<em style='color: #999;'>Ready...</em>"
            )
            debug_html = (
                "".join(debug_outputs)
                if debug_outputs
                else "<em style='color: #999;'>No debug output...</em>"
            )

            return docker_html, tools_html, reasoning_html, status_html, debug_html

        yield history, current_response, *build_activity_logs()

        # Process stream
        async for chunk in stream:
            logger.debug(f"chunk: {chunk.model_dump()}")
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # Handle content (agent's response)
            if delta.content:
                # Check if this is debug content
                if is_debug_content(delta.content):
                    # Add to debug section (collapsed by default)
                    debug_outputs.append(
                        f"<div style='margin: 0.5rem 0; padding: 0.5rem; background: #f5f5f5; border-left: 3px solid #999; font-family: monospace; font-size: 0.85em; white-space: pre-wrap;'>{delta.content}</div>"
                    )
                else:
                    # If we haven't seen tool calls yet, this is reasoning/thinking
                    if not seen_first_tool_call and delta.content.strip():
                        current_reasoning_text += delta.content

                    # Add to chat response
                    current_response += delta.content
                    # Update the last message in history
                    history[-1] = (message, current_response)

                yield history, current_response, *build_activity_logs()

            # Handle tool calls
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    tool_id = tool_call.id if tool_call.id else f"tool_{len(tool_calls_buffer)}"

                    if tool_id not in tool_calls_buffer:
                        tool_calls_buffer[tool_id] = {"name": "", "arguments": ""}

                    if tool_call.function:
                        if tool_call.function.name:
                            tool_calls_buffer[tool_id]["name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            tool_calls_buffer[tool_id]["arguments"] += tool_call.function.arguments

            # After processing all tool calls in this chunk, check for complete ones to display
            for tool_id, tool_data in tool_calls_buffer.items():
                # Only display if we have both name and arguments, and haven't displayed yet
                if (
                    tool_data["name"]
                    and tool_data["arguments"]
                    and tool_id not in displayed_tool_calls
                ):
                    # Check if arguments are complete JSON
                    try:
                        json.loads(tool_data["arguments"])
                        # JSON is valid, tool call is complete
                        displayed_tool_calls.add(tool_id)

                        tool_name = tool_data["name"]
                        tool_args = tool_data["arguments"]

                        # Mark that we've seen a tool call (stops reasoning capture)
                        if not seen_first_tool_call:
                            seen_first_tool_call = True

                            # Add any buffered reasoning text before first tool call
                            if current_reasoning_text.strip():
                                reasoning_steps.append(
                                    format_reasoning_step(current_reasoning_text.strip())
                                )
                                current_reasoning_text = ""

                            # For first-time users, show container initialization NOW (before tool execution)
                            if (
                                is_first_execution
                                and docker_activities
                                and "Preparing container" in docker_activities[0]
                            ):
                                # Replace "Preparing container" with "Initializing container"
                                docker_activities[0] = format_docker_action(
                                    "Initializing container", f"User: {user_id}"
                                )

                        # Add to tool calls section
                        tool_calls_list.append(format_tool_call(tool_name, tool_args))

                        # Add Docker-specific info
                        if tool_name == "execute_bash":
                            try:
                                args = json.loads(tool_args)
                                cmd = args.get("command", "")
                                docker_activities.append(
                                    format_docker_action("Executing command", f"<code>{cmd}</code>")
                                )
                            except (json.JSONDecodeError, KeyError):
                                pass
                        elif tool_name == "write_file":
                            try:
                                args = json.loads(tool_args)
                                path = args.get("file_path", "")
                                docker_activities.append(
                                    format_docker_action(
                                        "Writing file", f"Path: <code>{path}</code>"
                                    )
                                )
                            except (json.JSONDecodeError, KeyError):
                                pass
                        elif tool_name == "read_file":
                            try:
                                args = json.loads(tool_args)
                                path = args.get("file_path", "")
                                docker_activities.append(
                                    format_docker_action(
                                        "Reading file", f"Path: <code>{path}</code>"
                                    )
                                )
                            except (json.JSONDecodeError, KeyError):
                                pass

                        yield history, current_response, *build_activity_logs()
                    except json.JSONDecodeError:
                        # Arguments not complete yet, wait for more chunks
                        pass

            # Handle finish reason
            if choice.finish_reason:
                if choice.finish_reason == "stop":
                    status_updates.append(
                        "<div style='margin: 1rem 0; padding: 0.5rem; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px;'>✅ <strong>Completed</strong></div>"
                    )

                    # Mark container as ready after successful completion (first time only)
                    if is_first_execution and seen_first_tool_call:
                        user_containers_initialized.add(user_id)
                        # Update docker status to show container is ready
                        if docker_activities and "Initializing container" in docker_activities[0]:
                            docker_activities.append(
                                format_docker_action(
                                    "Container ready",
                                    "✅ Successfully initialized and ready for commands",
                                )
                            )

                elif choice.finish_reason == "tool_calls":
                    reasoning_steps.append(format_reasoning_step("Processing tool call results..."))

                yield history, current_response, *build_activity_logs()

    except Exception as e:
        error_msg = f"Error: {e!s}"
        logger.error(f"Chat error: {e}", exc_info=True)
        status_updates.append(
            f"<div style='margin: 1rem 0; padding: 0.5rem; background: #f8d7da; border-left: 4px solid #dc3545; border-radius: 4px;'>❌ <strong>Error:</strong> {error_msg}</div>"
        )
        yield history, current_response, *build_activity_logs()


async def refresh_health() -> str:
    """Refresh health status."""
    health = await check_health()
    return format_health_status(health)


def clear_chat() -> tuple[list, str, str, str, str, str, str]:
    """Clear chat history and activity log."""
    return (
        [],
        "",
        "<em style='color: #999;'>No activity yet...</em>",
        "<em style='color: #999;'>No activity yet...</em>",
        "<em style='color: #999;'>No reasoning steps yet...</em>",
        "<em style='color: #999;'>Ready...</em>",
        "<em style='color: #999;'>No debug output...</em>",
    )


# Create Gradio interface
with gr.Blocks(css=CUSTOM_CSS, title="Code Execution with MCP") as demo:
    # Header
    gr.HTML("""
        <div class="header">
            <h1>🚀 Code Execution with MCP</h1>
            <p>Secure, containerized code execution platform for AI agents</p>
        </div>
    """)

    # Info Section
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("""
            ### 📖 What is this?

            This platform enables AI agents to execute code safely in isolated Docker containers.
            Each user gets their own secure environment with:

            - **Per-user isolation**: Your code runs in your own Docker container
            - **Multi-language support**: Python, bash, and more
            - **Pre-installed libraries**: NumPy, SymPy, Pandas, and other common tools
            - **Skill system**: Domain-specific knowledge for specialized tasks
            - **Real-time monitoring**: Watch the agent's reasoning and tool usage

            ### 🛠️ How it works

            1. **You ask** a question or request a task
            2. **Agent reasons** about the best approach using Google ADK
            3. **Tools execute** in isolated Docker containers via MCP protocol
            4. **Results stream** back to you in real-time

            ### 🔒 Security Features

            - Non-root execution in containers
            - Read-only access to shared resources
            - Timeout protection for long-running tasks
            - Per-user workspace isolation
            """)

        with gr.Column(scale=1):
            gr.Markdown("### 🏥 System Status")
            health_display = gr.HTML(label="Health Status")
            refresh_btn = gr.Button("🔄 Refresh Status", size="sm")

            gr.Markdown("### 👤 User Session")
            user_id_display = gr.Textbox(
                label="Your User ID", value=f"user-{uuid.uuid4().hex[:8]}", interactive=False
            )
            new_session_btn = gr.Button("🔄 New Session", size="sm")

    gr.Markdown("---")

    # Chat Interface
    gr.Markdown("### 💬 Chat with Agent")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="Conversation", height=500, show_copy_button=True)

            with gr.Row():
                msg_input = gr.Textbox(
                    label="Your Message",
                    placeholder="Ask me to execute code, analyze data, solve math problems...",
                    lines=3,
                    scale=4,
                )
                with gr.Column(scale=1):
                    submit_btn = gr.Button("📤 Send", variant="primary")
                    clear_btn = gr.Button("🗑️ Clear", variant="secondary")

        with gr.Column(scale=1):
            gr.Markdown("### 🔍 Agent Activity Monitor")
            with gr.Accordion("🐳 Docker Operations", open=True):
                docker_log = gr.HTML(value="<em style='color: #999;'>No activity yet...</em>")
            with gr.Accordion("🔧 Tool Calls", open=True):
                tools_log = gr.HTML(value="<em style='color: #999;'>No activity yet...</em>")
            with gr.Accordion("🤔 Agent Reasoning", open=False):
                reasoning_log = gr.HTML(
                    value="<em style='color: #999;'>No reasoning steps yet...</em>"
                )
            with gr.Accordion("✅ Status", open=True):
                status_log = gr.HTML(value="<em style='color: #999;'>Ready...</em>")
            with gr.Accordion("🔍 Debug/Raw Output", open=False):
                debug_log = gr.HTML(value="<em style='color: #999;'>No debug output...</em>")

    # Examples
    gr.Markdown("### 💡 Example Queries")
    gr.Examples(
        examples=[
            ["Write a Python script to calculate the factorial of 10"],
            ["Create a plot showing sine and cosine waves from 0 to 2π"],
            ["Find the derivative of x³ + 2x² - 5x + 3 using SymPy"],
            ["Write a bash script to list all .py files in the workspace"],
            ["Generate 100 random numbers and calculate their mean and standard deviation"],
        ],
        inputs=msg_input,
    )

    # Event handlers
    async def submit_message(message, history, user_id):
        async for h, _resp, d_log, t_log, r_log, s_log, dbg_log in chat_with_agent(
            message, history, user_id
        ):
            yield h, "", d_log, t_log, r_log, s_log, dbg_log

    submit_btn.click(
        fn=submit_message,
        inputs=[msg_input, chatbot, user_id_display],
        outputs=[chatbot, msg_input, docker_log, tools_log, reasoning_log, status_log, debug_log],
    )

    msg_input.submit(
        fn=submit_message,
        inputs=[msg_input, chatbot, user_id_display],
        outputs=[chatbot, msg_input, docker_log, tools_log, reasoning_log, status_log, debug_log],
    )

    clear_btn.click(
        fn=clear_chat,
        outputs=[chatbot, msg_input, docker_log, tools_log, reasoning_log, status_log, debug_log],
    )

    refresh_btn.click(fn=refresh_health, outputs=health_display)

    new_session_btn.click(fn=lambda: f"user-{uuid.uuid4().hex[:8]}", outputs=user_id_display)

    # Load health status on startup
    demo.load(fn=refresh_health, outputs=health_display)

    # Add JavaScript for collapsible sections
    demo.load(
        js="""
        function() {
            console.log('Setting up collapsible sections...');

            // Use setTimeout to ensure DOM is ready
            setTimeout(function() {
                document.addEventListener('click', function(e) {
                    const header = e.target.closest('.activity-section-header');
                    if (!header) return;

                    const sectionId = header.getAttribute('data-section-id');
                    if (!sectionId) return;

                    console.log('Toggling section:', sectionId);

                    const content = document.getElementById(sectionId + '-content');
                    const toggle = document.getElementById(sectionId + '-toggle');

                    if (content && toggle) {
                        if (content.style.display === 'none') {
                            content.style.display = 'block';
                            toggle.textContent = '▼';
                        } else {
                            content.style.display = 'none';
                            toggle.textContent = '▶';
                        }
                    }
                });
                console.log('Collapsible sections initialized');
            }, 500);
        }
        """
    )

    # Footer
    gr.Markdown("""
    ---
    <div style='text-align: center; color: #666; padding: 1rem 0;'>
        <p>Built with ❤️ using FastMCP, Google ADK, and Gradio</p>
        <p>Team: <a href='https://huggingface.co/mohar1406' target='_blank'>Mohar Dey</a> •
        <a href='https://huggingface.co/jkadowak' target='_blank'>Jonathan Kadowaki</a></p>
    </div>
    """)


if __name__ == "__main__":
    # Start Gradio UI
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
