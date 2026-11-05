import http from "node:http";

const PORT = 19090;
const CONTENT = "Reconnaissance complete. No exploitable issues were confirmed.";

function completion(stream) {
  if (stream) return null;
  return {
    id: "chatcmpl-mock",
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: "mock",
    choices: [
      {
        index: 0,
        message: { role: "assistant", content: CONTENT },
        finish_reason: "stop",
      },
    ],
    usage: { prompt_tokens: 12, completion_tokens: 8, total_tokens: 20 },
  };
}

const server = http.createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ status: "ok" }));
    return;
  }
  if (!request.url?.endsWith("/chat/completions") || request.method !== "POST") {
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: { message: "not found" } }));
    return;
  }

  let body = "";
  request.on("data", (chunk) => {
    body += chunk;
  });
  request.on("end", () => {
    let payload = {};
    try {
      payload = JSON.parse(body || "{}");
    } catch {
      payload = {};
    }

    if (payload.stream) {
      response.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
      });
      const chunk = {
        id: "chatcmpl-mock",
        object: "chat.completion.chunk",
        created: Math.floor(Date.now() / 1000),
        model: "mock",
        choices: [
          { index: 0, delta: { role: "assistant", content: CONTENT }, finish_reason: null },
        ],
      };
      response.write(`data: ${JSON.stringify(chunk)}\n\n`);
      response.write(
        `data: ${JSON.stringify({
          id: "chatcmpl-mock",
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: "mock",
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
        })}\n\n`,
      );
      response.write(
        `data: ${JSON.stringify({
          id: "chatcmpl-mock",
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: "mock",
          choices: [],
          usage: { prompt_tokens: 12, completion_tokens: 8, total_tokens: 20 },
        })}\n\n`,
      );
      response.end("data: [DONE]\n\n");
      return;
    }

    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(completion(false)));
  });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[mock-llm] http://127.0.0.1:${PORT}`);
});
