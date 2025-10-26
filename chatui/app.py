# Chainlit application main entry point for BSP AI Assistant
# This file handles authentication, chat profiles, startup routines, and message processing
# Supporting both standard LLM providers via LiteLLM and Azure AI Foundry agents

import time
import chainlit as cl
from utils.utils import (
    append_message, init_settings, get_llm_details, get_llm_models, get_logger,
)
from typing import Dict, Optional
from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from utils.chats import chat_completion
from utils.foundry import chat_agent
from deep_research.pipeline import run_deep_research
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

logger = get_logger()


@cl.action_callback("set_mode")
async def set_mode(action: cl.Action):
    """
    Handle mode setting from work/web toggle switch.
    
    Args:
        action: The action object containing the mode payload
    """
    # Sanitize input
    value = str(action.payload.get("mode", "work")).lower()
    if value not in {"work", "web"}:
        value = "null1"

    # Persist to the per-session store
    cl.user_session.set("mode", value)
    logger.info(f"Mode set to: {value}")


@cl.header_auth_callback
def header_auth_callback(headers: Dict) -> Optional[cl.User]:
    """
    Handle authentication using headers from Azure App Service.
    
    Extracts user information from HTTP headers for authentication
    in Azure App Service environments.
    
    Args:
        headers: Dictionary containing HTTP request headers
        
    Returns:
        Optional[cl.User]: User object if authentication successful, None otherwise
    """
    # Verify the signature of a token in the header (ex: jwt token)
    # or check that the value is matching a row from your database
    user_name = headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'dummy@microsoft.com')
    user_id = headers.get('X-MS-CLIENT-PRINCIPAL-ID', '9876543210')
    logger.debug(f"Auth Headers: {headers}")

    if user_name:
        return cl.User(identifier=user_name, metadata={"role": "admin", "provider": "header", "id": user_id})
    else:
        return None



@cl.set_chat_profiles
async def chat_profile():
    llm_models = get_llm_models()  # should return a list[dict]

    profiles = []
    for m in llm_models or []:
        if not isinstance(m, dict):
            continue
        name = (m.get("model_deployment") or "unknown-deployment").strip()
        desc = (m.get("description") or "No description").strip()
        profiles.append(
            cl.ChatProfile(
                name=name,
                markdown_description=desc
            )
        )

    # Fallback if nothing parsed
    if not profiles:
        profiles = [cl.ChatProfile(name="default", markdown_description="Fallback profile")]
    return profiles



@cl.set_starters
async def set_starters():
    """
    Define starter conversation prompts for the chat interface.
    
    Provides pre-configured conversation starters to help users
    begin interactions with the AI assistant.
    
    Returns:
        List[cl.Starter]: List of starter conversation prompts
    """
    return [
        cl.Starter(
            label="Morning routine ideation",
            message="Can you help me create a personalized morning routine that would help increase my productivity throughout the day? Start by asking me about my current habits and what activities energize me in the morning.",
            icon="/public/bulb.webp",
            ),

        cl.Starter(
            label="Spot the errors",
            message="How can I avoid common mistakes when proofreading my work?",
            icon="/public/warning.webp",
            ),
        cl.Starter(
            label="Get more done",
            message="How can I improve my productivity during remote work?",
            icon="/public/rocket.png",
            ),
        cl.Starter(
            label="Boost your knowledge",
            message="Help me learn about [topic]",
            icon="/public/book.png",
            )
        ]


@cl.on_chat_resume
async def on_chat_resume(thread):
    """
    Handle chat resumption when a user returns to an existing conversation.
    
    Args:
        thread: The conversation thread being resumed
    """
    pass


