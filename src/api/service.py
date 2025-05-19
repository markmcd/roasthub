import asyncio
import json
import pathlib
import re
import traceback

from crewai.agents.parser import AgentFinish
from crewai.tasks.task_output import TaskOutput
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import urllib.parse

from github_roaster.crew import GithubRoaster


STATIC_DIR = pathlib.Path(__file__).parent.parent / "static"
KEEPALIVE_INTERVAL_SECS = 5
MAX_KEEPALIVE_SECS = 120

app = FastAPI()
app.mount("/r", StaticFiles(directory=STATIC_DIR), name="static")


async def _process_roast(username: str, output_queue: asyncio.Queue):
    """Starts the roasting crew, pushing progress to the queue."""
    await output_queue.put({'event': 'progress_update',
                            'status': 'started'})

    roasting_loop = asyncio.get_running_loop()

    def update_hook(msg: TaskOutput | AgentFinish) -> None:
        if isinstance(msg, AgentFinish):
            # Any step_callbacks are handled here.
            print(json.dumps({
                'thought': msg.thought,
                'output': msg.output,
                'text': msg.text
            }))
            return

        # Write to the async queue from this (sync) callback by using
        # the outer event loop.
        roasting_loop.call_soon_threadsafe(
            lambda: asyncio.create_task(output_queue.put({
                'event': 'progress_update',
                'task': msg.name,
                'summary': msg.summary,
                'status': 'task_done'
            }))
        )

    crew = GithubRoaster().crew(task_callback=update_hook, step_callback=update_hook)

    result = await crew.kickoff_async(inputs=dict(username=username))
    await output_queue.put({'status': 'completed', 'output': result.raw})


@app.get("/roast")
async def process_roast_stream(username: str):
    """Handle roast API request, with streamed progress events."""

    # Take the first word. GitHub usernames don't have whitespace.
    username, *_ = re.split(r'\s+', username.strip())
    # And to reduce likelihood of a prompt injection, limit the char count too.
    username = username[:128]

    async def generate_updates():
        update_queue = asyncio.Queue()

        # Start the crew running in the background so we don't block.
        roast_task = asyncio.create_task(_process_roast(username, update_queue))

        # Start a task to pull queued events for the main loop.
        data_task = asyncio.create_task(update_queue.get())

        # Start a heartbeat task as a keepalive on mobile devices.
        heartbeat_task = asyncio.create_task(asyncio.sleep(KEEPALIVE_INTERVAL_SECS))

        try:
            while True:
                # Poll for updates from the roast task while sending heartbeat pings.
                done, pending = await asyncio.wait(
                    [data_task, heartbeat_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=MAX_KEEPALIVE_SECS,
                )

                if data_task in done:
                    update = await data_task
                    # Log the message
                    print(json.dumps(update))

                    output = ''
                    # Include an event if one is present.
                    if event := update.pop('event', None):
                        output += f'event: {event}\n'

                    output += f"data: {json.dumps(update)}\n\n"
                    yield output
                    # Get the next queue item.
                    data_task = asyncio.create_task(update_queue.get())

                    # Break if the crew is done.
                    if update.get('status') == 'completed':
                        break

                elif heartbeat_task in done:
                    yield "event: ping\ndata: {}\n\n"
                    # Reset timer.
                    heartbeat_task = asyncio.create_task(asyncio.sleep(KEEPALIVE_INTERVAL_SECS))

                elif not done and pending:  # real timeout
                    raise asyncio.TimeoutError("Stream timed out.")

        except asyncio.TimeoutError:
            # Send an error event if the connection times out.
            yield f"data: {json.dumps({'status': 'error', 'message': 'Stream timed out.'})}\n\n"
            print("Stream timed out: No updates received.")

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'An error occurred: {str(e)}'})}\n\n"
            print(f"Error during streaming: {e}")
            print(json.dumps({
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            }))

        finally:
            # Ensure background task is cancelled if the client disconnects or streaming finishes
            if not roast_task.done():
                roast_task.cancel()
            if not heartbeat_task.done():
                heartbeat_task.cancel()
            if not data_task.done():
                data_task.cancel()

            await asyncio.gather(roast_task, heartbeat_task, return_exceptions=True)

    return StreamingResponse(generate_updates(), media_type="text/event-stream")


@app.get("/")
async def home_page(username: str | None = None):
    """Redirect to the index in the static dir."""
    if username:
        username = urllib.parse.quote_plus(username)
        return RedirectResponse(url=f"/r/index.html?username={username}")
    else:
        return RedirectResponse(url="/r/index.html")
