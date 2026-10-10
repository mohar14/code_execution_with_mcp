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

PROJECT_ROOT = Path(__file__).parent.parent.absolute()

load_dotenv(PROJECT_ROOT / ".env")

AGENT_API_URL = os.getenv("AGENT_API_URL", "http://localhost:8000")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "anthropic/claude-sonnet-4-5-20250929")

client = AsyncOpenAI(
    base_url=f"{AGENT_API_URL}/v1",
    api_key="",
)

user_containers_initialized = set()


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

/* Artifact viewer styles */
.artifacts-container {
    margin-top: 15px;
    background: white;
    border-radius: 8px;
    padding: 15px;
    border: 1px solid #e0e0e0;
}

.artifacts-header {
    font-size: 1.1em;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 2px solid #667eea;
    color: #333;
}

.artifacts-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.artifact-item {
    display: flex;
    align-items: center;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 6px;
    border-left: 3px solid #667eea;
    transition: all 0.2s ease;
}

.artifact-item:hover {
    background: #e9ecef;
    transform: translateX(5px);
}

.artifact-icon {
    font-size: 1.5em;
    margin-right: 12px;
}

.artifact-link {
    color: #667eea;
    text-decoration: none;
    font-weight: 500;
    font-family: 'Monaco', 'Courier New', monospace;
    font-size: 0.95em;
}