@cl.on_chat_start
async def start():
    """
    Initialize the chat session and send a welcome message.
    
    Sets up chat settings, initializes Azure AI Foundry agents if needed,
    and prepares the conversation environment for the user.
    """
    try:
        cl.user_session.set("chat_settings", await init_settings())
        llm_details = get_llm_details()
        
        # Try to render the bridge element
        try:
            bridge = cl.CustomElement(name="SettingsBridge", props={}, display="inline")
            msg = cl.Message(content="How can I help you today?", author="agent", elements=[bridge])
            await msg.send()
        except Exception as e:
            raise RuntimeError(f"Error on chat start: {str(e)}")

        # Create an instance of the AgentsClient using DefaultAzureCredential
        if cl.user_session.get("chat_settings").get("model_provider") == "foundry" and not cl.user_session.get("thread_id"):
            agents_client = AgentsClient(
                # conn_str=llm_details["api_key"],
                endpoint=llm_details["api_endpoint"],
                credential=DefaultAzureCredential()
            )

            # Create a thread for the agent
            thread = agents_client.threads.create()
            cl.user_session.set("thread_id", thread.id)
            logger.info(f"New thread created, thread ID: {thread.id}")

    except Exception as e:
        await cl.Message(content=f"An error occurred: {str(e)}", author="Error").send()
        logger.error(f"Error: {str(e)}")


@cl.on_message
async def on_message(message: cl.Message):
    user_input = message.content.strip()
    mode = cl.user_session.get("mode", "default")

    # Route to deep research if user typed a command or UI set the mode
    is_research_cmd = user_input.lower().startswith("/research ")
    if is_research_cmd or mode == "deep_research":
        topic = user_input[len("/research "):].strip() if is_research_cmd else user_input

        thinking_box = await cl.Message(author="🧠", content="(thinking…)").send()
        progress_box = await cl.Message(content="Starting research…").send()

        async def notify(event: str, data: dict):
            if event == "thinking":
                # before: await thinking_box.update(content=...)
                thinking_box.content = data.get("thoughts", "")
                await thinking_box.update()

            elif event == "generate_query":
                await cl.Message(
                    content=f"🔎 **Query:** {data['query']}\n\n_Why:_ {data.get('rationale','')}"
                ).send()

            elif event == "web_research":
                await cl.Message(
                    content=f"🌐 Collected {len(data.get('sources', []))} source(s)."
                ).send()

            elif event == "summarize":
                # before: await progress_box.update(content="📝 Updating summary…")
                progress_box.content = "📝 Updating summary…"
                await progress_box.update()

            elif event == "reflection":
                await cl.Message(
                    content=f"🧭 Follow-up query: {data.get('query','')}"
                ).send()

            elif event == "routing":
                await cl.Message(
                    content=f"🔁 Decision: {data['decision']} (loop {data['loop_count']})"
                ).send()

            elif event == "finalize":
                imgs = data.get("images", [])
                elements = [
                    cl.Image(name=f"image-{i+1}", url=u, display="inline")
                    for i, u in enumerate(imgs)
                ]
                await cl.Message(
                    content=data["summary"],   # markdown summary (no <div> HTML)
                    elements=elements          # Chainlit renders the images for you
                ).send()

        try:
            final_md = await run_deep_research(topic, notify=notify)
            if final_md:
                await cl.Message(content="✅ Research complete. See final summary above.").send()
        except Exception as e:
            await cl.Message(content=f"❌ Research error: {e}").send()
        return

    # ---------- normal chat path ----------
    try:
        cl.user_session.set("start_time", time.time())

        # keep your existing logging + session message handling
        # logger.info(f"on_message mode: {mode}")
        msgs = append_message("user", user_input, message.elements)

        provider = cl.user_session.get("chat_settings", {}).get("model_provider")
        if provider == "foundry":
            full_response = await chat_agent(user_input)
        else:
            full_response = await chat_completion(msgs)

        append_message("assistant", full_response)
        await cl.Message(content=full_response).send()

    except Exception as e:
        await cl.Message(content=f"An error occurred: {e}", author="Error").send()
        # logger.error(f"Error: {e}")
