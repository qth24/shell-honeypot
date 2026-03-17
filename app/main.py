import asyncio
import logging
import os
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(title="Cowrie Web Honeypot")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
logger = logging.getLogger("honeypot.web")


TELNET_IAC = 255
TELNET_DONT = 254
TELNET_DO = 253
TELNET_WONT = 252
TELNET_WILL = 251
TELNET_SB = 250
TELNET_SE = 240


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _auto_login_enabled() -> bool:
    return env("AUTO_LOGIN_USERNAME", "").strip() != ""


async def connect_to_cowrie(host: str, port: int, retries: int = 15, delay: float = 2.0) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    last_error: OSError | None = None

    for attempt in range(1, retries + 1):
        try:
            return await asyncio.open_connection(host, port)
        except OSError as exc:
            last_error = exc
            logger.warning(
                "connect to cowrie failed attempt=%s/%s host=%s port=%s error=%s",
                attempt,
                retries,
                host,
                port,
                exc,
            )
            if attempt < retries:
                await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "banner": env("SHELL_BANNER", "Cowrie Web Console"),
            "cowrie_host": env("COWRIE_HOST", "cowrie"),
            "cowrie_port": int(env("COWRIE_PORT", "2223")),
        }
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def _telnet_reply(command: int, option: int) -> bytes:
    if command == TELNET_DO:
        return bytes([TELNET_IAC, TELNET_WONT, option])
    if command == TELNET_DONT:
        return bytes([TELNET_IAC, TELNET_WONT, option])
    if command == TELNET_WILL:
        return bytes([TELNET_IAC, TELNET_DO, option])
    if command == TELNET_WONT:
        return bytes([TELNET_IAC, TELNET_DONT, option])
    return b""


async def pump_telnet_to_ws(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, ws: WebSocket) -> None:
    pending = bytearray()
    in_subnegotiation = False
    login_buffer = ""
    sent_username = False
    sent_password = False

    while True:
        chunk = await reader.read(1024)
        if not chunk:
            break

        if pending:
            data = bytes(pending) + chunk
            pending.clear()
        else:
            data = chunk

        out = bytearray()
        i = 0

        while i < len(data):
            byte = data[i]

            if in_subnegotiation:
                if byte == TELNET_IAC and i + 1 < len(data) and data[i + 1] == TELNET_SE:
                    in_subnegotiation = False
                    i += 2
                    continue
                i += 1
                continue

            if byte != TELNET_IAC:
                out.append(byte)
                i += 1
                continue

            if i + 1 >= len(data):
                pending.extend(data[i:])
                break

            command = data[i + 1]

            if command == TELNET_IAC:
                out.append(TELNET_IAC)
                i += 2
                continue

            if command == TELNET_SB:
                if i + 2 >= len(data):
                    pending.extend(data[i:])
                    break
                in_subnegotiation = True
                i += 2
                continue

            if i + 2 >= len(data):
                pending.extend(data[i:])
                break

            option = data[i + 2]
            reply = _telnet_reply(command, option)
            if reply:
                writer.write(reply)
                await writer.drain()
            i += 3

        if out:
            logger.info("telnet->ws bytes=%s raw=%r", len(out), bytes(out)[:200])
            text = out.decode("utf-8", errors="ignore")
            logger.info("telnet->ws text=%r", text[:200])
            login_buffer = (login_buffer + text)[-256:]

            if _auto_login_enabled():
                lowered = login_buffer.lower()

                if (not sent_username) and ("login:" in lowered or "username:" in lowered):
                    writer.write(f"{env('AUTO_LOGIN_USERNAME', 'root')}\r\n".encode("utf-8"))
                    await writer.drain()
                    sent_username = True
                    login_buffer = ""
                    continue

                if sent_username and (not sent_password) and "password:" in lowered:
                    writer.write(f"{env('AUTO_LOGIN_PASSWORD', '123')}\r\n".encode("utf-8"))
                    await writer.drain()
                    sent_password = True
                    login_buffer = ""
                    continue

            await ws.send_text(text)


async def pump_ws_to_telnet(ws: WebSocket, writer: asyncio.StreamWriter) -> None:
    while True:
        message = await ws.receive_text()
        logger.info("ws->telnet text=%r", message[:200])
        payload = message.replace("\n", "\r\n").encode("utf-8", errors="ignore")
        writer.write(payload)
        await writer.drain()


@app.websocket("/ws/shell")
async def websocket_shell(ws: WebSocket) -> None:
    await ws.accept()

    host = env("COWRIE_HOST", "cowrie")
    port = int(env("COWRIE_PORT", "2223"))

    try:
        reader, writer = await connect_to_cowrie(host, port)
    except OSError as exc:
        await ws.send_text(f"\r\n[bridge] Unable to reach Cowrie at {host}:{port}: {exc}\r\n")
        await ws.close(code=1011)
        return

    try:
        telnet_task = asyncio.create_task(pump_telnet_to_ws(reader, writer, ws))
        input_task = asyncio.create_task(pump_ws_to_telnet(ws, writer))

        done, pending = await asyncio.wait(
            {telnet_task, input_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    finally:
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        with suppress(Exception):
            await ws.close()
