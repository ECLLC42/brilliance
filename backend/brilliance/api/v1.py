# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
from brilliance.agents.workflows import (
    orchestrate_research,
    multi_source_search,
    prepare_results_for_synthesis,
)
from brilliance.synthesis.synthesis_tool import synthesize_papers_async
import logging

load_dotenv()
app = Flask(__name__)

# Allow requests from the deployed front-end
frontend_origin = os.getenv("FRONTEND_URL", "*")
CORS(app, origins=frontend_origin)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.route("/health")
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"})

@app.route("/collect", methods=["POST"])
def collect():
    """Step 1 – gather papers from all sources and return raw results + optimization metadata."""
    try:
        data = request.get_json(force=True)
        query = data.get("query")
        if not query:
            return jsonify({"error": "No query provided"}), 400

        logger.info(f"Collecting papers for query: {query}")
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Multi-source search (no synthesis)
        search_results = loop.run_until_complete(multi_source_search(query))
        payload = prepare_results_for_synthesis(search_results)
        loop.close()
        return jsonify(payload)
    except Exception as e:
        logger.exception("Error during collect phase")
        return jsonify({"error": str(e)}), 500


@app.route("/synthesize", methods=["POST"])
def synthesize():
    """Step 2 – given raw_results and query metadata, run LLM synthesis and return summary."""
    try:
        data = request.get_json(force=True)
        raw_results = data.get("raw_results")
        optimized_query = data.get("optimized_query", {})
        user_query = data.get("query", "") or " ".join(optimized_query.get("keywords", []))

        if not raw_results or not isinstance(raw_results, dict):
            return jsonify({"error": "raw_results must be provided"}), 400

        # Build combined paper text block
        combined_papers = ""
        for source, content in raw_results.items():
            if content and isinstance(content, str) and not content.startswith("Error") and content.strip():
                combined_papers += f"\n=== {source.upper()} Results ===\n{content}\n"

        if not combined_papers.strip():
            return jsonify({"error": "No valid papers to synthesize"}), 400

        synthesis_prompt = f"User Query: {user_query}\n\nPaper Data:\n{combined_papers}"

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        summary_text = loop.run_until_complete(synthesize_papers_async(synthesis_prompt))
        loop.close()

        return jsonify({"synthesis": summary_text})
    except Exception as e:
        logger.exception("Error during synthesis phase")
        return jsonify({"error": str(e)}), 500


# Existing legacy endpoint left for backward compatibility
@app.route("/research", methods=["POST"])
def research():
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            query = data.get('query')
        else:
            # Handle form data from the simple HTML form
            query = request.form.get('query')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
            
        logger.info(f"Processing research query: {query}")
        
        # Use the research orchestration workflow
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(orchestrate_research(query))
        loop.close()
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error processing research query: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run()