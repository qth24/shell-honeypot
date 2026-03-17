let socket;
const terminalEl = document.getElementById("terminal");
const fallbackForm = document.getElementById("fallback-form");
const fallbackInput = document.getElementById("fallback-input");

let term = null;
let useFallback = false;
let fallbackBuffer = "";

function setupTerminal() {
  const TerminalCtor = window.Terminal;

  if (!TerminalCtor) {
    useFallback = true;
    fallbackForm.classList.remove("is-hidden");
    terminalEl.classList.add("terminal-fallback");
    terminalEl.textContent = "";
    fallbackInput.focus();
    return;
  }

  try {
    term = new TerminalCtor({
      cursorBlink: true,
      convertEol: false,
      fontFamily: '"IBM Plex Mono", Consolas, monospace',
      fontSize: 16,
      theme: {
        background: "#070a0e",
        foreground: "#d6ffe9",
        cursor: "#69f0ae",
        selectionBackground: "rgba(105, 240, 174, 0.24)",
      },
    });

    term.open(terminalEl);
    term.focus();
  } catch (_error) {
    useFallback = true;
    fallbackForm.classList.remove("is-hidden");
    terminalEl.classList.add("terminal-fallback");
    terminalEl.textContent = "";
    fallbackInput.focus();
  }
}

function write(text) {
  if (useFallback) {
    fallbackBuffer += text;
    terminalEl.textContent = fallbackBuffer;
    terminalEl.scrollTop = terminalEl.scrollHeight;
    return;
  }

  term.write(text);
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/shell`);

  socket.addEventListener("open", () => {
    if (useFallback) {
      fallbackInput.focus();
      return;
    }

    term.focus();
  });

  socket.addEventListener("message", (event) => {
    write(event.data);
  });

  socket.addEventListener("close", () => {
    write("\r\n[connection closed]\r\n");
  });

  socket.addEventListener("error", () => {
    write("\r\n[connection error]\r\n");
  });
}

function send(data) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(data);
  }
}

fallbackForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = fallbackInput.value;
  if (!value) {
    return;
  }

  write(`$ ${value}\r\n`);
  send(`${value}\n`);
  fallbackInput.value = "";
});

setupTerminal();

if (!useFallback) {
  term.onData((data) => {
    send(data);
  });
}

window.addEventListener("resize", () => {
  if (!useFallback) {
    term.focus();
    return;
  }

  fallbackInput.focus();
});

connect();
