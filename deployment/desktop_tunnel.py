"""Loopback desktop relay over authenticated SSH exec; no sshd changes."""
import asyncio
import contextlib
import argparse

SSH_HOST = "feiniu"
LOCAL_PORT = REMOTE_PORT = 16080

REMOTE = """import socket,sys,threading
s=socket.create_connection(('127.0.0.1',16080))
def send():
 try:
  while True:
   b=sys.stdin.buffer.read1(65536)
   if not b:break
   s.sendall(b)
 finally:
  s.shutdown(socket.SHUT_WR)
threading.Thread(target=send,daemon=True).start()
while True:
 b=s.recv(65536)
 if not b:break
 sys.stdout.buffer.write(b);sys.stdout.buffer.flush()
"""


async def relay(reader, writer):
    import base64
    encoded = base64.b64encode(REMOTE.replace("16080", str(REMOTE_PORT)).encode()).decode()
    command = f"python3 -u -c \"import base64;exec(base64.b64decode('{encoded}'))\""
    process = await asyncio.create_subprocess_exec(
        'ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
        SSH_HOST, command, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    async def copy(source, target):
        while data := await source.read(65536):
            target.write(data)
            await target.drain()
    tasks = [asyncio.create_task(copy(reader, process.stdin)),
             asyncio.create_task(copy(process.stdout, writer))]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        await process.wait()


async def main():
    server = await asyncio.start_server(relay, '127.0.0.1', LOCAL_PORT)
    print(f'Desktop relay: http://127.0.0.1:{LOCAL_PORT}/vnc.html?autoconnect=1&resize=scale', flush=True)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ssh-host', default='feiniu')
    parser.add_argument('--local-port', type=int, default=16080)
    parser.add_argument('--remote-port', type=int, default=16080)
    args = parser.parse_args()
    SSH_HOST, LOCAL_PORT, REMOTE_PORT = args.ssh_host, args.local_port, args.remote_port
    asyncio.run(main())
