import asyncio
import json
import pathlib
import re

from crewai.agents.parser import AgentFinish
from crewai.tasks.task_output import TaskOutput
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from github_roaster.crew import GithubRoaster


STATIC_DIR = pathlib.Path(__file__).parent.parent / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def _process_roast(username: str, output_queue: asyncio.Queue):
    """Starts the roasting crew, pushing progress to the queue."""
    await output_queue.put({'event': 'progress_update',
                            'status': 'started'})

    roasting_loop = asyncio.get_running_loop()

    def update_hook(msg: TaskOutput | AgentFinish) -> None:
        if not isinstance(msg, TaskOutput):
            # Any step_callbacks are handled here.
            print(msg)
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

        try:
            while True:
                # Poll for updates from the roast task - the callbacks should be
                # sending updates, so the timeout is pretty generous.
                update = await asyncio.wait_for(update_queue.get(), timeout=120)

                output = ''
                # Include an event if one is present.
                if event := update.pop('event', None):
                    output += f'event: {event}\n'

                output += f"data: {json.dumps(update)}\n\n"
                yield output

                # Break if the crew is done.
                if update.get('status') == 'completed':
                    break

        except asyncio.TimeoutError:
            # Handle cases where the task times out between updates.
            yield f"data: {json.dumps({'status': 'error', 'message': 'Stream timed out.'})}\n\n"
            print("Stream timed out: No updates received.")

        except Exception as e:
            # Catch any other exceptions during streaming
            yield f"data: {json.dumps({'status': 'error', 'message': f'An error occurred: {str(e)}'})}\n\n"
            print(f"Error during streaming: {e}")

        finally:
            # Ensure background task is cancelled if the client disconnects or streaming finishes
            if not roast_task.done():
                roast_task.cancel()
            await asyncio.gather(roast_task, return_exceptions=True)

    return StreamingResponse(generate_updates(), media_type="text/event-stream")


@app.get("/")
async def home_page():
    """Redirect to the index in the static dir."""
    return RedirectResponse(url="/static/index.html")
