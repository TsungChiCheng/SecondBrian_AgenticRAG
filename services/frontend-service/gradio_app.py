# ui/gradio_app.py
from __future__ import annotations

import argparse, datetime, requests, gradio as gr
from config.config import settings

API_BASE = f"http://{settings.API_HOST}:{settings.API_PORT}"

# ───────────────────────── helpers ──────────────────────────
def ask_question(user_input: str):
    try:
        r = requests.post(f"{API_BASE}/ask", json={"user_input": user_input}, timeout=30)
        if r.status_code != 200:
            return "(Error)", "", f"❌ {r.status_code}: {r.text}", gr.update(value=user_input)

        data = r.json()
        answers = data.get("answers", {})
        answers_str = "\n".join(f"{k}: {v}" for k, v in answers.items()) if isinstance(answers, dict) else str(answers)
        return data.get("summary", "(No summary)"), answers_str, "✅ Success", gr.update(value="")
    except Exception as e:
        return "(Error)", "", f"❌ Exception: {e}", gr.update(value=user_input)

def reset_memory():
    try:
        r = requests.post(f"{API_BASE}/reset", timeout=10)
        if r.status_code == 200:
            return "", "", "✅ Memory cleared"
        return "", "", f"❌ Reset failed ({r.status_code})"
    except Exception as e:
        return "", "", f"❌ Exception: {e}"

def daily_summarize(day_str: str):
    try:
        r = requests.post(f"{API_BASE}/tools/daily_summarizer", json={"day": day_str}, timeout=60)
        if r.status_code != 200:
            return None, f"❌ {r.status_code}: {r.text}"
        data = r.json()
        return data["items"], f"✅ Summarized {data['entries_count']} Q&A items"
    except Exception as e:
        return None, f"❌ Exception: {e}"

# ─────────────────────────  UI  ─────────────────────────────
with gr.Blocks(title="Second-Brain UI") as demo:
    gr.Markdown("## 🌐 LangChain Ask App")

    with gr.Row():
        prompt = gr.Textbox(label="Your Question", placeholder="e.g. What is the capital of France?")
        send_btn = gr.Button("Send")

    reset_btn = gr.Button("Reset Memory")
    summary   = gr.Textbox(label="Summary", interactive=False)
    answers   = gr.Textbox(label="Answers", lines=10, interactive=False)
    status    = gr.Markdown()

    gr.Markdown("---")
    gr.Markdown("### 🗓️ Daily Knowledge Tools")

    day_input  = gr.Textbox(
        label="Day (YYYY-MM-DD)",
        value=datetime.date.today().isoformat(),
        info="Date of logs to summarise"
    )

    summarize_btn = gr.Button("Daily Summarize")
    json_out = gr.JSON(label="Topic → Knowledge Points")  # shows summarizer output
    status2  = gr.Markdown()

    # Wiring
    send_btn.click(
        fn=ask_question,
        inputs=prompt,
        outputs=[summary, answers, status, prompt],
    )
    reset_btn.click(fn=reset_memory, outputs=[summary, answers, status])

    summarize_btn.click(
        fn=daily_summarize,
        inputs=day_input,
        outputs=[json_out, status2],
    )

# ───────────────────── launch server  ───────────────────────
cli = argparse.ArgumentParser()
cli.add_argument("--server-port", type=int, default=settings.UI_PORT)
cli.add_argument("--server-name", default=settings.API_HOST)
args, _ = cli.parse_known_args()

demo.launch(
    server_name=args.server_name,
    server_port=args.server_port,
    share=settings.GRADIO_SHARE,
)