.artifact-link:hover {
    text-decoration: underline;
    color: #5568d3;
}
"""


async def check_health() -> dict:
    health_status = {
        "agent_api": {"status": "unknown", "message": ""},
    }

    try:
        async with httpx.AsyncClient() as http_client:
            try:
                response = await http_client.get(f"{AGENT_API_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
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


async def fetch_artifacts(user_id: str) -> list[str]:
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"{AGENT_API_URL}/artifacts/{user_id}", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get("artifacts", [])
    except Exception as e:
        logger.error(f"Failed to fetch artifacts: {e}")
        return []


def format_health_status(health: dict) -> str:
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


def format_artifacts_section(user_id: str, artifacts: list[str]) -> str:
    if not artifacts:
        return """
        <div class="info-box" style="margin-top: 10px;">
            <p>📦 No artifacts generated yet.</p>
            <p style="font-size: 0.9em; color: #666;">
                Artifacts created by the agent will appear here.
            </p>
        </div>
        """

    artifact_links = []
    for artifact in artifacts:
        download_url = f"{AGENT_API_URL}/artifacts/{user_id}/{artifact}"
        icon = "📄"
        if artifact.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
            icon = "🖼️"
        elif artifact.endswith((".pdf",)):
            icon = "📕"
        elif artifact.endswith((".py", ".js", ".ts", ".java", ".cpp")):
            icon = "💻"
        elif artifact.endswith((".csv", ".xlsx", ".json")):
            icon = "📊"

        artifact_links.append(f"""
        <div class="artifact-item">
            <span class="artifact-icon">{icon}</span>
            <a href="{download_url}"
               download="{artifact}"
               class="artifact-link"
               target="_blank">
                {artifact}
            </a>
        </div>
        """)

    artifacts_html = "\n".join(artifact_links)

    return f"""
    <div class="artifacts-container">
        <div class="artifacts-header">
            <strong>📦 Generated Artifacts ({len(artifacts)})</strong>
        </div>
        <div class="artifacts-list">
            {artifacts_html}
        </div>
    </div>
    """


async def refresh_artifacts_display(user_id: str) -> str:
    artifacts = await fetch_artifacts(user_id)
    return format_artifacts_section(user_id, artifacts)


async def parse_stream_event(line: str) -> dict | None:
    if not line.strip() or line.startswith(":"):
        return None

    if line.startswith("data: "):
        data = line[6:]
        if data.strip() == "[DONE]":
            return {"type": "done"}
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    return None


def format_tool_call(tool_name: str, arguments: str) -> str:
    html = "<div class='tool-call'>"
    html += f"<div class='tool-call-header'>🔧 Tool Call: {tool_name}</div>"

    try:
        args = json.loads(arguments)
        html += "<div style='margin-top: 0.5rem;'>"
        html += "<strong>Arguments:</strong><br>"
        for key, value in args.items():
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
    html = "<div class='reasoning-step'>"
    html += "<div><strong>🤔 Agent Reasoning:</strong></div>"
    html += f"<div style='margin-top: 0.5rem;'>{content}</div>"
    html += "</div>"
    return html


def is_debug_content(text: str) -> bool:
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
    if not text or not text.strip():
        return text

    if is_debug_content(text):
        return ""

    return text


def create_collapsible_section(
    title: str, icon: str, content: str, section_id: str, default_open: bool = True
) -> str:
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
    html = "<div class='docker-info'>"
    html += f"<div><strong>🐳 Docker:</strong> {action}</div>"
    if details:
        html += f"<div style='margin-top: 0.5rem; font-size: 0.9em;'>{details}</div>"
    html += "</div>"
    return html


async def chat_with_agent(
    message: str, history: list[tuple[str, str]], user_id: str
) -> AsyncIterator[tuple[list[tuple[str, str]], str, str, str, str, str]]:
    global client

    if not message.strip():
        yield (
            history,
            "",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>Ready...</em>",
            format_artifacts_section("", []),
        )
        return

    if client is None:
        error_msg = "Services not initialized. Please wait for startup to complete."
        yield (
            history,
            "",
            "<em style='color: #999;'>No activity yet...</em>",
            "<em style='color: #999;'>No activity yet...</em>",
            f"<div style='color: red;'>{error_msg}</div>",
            format_artifacts_section("", []),
        )
        return

    history.append((message, ""))

    docker_activities = []
    tool_calls_list = []
    status_updates = []

    current_response = ""
    tool_calls_buffer = {}
    displayed_tool_calls = set()
    seen_first_tool_call = False

    global user_containers_initialized
    is_first_execution = user_id not in user_containers_initialized

    if is_first_execution:
        docker_activities.append(format_docker_action("Preparing container", f"User: {user_id}"))
    else:
        docker_activities.append(
            format_docker_action("Container ready", f"✅ Using existing container for {user_id}")
        )

    try:
        stream = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": message}],
            stream=True,
            user=user_id,
        )

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
            status_html = (
                "".join(status_updates)
                if status_updates
                else "<em style='color: #999;'>Ready...</em>"
            )

            return docker_html, tools_html, status_html

        yield history, current_response, *build_activity_logs(), format_artifacts_section("", [])

        async for chunk in stream:
            logger.debug(f"chunk: {chunk.model_dump()}")
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                if not is_debug_content(delta.content):
                    current_response += delta.content
                    history[-1] = (message, current_response)

                yield (
                    history,
                    current_response,
                    *build_activity_logs(),
                    format_artifacts_section("", []),
                )

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

            for tool_id, tool_data in tool_calls_buffer.items():
                if (
                    tool_data["name"]
                    and tool_data["arguments"]
                    and tool_id not in displayed_tool_calls
                ):
                    try:
                        json.loads(tool_data["arguments"])
                        displayed_tool_calls.add(tool_id)

                        tool_name = tool_data["name"]
                        tool_args = tool_data["arguments"]

                        if not seen_first_tool_call:
                            seen_first_tool_call = True

                            if (
                                is_first_execution
                                and docker_activities
                                and "Preparing container" in docker_activities[0]
                            ):
                                docker_activities[0] = format_docker_action(
                                    "Initializing container", f"User: {user_id}"
                                )

                        tool_calls_list.append(format_tool_call(tool_name, tool_args))

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

                        yield (
                            history,
                            current_response,
                            *build_activity_logs(),
                            format_artifacts_section("", []),
                        )
                    except json.JSONDecodeError:
                        pass

            if choice.finish_reason:
                if choice.finish_reason == "stop":
                    status_updates.append(
                        "<div style='margin: 1rem 0; padding: 0.5rem; background: #d4edda; border-left: 4px solid #28a745; border-radius: 4px;'>✅ <strong>Completed</strong></div>"
                    )

                    if is_first_execution and seen_first_tool_call:
                        user_containers_initialized.add(user_id)
                        if docker_activities and "Initializing container" in docker_activities[0]:
                            docker_activities.append(
                                format_docker_action(
                                    "Container ready",
                                    "✅ Successfully initialized and ready for commands",
                                )
                            )

                if choice.finish_reason == "stop":
                    artifacts_html = await refresh_artifacts_display(user_id)
                    yield history, current_response, *build_activity_logs(), artifacts_html
                else:
                    yield (
                        history,
                        current_response,
                        *build_activity_logs(),
                        format_artifacts_section("", []),
                    )

    except Exception as e:
        error_msg = f"Error: {e!s}"
        logger.error(f"Chat error: {e}")
        status_updates.append(
            f"<div style='margin: 1rem 0; padding: 0.5rem; background: #f8d7da; border-left: 4px solid #dc3545; border-radius: 4px;'>❌ <strong>Error:</strong> {error_msg}</div>"
        )
        current_response += (
            "\n\nSomething went wrong during agent execution. Please try again later."
        )
        history[-1] = (message, current_response)
        yield history, current_response, *build_activity_logs(), format_artifacts_section("", [])
        return


async def refresh_health() -> str:
    health = await check_health()
    return format_health_status(health)


def clear_chat() -> tuple[list, str, str, str, str, str]:
    return (
        [],
        "",
        "<em style='color: #999;'>No activity yet...</em>",
        "<em style='color: #999;'>No activity yet...</em>",
        "<em style='color: #999;'>Ready...</em>",
        format_artifacts_section("", []),
    )


def new_session_and_clear() -> tuple[str, list, str, str, str, str, str]:
    new_user_id = f"user-{uuid.uuid4().hex[:8]}"
    cleared = clear_chat()
    return (new_user_id, *cleared)


with gr.Blocks(css=CUSTOM_CSS, title="Code Execution with MCP") as demo:
    gr.HTML("""
        <div class="header">
            <h1>🚀 Code Execution with MCP</h1>
            <p>Secure, containerized code execution platform for AI agents</p>
        </div>
    """)

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

    gr.Markdown("### 💬 Chat with Agent")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="Conversation",
                height=500,
                show_copy_button=True,
                latex_delimiters=[
                    {"left": "$$", "right": "$$", "display": True},
                    {"left": "$", "right": "$", "display": False},
                ],
            )

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
            with gr.Accordion("✅ Status", open=True):
                status_log = gr.HTML(value="<em style='color: #999;'>Ready...</em>")
            with gr.Accordion("📦 Generated Artifacts", open=False):
                gr.Markdown(
                    """
                    View and download files created by the agent during execution.
                    Click any artifact to download it to your machine.
                    """
                )
                with gr.Row():
                    refresh_artifacts_btn = gr.Button(
                        "🔄 Refresh Artifacts", size="sm", variant="secondary"
                    )
                artifacts_display = gr.HTML(
                    value=format_artifacts_section("", []), label="Artifacts"
                )

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

    async def submit_message(message, history, user_id):
        async for h, _resp, d_log, t_log, s_log, a_display in chat_with_agent(
            message, history, user_id
        ):
            yield h, "", d_log, t_log, s_log, a_display

    submit_btn.click(
        fn=submit_message,
        inputs=[msg_input, chatbot, user_id_display],
        outputs=[chatbot, msg_input, docker_log, tools_log, status_log, artifacts_display],
    )

    msg_input.submit(
        fn=submit_message,
        inputs=[msg_input, chatbot, user_id_display],
        outputs=[chatbot, msg_input, docker_log, tools_log, status_log, artifacts_display],
    )

    clear_btn.click(
        fn=clear_chat,
        outputs=[chatbot, msg_input, docker_log, tools_log, status_log, artifacts_display],
    )

    refresh_btn.click(fn=refresh_health, outputs=health_display)

    new_session_btn.click(
        fn=new_session_and_clear,
        outputs=[
            user_id_display,
            chatbot,
            msg_input,
            docker_log,
            tools_log,
            status_log,
            artifacts_display,
        ],
    )

    refresh_artifacts_btn.click(
        fn=refresh_artifacts_display, inputs=[user_id_display], outputs=[artifacts_display]
    )

    demo.load(fn=refresh_health, outputs=health_display)

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

    gr.Markdown("""
    ---
    <div style='text-align: center; color: #666; padding: 1rem 0;'>
        <p>Built with ❤️ using FastMCP, Google ADK, and Gradio</p>
        <p>Team: <a href='https://huggingface.co/mohar1406' target='_blank'>Mohar Dey</a> •
        <a href='https://huggingface.co/jkadowak' target='_blank'>Jonathan Kadowaki</a></p>
    </div>
    """)


if __name__ == "__main__":
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
