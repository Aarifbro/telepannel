import asyncio
import time
import threading
from typing import Set, List

import aiohttp

# ====== PROXY SOURCES (HTTP) ======
PROXY_SOURCES = [
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/proxies/http.txt",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://openproxy.space/list/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://www.freeproxy.world/?format=txt&type=http",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/xResults/Proxies.txt",
    "https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/list/http.txt",
    "https://raw.githubusercontent.com/oxylabs/free-proxy-list/main/http.txt",
    "https://api.openproxylist.xyz/http.txt",
    "https://www.proxyscan.io/api/proxy?format=txt&limit=500&type=http",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTP_RAW.txt",
    "http://pubproxy.com/api/proxy?format=txt&type=http&limit=500",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/Volodichevca/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/elliotwutingfeng/HTTP-Proxy/main/http.txt",
    "https://raw.githubusercontent.com/AsliddinTojiboyev/proxylist/main/http.txt",
    "https://raw.githubusercontent.com/sunny9577/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/hanwayTech/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTP.txt",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
]

# ====== CHECKING CONFIG (Telegram-safe) ======
TEST_URLS = [
    "http://httpbin.org/ip",
    "http://icanhazip.com",
]
FETCH_TIMEOUT = aiohttp.ClientTimeout(total=12)
CHECK_TIMEOUT = aiohttp.ClientTimeout(total=6)
FETCH_CONCURRENCY = 50      # fetch sources gently
CHECK_CONCURRENCY = 50     # accuracy-biased
PROGRESS_INTERVAL = 10     # seconds
OUTPUT_FILE = "working_proxies.txt"


# ====== INTERNAL HELPERS ======

async def _fetch_source(session: aiohttp.ClientSession, url: str) -> Set[str]:
    proxies = set()
    try:
        async with session.get(url, timeout=FETCH_TIMEOUT) as r:
            if r.status != 200:
                return proxies
            text = await r.text()
    except Exception:
        return proxies

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # normalize ip:port only
        if ":" in line and " " not in line:
            proxies.add(line)
    return proxies


async def _fetch_proxies(target_amount: int) -> List[str]:
    collected: Set[str] = set()
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    async with aiohttp.ClientSession() as session:
        async def guarded_fetch(url):
            async with sem:
                return await _fetch_source(session, url)

        tasks = [guarded_fetch(url) for url in PROXY_SOURCES]

        for coro in asyncio.as_completed(tasks):
            batch = await coro
            collected |= batch
            if len(collected) >= int(target_amount * 1.4):  # headroom
                break

    return list(collected)


async def _check_one(session, proxy: str, sem: asyncio.Semaphore):
    proxy_url = f"http://{proxy}"
    async with sem:
        for url in TEST_URLS:
            try:
                async with session.get(url, proxy=proxy_url, timeout=CHECK_TIMEOUT) as r:
                    if r.status != 200:
                        return None
            except Exception:
                return None
        return proxy


async def _check_proxies(
    proxies: List[str],
    target_amount: int,
    progress_cb
):
    sem = asyncio.Semaphore(CHECK_CONCURRENCY)
    checked = 0
    live: List[str] = []
    last_update = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [_check_one(session, p, sem) for p in proxies]

        for coro in asyncio.as_completed(tasks):
            res = await coro
            checked += 1
            if res:
                live.append(res)

            now = time.time()
            if now - last_update >= PROGRESS_INTERVAL:
                await progress_cb(checked, len(live))
                last_update = now

            if checked >= target_amount:
                break

    # final update
    await progress_cb(checked, len(live))
    return live, checked


# ====== PUBLIC ENTRY POINT ======

def start_live_proxy_job(
    bot,
    user_states,
    user_id: int,
    chat_id: int,
    message_id: int,
    target_amount: int
):
    """
    Called by tools_handler.py.
    Runs in background thread, manages asyncio loop internally.
    """

    from tools_handler import (
        update_live_proxy_progress,
        finish_live_proxy_job,
        # same dict passed to register_tools_handlers
    )

    def _thread_runner():
        async def _run():
            # ---- FETCH ----
            proxies = await _fetch_proxies(target_amount)

            # ---- CHECK ----
            async def progress_cb(checked, live):
                update_live_proxy_progress(
                    bot=bot,
                    chat_id=chat_id,
                    message_id=message_id,
                    target=target_amount,
                    checked=checked,
                    live=live,
                    status="RUNNING",
                )

            live_list, checked = await _check_proxies(
                proxies=proxies,
                target_amount=target_amount,
                progress_cb=progress_cb,
            )

            # ---- WRITE FILE ----
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                for p in live_list:
                    f.write(p + "\n")

            # ---- FINISH (UI + FILE SEND) ----
            finish_live_proxy_job(
                bot=bot,
                user_states=user_states,
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                target=target_amount,
                checked=checked,
                live=len(live_list),
            )

        asyncio.run(_run())

    threading.Thread(target=_thread_runner, daemon=True).start()

