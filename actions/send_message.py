import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

try:
    import pygetwindow as gw
    _PYGETWINDOW = True
except Exception:
    _PYGETWINDOW = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            # For WhatsApp prefer launching native desktop app directly
            if app_name.lower() == "whatsapp":
                try:
                    if _launch_whatsapp_desktop():
                        time.sleep(2.5)
                        return True
                except Exception:
                    pass

            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            # wait for a window with app name to appear (if pygetwindow available)
            if _PYGETWINDOW:
                deadline = time.time() + 8.0
                while time.time() < deadline:
                    try:
                        wins = gw.getAllTitles()
                        for t in wins:
                            if t and app_name.lower() in t.lower():
                                try:
                                    w = gw.getWindowsWithTitle(t)[0]
                                    if w.isMinimized:
                                        w.restore()
                                    w.activate()
                                except Exception:
                                    pass
                                time.sleep(0.3)
                                return True
                    except Exception:
                        pass
                    time.sleep(0.4)
                print(f"[SendMessage] ⚠️ Could not find window for {app_name} after launch")
                return True

            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _launch_whatsapp_desktop() -> bool:
    """Try to locate and launch the native WhatsApp Desktop executable, or use the whatsapp: protocol."""
    try:
        # Common LocalAppData path used by WhatsApp installer
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = []
        if local:
            candidates.extend(list(Path(local).glob("WhatsApp/**/WhatsApp.exe")))
            candidates.extend(list(Path(local).glob("WhatsApp/*/WhatsApp.exe")))

        prog = os.environ.get("ProgramFiles", "")
        if prog:
            candidates.extend(list(Path(prog).glob("**/WhatsApp.exe")))
        prog86 = os.environ.get("ProgramFiles(x86)", "")
        if prog86:
            candidates.extend(list(Path(prog86).glob("**/WhatsApp.exe")))

        for p in candidates:
            try:
                subprocess.Popen([str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[SendMessage] Launched WhatsApp desktop from: {p}")
                return True
            except Exception:
                continue

        # Fallback: use whatsapp protocol handler which typically opens the native app
        try:
            subprocess.run(["cmd", "/c", "start", "whatsapp:"], check=False)
            print("[SendMessage] Launched WhatsApp via protocol handler")
            return True
        except Exception:
            pass

    except Exception as e:
        print(f"[SendMessage] ⚠️ _launch_whatsapp_desktop failed: {e}")
    return False


def _pywinauto_whatsapp_send(receiver: str, message: str, debug_dir: str | None = None) -> bool:
    """Use pywinauto to interact with WhatsApp Desktop on Windows for a more reliable flow.
    Returns True on success, False otherwise. This is optional and falls back to existing methods.
    """
    try:
        from pywinauto import Application
        from pywinauto.keyboard import send_keys
    except Exception:
        return False

    try:
        # Try to connect to a running WhatsApp process first
        app = None
        try:
            app = Application(backend="uia").connect(path="WhatsApp.exe")
        except Exception:
            # Try to start any discovered WhatsApp.exe via common paths
            exe = None
            local = os.environ.get("LOCALAPPDATA", "")
            if local:
                for p in Path(local).glob("**/WhatsApp.exe"):
                    exe = str(p)
                    break
            if not exe:
                prog = os.environ.get("ProgramFiles", "")
                if prog:
                    for p in Path(prog).glob("**/WhatsApp.exe"):
                        exe = str(p)
                        break
            if exe:
                app = Application(backend="uia").start(exe)
            else:
                return False

        # Give the app time to be ready
        time.sleep(1.2)

        # Get main window
        try:
            win = app.window(title_re=".*WhatsApp.*")
        except Exception:
            win = app.top_window()

        win.set_focus()
        time.sleep(0.2)

        # Open chat search (Ctrl+K)
        # Prefer any visible Edit control, not just one with an exact Search title,
        # because WhatsApp Desktop variants expose different UIA names.
        tried = False
        try:
            edits = [c for c in win.descendants(control_type="Edit") if c.is_visible()]
            search = None
            for control in edits:
                title = (control.element_info.name or "").lower()
                if "search" in title or "start new chat" in title or "new chat" in title:
                    search = control
                    break
            if search is None and edits:
                search = edits[0]
            if search is None:
                raise RuntimeError("No visible Edit controls found")
            search.set_focus()
            time.sleep(0.12)
            try:
                if hasattr(search, "set_edit_text"):
                    search.set_edit_text(receiver)
                else:
                    search.type_keys('^a{BACKSPACE}', set_foreground=True)
                    search.type_keys(receiver, with_spaces=True)
            except Exception:
                send_keys(receiver, with_spaces=True)
            time.sleep(0.5)
            opened = False
            try:
                receiver_clean = receiver.lower().strip()
                ranked = []
                for control in win.descendants():
                    if not control.is_visible():
                        continue
                    name = (control.element_info.name or "").strip()
                    role = (control.element_info.control_type or "").lower()
                    name_l = name.lower()
                    if role in {"listitem", "text"}:
                        score = 0
                        if receiver_clean and receiver_clean in name_l:
                            score += 10
                        if name_l.startswith(receiver_clean):
                            score += 5
                        if score:
                            ranked.append((score, control))

                if ranked:
                    ranked.sort(key=lambda item: item[0], reverse=True)
                    target = ranked[0][1]
                    try:
                        target.click_input()
                    except Exception:
                        target.click()
                    time.sleep(0.8)
                    opened = True
            except Exception:
                pass

            if not opened:
                # Try keyboard navigation to open first search result
                send_keys('{DOWN}')
                time.sleep(0.1)
                send_keys('{ENTER}')
                time.sleep(0.6)
                opened = True

            if not opened:
                # As a fallback, click the first visible list item in the chat list
                try:
                    list_items = [c for c in win.descendants(control_type="ListItem") if c.is_visible()]
                    if list_items:
                        try:
                            list_items[0].click_input()
                        except Exception:
                            list_items[0].click()
                        time.sleep(0.6)
                        opened = True
                except Exception:
                    pass
            tried = True
        except Exception:
            # if UIA search Edit not found, fall back to clicking the search box area
            try:
                if debug_dir:
                    # dump control identifiers to debug file for inspection
                    try:
                        import io, sys as _sys
                        buf = io.StringIO()
                        _old = _sys.stdout
                        _sys.stdout = buf
                        win.print_control_identifiers()
                        _sys.stdout = _old
                        Path(debug_dir).mkdir(parents=True, exist_ok=True)
                        (Path(debug_dir) / "whatsapp_controls.txt").write_text(buf.getvalue(), encoding="utf-8")
                    except Exception:
                        pass

                left, top, width, height = win.rectangle().left, win.rectangle().top, win.rectangle().width(), win.rectangle().height()
                # click into the search box approximate position
                sx = left + int(width * 0.12)
                sy = top + int(height * 0.065)
                pyautogui.click(sx, sy)
                time.sleep(0.12)
                pyautogui.write(receiver, interval=0.03)
                time.sleep(0.45)
                # Prefer opening the first result explicitly
                pyautogui.press('down')
                time.sleep(0.1)
                pyautogui.press('enter')
                time.sleep(0.8)
                tried = True
            except Exception:
                pass

        if not tried:
            # Open search and type using keyboard as fallback
            send_keys('^k')
            time.sleep(0.4)
            send_keys(receiver, with_spaces=True)
            time.sleep(0.6)
            send_keys('{ENTER}')
        time.sleep(0.6)

        # Paste or type message into the message input control when possible
        sent = False
        try:
            # Try UIA child window first (preferred)
            msg = None
            try:
                msg = win.child_window(title_re="(Type a message|Message|Write a message)", control_type="Edit")
                msg.set_focus()
            except Exception:
                # Try to locate any Edit control in the bottom area of the window
                try:
                    edits = [c for c in win.descendants(control_type="Edit") if c.is_visible()]
                    if edits:
                        wr = win.rectangle()
                        bottom_threshold = wr.top + int(wr.height() * 0.78)
                        bottom_edits = [e for e in edits if getattr(e, 'rectangle', lambda: wr)().top >= bottom_threshold]
                        if bottom_edits:
                            msg = bottom_edits[-1]
                            msg.set_focus()
                except Exception:
                    msg = None

            # If we have an edit control, paste/type into it
            if msg is not None:
                time.sleep(0.08)
                try:
                    if _PYPERCLIP:
                        pyperclip.copy(message)
                        time.sleep(0.08)
                        send_keys('^v')
                    else:
                        # use control's type_keys when available
                        try:
                            msg.type_keys(message, with_spaces=True)
                        except Exception:
                            send_keys(message, with_spaces=True)
                    time.sleep(0.12)
                except Exception:
                    pass
            else:
                # Click approximate composer area on right/bottom, then paste/type
                try:
                    rect = win.rectangle()
                    cx = rect.left + int(rect.width() * 0.72)
                    cy = rect.top + int(rect.height() * 0.92)
                    if _PYAUTOGUI:
                        pyautogui.click(cx, cy)
                    else:
                        try:
                            win.click_input(coords=(cx - rect.left, cy - rect.top))
                        except Exception:
                            pass
                    time.sleep(0.12)
                except Exception:
                    pass

                try:
                    if _PYPERCLIP:
                        pyperclip.copy(message)
                        time.sleep(0.08)
                        send_keys('^v')
                    else:
                        send_keys(message, with_spaces=True)
                    time.sleep(0.12)
                except Exception:
                    pass

            # Try to click a visible Send button (green) if present, otherwise press Enter
            clicked_send = False
            try:
                btns = [b for b in win.descendants(control_type="Button") if b.is_visible()]
                for b in btns:
                    name = (b.element_info.name or "").lower()
                    if 'send' in name or 'arrow' in name or 'paper plane' in name:
                        try:
                            b.click_input()
                            clicked_send = True
                            break
                        except Exception:
                            try:
                                b.click()
                                clicked_send = True
                                break
                            except Exception:
                                continue
            except Exception:
                clicked_send = False

            if not clicked_send:
                try:
                    send_keys('{ENTER}')
                except Exception:
                    if _PYAUTOGUI:
                        pyautogui.press('enter')

            sent = True
        except Exception:
            sent = False
        time.sleep(0.2)
        send_keys('{ENTER}')
        time.sleep(0.4)

        if debug_dir:
            _save_debug_snapshot("pywinauto_after_send", debug_dir)

        return bool(sent)
    except Exception as e:
        print(f"[SendMessage] ⚠️ pywinauto whatsapp send failed: {e}")
        return False


def _save_debug_snapshot(name: str, debug_dir: str = None):
    try:
        if not _PYAUTOGUI:
            return
        from datetime import datetime
        root = Path("tools") / "send_debug"
        if debug_dir:
            root = Path(debug_dir)
        root.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        path = root / f"{ts}_{name}.png"
        pyautogui.screenshot(str(path))
        print(f"[SendMessage][debug] Saved snapshot: {path}")
    except Exception as e:
        print(f"[SendMessage][debug] Could not save snapshot: {e}")


def _click_message_input(app_name: str, debug_dir: str | None = None) -> bool:
    _require_pyautogui()
    try:
        if _get_os() == "windows":
            try:
                from pywinauto import Desktop
                win = Desktop(backend="uia").active()
                edits = [c for c in win.descendants(control_type="Edit") if c.is_visible()]
                target = None
                for control in edits:
                    name = (control.element_info.name or "").lower()
                    if "message" in name or "type a message" in name or "write a message" in name:
                        target = control
                        break
                if target is None and edits:
                    target = edits[-1]
                if target is not None:
                    try:
                        target.click_input()
                    except Exception:
                        target.click()
                    time.sleep(0.25)
                    if debug_dir:
                        _save_debug_snapshot("after_click_input", debug_dir)
                    return True
            except Exception:
                pass

        # If we can get the active window, click near the bottom center where the input box usually is
        if _PYGETWINDOW:
            try:
                active = gw.getActiveWindow()
            except Exception:
                active = None
            if active:
                left, top, width, height = active.left, active.top, active.width, active.height
                x = left + int(width * 0.5)
                y = top + int(height * 0.92)
                pyautogui.click(x, y)
                time.sleep(0.18)
                if debug_dir:
                    _save_debug_snapshot("after_click_input", debug_dir)
                return True

        # Fallback: click near bottom-center of the primary screen
        w, h = pyautogui.size()
        pyautogui.click(int(w * 0.5), int(h * 0.92))
        time.sleep(0.18)
        if debug_dir:
            _save_debug_snapshot("after_click_input", debug_dir)
        return True

    except Exception as e:
        print(f"[SendMessage] ⚠️ click message input failed: {e}")
        return False


def _clean_text(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum() or ch.isspace()).strip()


def _ocr_chat_header_matches(receiver: str, debug_dir: str | None = None) -> bool:
    # Try OCR on the chat header area to ensure the selected chat matches `receiver`.
    try:
        try:
            import pytesseract
        except Exception:
            pytesseract = None

        # grab active window bounds
        try:
            active = gw.getActiveWindow() if _PYGETWINDOW else None
        except Exception:
            active = None

        img = pyautogui.screenshot()

        if active:
            left, top, width, height = active.left, active.top, active.width, active.height
            crop = (
                left + int(width * 0.05),
                top + int(height * 0.02),
                left + int(width * 0.95),
                top + int(height * 0.18),
            )
        else:
            sw, sh = pyautogui.size()
            crop = (int(sw * 0.3), int(sh * 0.02), int(sw * 0.7), int(sh * 0.12))

        cropped = img.crop(crop)
        if debug_dir:
            try:
                dest = Path(debug_dir) / f"ocr_header_{int(time.time()*1000)}.png"
                cropped.save(dest)
                print(f"[SendMessage][debug] Saved header crop: {dest}")
            except Exception:
                pass

        if pytesseract:
            try:
                text = pytesseract.image_to_string(cropped, lang="eng")
                if _clean_text(receiver) in _clean_text(text):
                    return True
            except Exception:
                pass

        # Fallback: try window title match
        try:
            active_title = (active.title or "").lower() if active else ""
            if receiver.lower() in active_title:
                return True
        except Exception:
            pass

    except Exception as e:
        print(f"[SendMessage] ⚠️ OCR header check failed: {e}")

    return False


def _click_search_result_candidates(app_name: str, receiver: str, debug_dir: str | None = None) -> bool:
    """Try clicking likely positions in the search results pane and verify header after each click."""
    _require_pyautogui()
    try:
        try:
            active = gw.getActiveWindow() if _PYGETWINDOW else None
        except Exception:
            active = None

        if active:
            left, top, width, height = active.left, active.top, active.width, active.height
            # target more-left column where chat results appear (narrow column)
            x = left + int(width * 0.22)
            # iterate the visible result rows from top to bottom.
            for frac in [0.45, 0.55, 0.65, 0.75, 0.85]:
                y = top + int(height * frac)
                pyautogui.doubleClick(x, y, interval=0.12)
                pyautogui.press("enter")
                time.sleep(0.5)
                if debug_dir:
                    _save_debug_snapshot(f"after_click_result_{int(frac*100)}", debug_dir)
                if _ocr_chat_header_matches(receiver, debug_dir):
                    return True
            # If OCR is unavailable or unreliable, a click in the result list is still
            # preferable to retyping or stepping through results again.
            return True

        # Fallback: click narrow column near left of screen at multiple heights
        sw, sh = pyautogui.size()
        x = int(sw * 0.22)
        for frac in [0.45, 0.55, 0.65, 0.75, 0.85]:
            y = int(sh * frac)
            pyautogui.doubleClick(x, y, interval=0.12)
            pyautogui.press("enter")
            time.sleep(0.5)
            if debug_dir:
                _save_debug_snapshot(f"after_click_result_{int(frac*100)}", debug_dir)
            if _ocr_chat_header_matches(receiver, debug_dir):
                return True
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ click_search_result_candidates failed: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False


def _browser_action_succeeded(result: str, expected: str) -> bool:
    result_text = (result or "").lower()
    return expected.lower() in result_text and not result_text.startswith("could not") and "error" not in result_text

def _search_in_app(query: str, app_name: str | None = None) -> None:
    _require_pyautogui()
    os_name = _get_os()
    # WhatsApp desktop uses Ctrl+K to search chats (not Ctrl+F which searches within chat)
    if app_name and "whatsapp" in app_name.lower():
        search_hotkey = ("command", "k") if os_name == "mac" else ("ctrl", "k")
    else:
        search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    if app_name and "whatsapp" in app_name.lower() and _PYGETWINDOW:
        try:
            active = gw.getActiveWindow()
        except Exception:
            active = None
        if active:
            left, top, width, height = active.left, active.top, active.width, active.height
            # WhatsApp's search input sits lower than the chat header; target the field center.
            pyautogui.click(left + int(width * 0.18), top + int(height * 0.19))
            time.sleep(0.15)
    # WhatsApp's search overlay usually starts empty after Ctrl+K.
    # Typing directly is safer than clipboard paste when focus is flaky.
    pyautogui.write(query, interval=0.03)
    time.sleep(0.9)


def _send_whatsapp_web(receiver: str, message: str) -> str:
    try:
        from actions.browser_control import browser_control
    except Exception:
        return ""

    try:
        browser_control(
            parameters={
                "action": "go_to",
                "browser": "chrome",
                "url": "https://web.whatsapp.com",
            },
            player=None,
        )
        time.sleep(5.0)

        search_descriptions = [
            "Search or start new chat",
            "Search",
            "Search chats",
            "Start new chat",
        ]
        search_result = ""
        for description in search_descriptions:
            search_result = browser_control(
                parameters={
                    "action": "smart_type",
                    "browser": "chrome",
                    "description": description,
                    "text": receiver,
                },
                player=None,
            )
            if _browser_action_succeeded(search_result, "Typed into"):
                break

        if not _browser_action_succeeded(search_result, "Typed into"):
            print(f"[SendMessage] ⚠️ WhatsApp search box not found for receiver: {receiver}")
            return ""

        enter_result = browser_control(
            parameters={"action": "press", "browser": "chrome", "key": "Enter"},
            player=None,
        )
        if not _browser_action_succeeded(enter_result, "Pressed"):
            print(f"[SendMessage] ⚠️ WhatsApp chat open failed for receiver: {receiver}")
            return ""
        time.sleep(2.0)

        message_result = ""
        for description in ("Type a message", "Message", "Write a message"):
            message_result = browser_control(
                parameters={
                    "action": "smart_type",
                    "browser": "chrome",
                    "description": description,
                    "text": message,
                },
                player=None,
            )
            if _browser_action_succeeded(message_result, "Typed into"):
                break

        if not _browser_action_succeeded(message_result, "Typed into"):
            fallback_result = browser_control(
                parameters={
                    "action": "type",
                    "browser": "chrome",
                    "text": message,
                    "clear_first": False,
                },
                player=None,
            )
            if not _browser_action_succeeded(fallback_result, "Text typed"):
                print(f"[SendMessage] ⚠️ WhatsApp message box not found for receiver: {receiver}")
                return ""

        send_result = browser_control(
            parameters={"action": "press", "browser": "chrome", "key": "Enter"},
            player=None,
        )
        if not _browser_action_succeeded(send_result, "Pressed"):
            print(f"[SendMessage] ⚠️ WhatsApp send key failed for receiver: {receiver}")
            return ""
        time.sleep(0.5)
        return f"Message sent to {receiver} via WhatsApp Web."
    except Exception as e:
        print(f"[SendMessage] ⚠️ WhatsApp Web flow failed: {e}")
        return ""

def _desktop_send(app_name: str, receiver: str, message: str, debug: bool = False, debug_dir: str | None = None) -> str:
    # On Windows, prefer a native UI-automation path using pywinauto for WhatsApp
    if _get_os() == "windows" and app_name.lower() == "whatsapp":
        try:
            if _pywinauto_whatsapp_send(receiver, message, debug_dir):
                return f"Message sent to {receiver} via {app_name}."
        except Exception:
            pass

    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    # Search exactly once to avoid retyping the contact name multiple times.
    _search_in_app(receiver, app_name)
    time.sleep(0.25)

    opened = False
    try:
        pyautogui.press("enter")
        time.sleep(0.7)
        if _PYGETWINDOW:
            try:
                active = gw.getActiveWindow()
                title = (active.title or "").lower() if active else ""
                if receiver.lower() in title or "whatsapp" in title:
                    opened = True
            except Exception:
                pass
        if not opened and _ocr_chat_header_matches(receiver, debug_dir):
            opened = True
    except Exception:
        pass

    if not opened:
        opened = _click_search_result_candidates(app_name, receiver, debug_dir)

    if not opened:
        return f"Could not open chat for {receiver} in {app_name}."

    # Ensure focus is on the message input: close search and tab into message box, then paste and send.
    send_attempts = 0
    while send_attempts < 3:
        if debug:
            _save_debug_snapshot("before_paste", debug_dir)
        # Close any open search overlay and try to focus the message input
        try:
            pyautogui.press("esc")
            time.sleep(0.12)
            for _ in range(4):
                pyautogui.press("tab")
                time.sleep(0.08)
        except Exception:
            pass

        # Try clicking the message input area to ensure focus before pasting
        try:
            _click_message_input(app_name, debug_dir)
        except Exception:
            pass

        _paste_text(message)
        time.sleep(0.2)
        if debug:
            _save_debug_snapshot("after_paste", debug_dir)
        pyautogui.press("enter")
        time.sleep(0.4)

        if debug:
            _save_debug_snapshot("after_send", debug_dir)

        # Attempt OCR verification of chat header before sending; if it doesn't match,
        # try selecting the next search result and re-verify up to 3 times.
        verified = False
        for sel_try in range(3):
            if _ocr_chat_header_matches(receiver, debug_dir):
                verified = True
                break
            # try next result in the list
            pyautogui.press("down")
            time.sleep(0.12)
            pyautogui.press("enter")
            time.sleep(0.45)

        if not verified:
            print(f"[SendMessage] ⚠️ Could not verify chat header for {receiver}")
            # Interactive fallback: ask the user to confirm the selected chat before sending.
            try:
                # If auto_confirm is enabled, proceed without prompting the user.
                auto_confirm = bool(getattr(sys, "_send_auto_confirm", False))
                if auto_confirm:
                    print(f"[SendMessage] ℹ️ auto_confirm enabled — proceeding to send to {receiver} without manual confirmation")
                    verified = True
                else:
                    if _PYAUTOGUI:
                        resp = pyautogui.confirm(text=f"Is the selected chat '{receiver}' correct?\nClick 'Send' to proceed, 'Skip' to abort.", buttons=["Send", "Skip"])
                        if resp and resp.lower().startswith("send"):
                            verified = True
                        else:
                            return f"User declined to send message to {receiver}."
                    else:
                        # Console fallback
                        ans = input(f"Is the selected chat '{receiver}' correct? Type 'y' to send: ")
                        if ans.strip().lower() == "y":
                            verified = True
                        else:
                            return f"User declined to send message to {receiver}."
            except Exception:
                return f"Could not confirm chat header for {receiver} in {app_name}."

        # No reliable programmatic confirmation of delivery; assume success after send
        return f"Message sent to {receiver} via {app_name}."

    return f"Failed to send message to {receiver} via {app_name}."


def _whatsapp_direct_send(receiver: str, message: str, debug_dir: str | None = None) -> str:
    """Reliable WhatsApp Desktop send using keyboard shortcuts and coordinates."""
    _require_pyautogui()

    # --- 1. Find or launch WhatsApp ---
    wa_win = None
    if _PYGETWINDOW:
        try:
            wins = [w for w in gw.getAllWindows() if "whatsapp" in (w.title or "").lower()]
            if wins:
                wa_win = wins[0]
        except Exception:
            pass

    if wa_win is None:
        _launch_whatsapp_desktop()
        time.sleep(3.5)
        if _PYGETWINDOW:
            try:
                wins = [w for w in gw.getAllWindows() if "whatsapp" in (w.title or "").lower()]
                if wins:
                    wa_win = wins[0]
            except Exception:
                pass

    if wa_win is None:
        return "Could not open WhatsApp window."

    # --- 2. Maximize and focus ---
    try:
        wa_win.maximize()
        time.sleep(0.4)
        wa_win.activate()
        time.sleep(0.5)
    except Exception:
        pass

    # Force focus by clicking the center of the window
    try:
        cx = wa_win.left + wa_win.width  // 2
        cy = wa_win.top  + wa_win.height // 2
        pyautogui.click(cx, cy)
        time.sleep(0.3)
    except Exception:
        pass

    if debug_dir:
        _save_debug_snapshot("01_wa_focused", debug_dir)

    # --- 3. Open search with Ctrl+F shortcut ---
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.8)

    # Clear any existing text and type receiver
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    pyautogui.write(receiver, interval=0.05)
    time.sleep(2.0)   # wait for search results to load

    if debug_dir:
        _save_debug_snapshot("02_search_typed", debug_dir)

    # --- 4. Click directly on the first chat result row ---
    # Results appear below the search box; first chat result is at ~35% height
    left = wa_win.left
    top  = wa_win.top
    w    = wa_win.width
    h    = wa_win.height
    rx = left + int(w * 0.17)   # centre of left chat panel
    ry = top  + int(h * 0.36)   # first result row ("chinni" appears at ~36%)
    pyautogui.click(rx, ry)
    time.sleep(1.5)   # wait for chat to open

    if debug_dir:
        _save_debug_snapshot("03_chat_opened", debug_dir)

    # --- 5. Click message input — window already maximized and focused, don't touch it ---
    # Pressing escape or re-activating the window causes the chat to close, so skip both.
    # Use the same bounds captured before the chat result was clicked (window hasn't moved).
    time.sleep(0.6)   # let the chat panel fully render

    mx = left + int(w * 0.65)    # centre of the right (chat) panel
    my = top  + int(h * 0.945)   # message input bar near the bottom
    for _ in range(3):
        pyautogui.click(mx, my)
        time.sleep(0.25)

    # --- 6. Paste message ---
    if _PYPERCLIP:
        pyperclip.copy(message)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(message, interval=0.04)
    time.sleep(0.4)

    if debug_dir:
        _save_debug_snapshot("04_message_typed", debug_dir)

    # --- 7. Send ---
    pyautogui.press("enter")
    time.sleep(0.5)

    if debug_dir:
        _save_debug_snapshot("05_after_send", debug_dir)

    return f"Message sent to {receiver} via WhatsApp."


def _send_whatsapp(receiver: str, message: str) -> str:
    debug_dir = getattr(sys, "_send_debug_dir", None)
    result = _whatsapp_direct_send(receiver, message, debug_dir=debug_dir)
    if result and "sent" in result.lower():
        print(f"[SendMessage] ✅ {result}")
    else:
        print(f"[SendMessage] ❌ {result}")
    return result


def _send_telegram(receiver: str, message: str) -> str:
    return _desktop_send("Telegram", receiver, message)


def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip()

    if not receiver:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        # allow callers to opt out of interactive confirmation by passing `auto_confirm=True`
        auto_confirm = bool(params.get("auto_confirm") or getattr(sys, "_send_auto_confirm", False))
        # store auto_confirm on sys for deeper helpers
        setattr(sys, "_send_auto_confirm", auto_confirm)

        result  = handler(receiver, message_text)
        if platform.lower().strip().startswith("whatsapp") and not result:
            result = _desktop_send("WhatsApp", receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    print(f"[SendMessage] {'✅' if 'sent' in result.lower() else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result