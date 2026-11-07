import http.server
import json
import logging
import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

from rag.vector_store import HealthVectorStore
from rag.chatbot import HealthRAGChatbot

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GutBut AI - Trust-Aware Health RAG</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --panel: #1e293b;
            --panel-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #10b981;
            --accent-hover: #059669;
            --user-bubble: #2563eb;
            --bot-bubble: #1e293b;
            --danger: #ef4444;
            --warning: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text-main); display: flex; height: 100vh; overflow: hidden; }

        /* Sidebar */
        aside {
            width: 320px;
            background: #111827;
            border-right: 1px solid var(--panel-border);
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        .logo { font-size: 1.25rem; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
        .control-group { margin-bottom: 24px; }
        .control-label { font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; display: flex; justify-content: space-between; }
        .trust-slider { width: 100%; accent-color: var(--accent); cursor: pointer; }
        .trust-info { font-size: 0.78rem; color: var(--text-muted); margin-top: 6px; line-height: 1.4; }
        .source-list { flex: 1; overflow-y: auto; margin-top: 10px; padding-right: 4px; }
        .source-card {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
            font-size: 0.8rem;
        }
        .source-badge {
            display: inline-block;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            margin-bottom: 4px;
        }
        .badge-pubmed { background: #065f46; color: #6ee7b7; }
        .badge-blog { background: #7c2d12; color: #fdba74; }
        .badge-yt { background: #831843; color: #f9a8d4; }
        .source-url { color: #60a5fa; text-decoration: none; word-break: break-all; display: block; margin-top: 4px; }
        .source-url:hover { text-decoration: underline; }

        /* Main Chat Area */
        main { flex: 1; display: flex; flex-direction: column; background: var(--bg); }
        header {
            padding: 16px 24px;
            border-bottom: 1px solid var(--panel-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header-title { font-size: 1.1rem; font-weight: 600; }
        .header-sub { font-size: 0.8rem; color: var(--text-muted); }
        .chat-container { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }

        .message { display: flex; flex-direction: column; max-width: 80%; animation: fadeIn 0.25s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

        .message.user { align-self: flex-end; }
        .message.bot { align-self: flex-start; }

        .bubble {
            padding: 14px 18px;
            border-radius: 12px;
            font-size: 0.92rem;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .message.user .bubble { background: var(--user-bubble); color: #fff; border-bottom-right-radius: 2px; }
        .message.bot .bubble { background: var(--bot-bubble); color: var(--text-main); border: 1px solid var(--panel-border); border-bottom-left-radius: 2px; }

        .citations-box {
            margin-top: 10px;
            padding: 10px 14px;
            background: #111827;
            border: 1px dashed var(--panel-border);
            border-radius: 8px;
            font-size: 0.78rem;
        }
        .citations-header { font-weight: 600; color: var(--accent); margin-bottom: 6px; }
        .citation-item { margin-bottom: 4px; color: var(--text-muted); }
        .citation-item a { color: #60a5fa; text-decoration: none; }

        /* Input Area */
        footer { padding: 18px 24px; border-top: 1px solid var(--panel-border); background: #111827; }
        .input-bar { display: flex; gap: 12px; }
        input[type="text"] {
            flex: 1;
            padding: 14px 18px;
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            color: var(--text-main);
            font-size: 0.95rem;
            outline: none;
        }
        input[type="text"]:focus { border-color: var(--accent); }
        button {
            padding: 14px 24px;
            background: var(--accent);
            color: #042f2e;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: background 0.15s ease;
        }
        button:hover { background: var(--accent-hover); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
    </style>
</head>
<body>
    <aside>
        <div class="logo">
            <span>🧬</span> GutBut Health AI
        </div>

        <div class="control-group">
            <div class="control-label">
                <span>Trust Filter</span>
                <span id="trust-val">0.00</span>
            </div>
            <input type="range" id="trust-slider" class="trust-slider" min="0" max="1" step="0.05" value="0.00">
            <div class="trust-info" id="trust-desc">
                Retrieving all sources (Blogs, YouTube, PubMed).
            </div>
        </div>

        <div class="control-label">Indexed Sources</div>
        <div class="source-list" id="source-list">
            <!-- Dynamically populated -->
        </div>
    </aside>

    <main>
        <header>
            <div>
                <div class="header-title">Trust-Aware Medical RAG Assistant</div>
                <div class="header-sub">Powered by Google Gemini 3.5 Flash & 3072-dim Embeddings</div>
            </div>
            <button onclick="clearChat()" style="padding: 6px 12px; font-size: 0.8rem; background: #334155; color: #fff;">Clear</button>
        </header>

        <div class="chat-container" id="chat">
            <div class="message bot">
                <div class="bubble">Hello! I am your GutBut evidence-grounded health assistant. 

Ask me anything about the **gut microbiome**, **diet**, **short-chain fatty acids (SCFAs)**, or **metabolic health**.

Adjust the **Trust Filter** on the left to restrict evidence to peer-reviewed research (PubMed) or include consumer blogs and video transcripts.</div>
            </div>
        </div>

        <footer>
            <div class="input-bar">
                <input type="text" id="user-input" placeholder="Ask a health question (e.g. How does fiber produce short-chain fatty acids?)..." onkeydown="if(event.key==='Enter') sendQuestion()">
                <button id="send-btn" onclick="sendQuestion()">Ask GutBut</button>
            </div>
        </footer>
    </main>

    <script>
        const chat = document.getElementById('chat');
        const slider = document.getElementById('trust-slider');
        const trustVal = document.getElementById('trust-val');
        const trustDesc = document.getElementById('trust-desc');
        const sourceList = document.getElementById('source-list');

        slider.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value);
            trustVal.textContent = val.toFixed(2);
            if (val >= 0.7) {
                trustDesc.textContent = "Strict: Only peer-reviewed scientific studies (PubMed) will be retrieved.";
                trustDesc.style.color = "#10b981";
            } else if (val >= 0.3) {
                trustDesc.textContent = "Moderate: Peer-reviewed papers and reputable channels.";
                trustDesc.style.color = "#f59e0b";
            } else {
                trustDesc.textContent = "Permissive: All sources included (Blogs, Videos, PubMed).";
                trustDesc.style.color = "#94a3b8";
            }
        });

        async function loadSources() {
            try {
                const res = await fetch('/api/sources');
                const data = await res.json();
                sourceList.innerHTML = '';
                data.forEach(s => {
                    const card = document.createElement('div');
                    card.className = 'source-card';
                    const badgeClass = s.type === 'pubmed' ? 'badge-pubmed' : (s.type === 'youtube' ? 'badge-yt' : 'badge-blog');
                    card.innerHTML = `
                        <span class="source-badge ${badgeClass}">${s.type.toUpperCase()} • Trust ${s.trust.toFixed(2)}</span>
                        <div style="font-weight: 600; color: #fff;">${s.author || 'Unknown'}</div>
                        <div style="color: #64748b; font-size: 0.72rem;">${s.chunks} chunks • ${s.date || 'N/A'}</div>
                        <a href="${s.url}" target="_blank" class="source-url">${s.url.substring(0, 36)}...</a>
                    `;
                    sourceList.appendChild(card);
                });
            } catch (e) {
                console.error(e);
            }
        }

        async function sendQuestion() {
            const input = document.getElementById('user-input');
            const query = input.value.trim();
            if (!query) return;

            const sendBtn = document.getElementById('send-btn');
            input.value = '';
            input.disabled = true;
            sendBtn.disabled = true;

            // Append user message
            const uMsg = document.createElement('div');
            uMsg.className = 'message user';
            uMsg.innerHTML = `<div class="bubble">${query}</div>`;
            chat.appendChild(uMsg);
            chat.scrollTop = chat.scrollHeight;

            // Append loading bot message
            const bMsg = document.createElement('div');
            bMsg.className = 'message bot';
            bMsg.innerHTML = `<div class="bubble"><em>Analyzing vetted medical passages...</em></div>`;
            chat.appendChild(bMsg);
            chat.scrollTop = chat.scrollHeight;

            try {
                const minTrust = parseFloat(slider.value);
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query, min_trust: minTrust })
                });
                const data = await res.json();

                let citationsHtml = '';
                if (data.sources && data.sources.length > 0) {
                    citationsHtml = `<div class="citations-box"><div class="citations-header">📚 Retrieved Evidence (Trust >= ${minTrust.toFixed(2)})</div>`;
                    data.sources.forEach((s, idx) => {
                        citationsHtml += `<div class="citation-item">[${idx+1}] <strong>${s.source_type.toUpperCase()}</strong> by ${s.author} (Trust: ${s.trust_score.toFixed(2)}, Similarity: ${s.similarity.toFixed(2)}) - <a href="${s.source_url}" target="_blank">View Link</a></div>`;
                    });
                    citationsHtml += `</div>`;
                }

                bMsg.innerHTML = `<div class="bubble">${data.answer}${citationsHtml}</div>`;
            } catch (e) {
                bMsg.innerHTML = `<div class="bubble" style="color: #ef4444;">Error: ${e.message}</div>`;
            } finally {
                input.disabled = false;
                sendBtn.disabled = false;
                input.focus();
                chat.scrollTop = chat.scrollHeight;
            }
        }

        function clearChat() {
            chat.innerHTML = `
                <div class="message bot">
                    <div class="bubble">Chat cleared. Ready for your next health question!</div>
                </div>
            `;
        }

        loadSources();
    </script>
</body>
</html>
"""

class RAGHttpHandler(http.server.BaseHTTPRequestHandler):
    vector_store: HealthVectorStore = None
    chatbot: HealthRAGChatbot = None

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._set_headers(200, "text/html; charset=utf-8")
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if parsed.path == "/api/sources":
            seen = {}
            for c in self.vector_store.chunks:
                url = c["source_url"]
                if url not in seen:
                    seen[url] = {
                        "url": url,
                        "type": c["source_type"],
                        "author": c["author"],
                        "trust": c["trust_score"],
                        "date": c["published_date"],
                        "chunks": 0
                    }
                seen[url]["chunks"] += 1

            self._set_headers(200, "application/json")
            self.wfile.write(json.dumps(list(seen.values())).encode("utf-8"))
            return

        self._set_headers(404, "text/plain")
        self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
                query = payload.get("query", "").strip()
                min_trust = float(payload.get("min_trust", 0.0))

                if not query:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Empty query"}).encode("utf-8"))
                    return

                res = self.chatbot.ask(query, min_trust_score=min_trust)
                self._set_headers(200)
                self.wfile.write(json.dumps(res).encode("utf-8"))
            except Exception as e:
                logging.error(f"Chat API error: {e}")
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404, "text/plain")
        self.wfile.write(b"Not Found")

def start_server(port=8000):
    logging.info("Initializing Vector Store & Chatbot for Web UI...")
    store = HealthVectorStore()
    bot = HealthRAGChatbot(vector_store=store)

    RAGHttpHandler.vector_store = store
    RAGHttpHandler.chatbot = bot

    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, RAGHttpHandler)
    logging.info(f"🚀 GutBut RAG Web UI running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down Web UI...")
        httpd.server_close()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port)

